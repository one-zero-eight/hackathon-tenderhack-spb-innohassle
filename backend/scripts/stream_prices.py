#!/usr/bin/env python3
"""Print products from the prices NDJSON stream."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_URL = "http://127.0.0.1:8000/prices/search"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call /prices/search and print every streamed product as it arrives.",
    )
    parser.add_argument("query", help="Search query, for example: 'iphone'")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Endpoint URL. Default: {DEFAULT_URL}")
    parser.add_argument("--limit", type=int, default=20, help="Max products per marketplace. Default: 20")
    parser.add_argument("--skip", type=int, default=0, help="Products to skip per marketplace. Default: 0")
    parser.add_argument(
        "--location",
        default="Москва",
        help="Region/city for marketplace pricing. Default: Москва",
    )
    parser.add_argument(
        "--bypass-spellchecker",
        action="store_true",
        help="Send bypass_spellchecker=true.",
    )
    parser.add_argument(
        "--bypass-relevance-filter",
        action="store_true",
        help="Send bypass_relevance_filter=true. By default the relevance filter is enabled.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print each product as compact JSON instead of a human-readable line.",
    )
    parser.add_argument(
        "--compare-relevance-filter",
        action="store_true",
        help="Run twice: with the relevance filter enabled, then bypassed, and print timing overhead.",
    )
    parser.add_argument("--relevance-quality", default="high")
    return parser.parse_args()


@dataclass
class StreamStats:
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    started_at: float = field(default_factory=time.perf_counter)
    first_product_at: float | None = None
    finished_at: float | None = None

    @property
    def elapsed(self) -> float:
        ended_at = self.finished_at or time.perf_counter()
        return ended_at - self.started_at

    @property
    def first_product_elapsed(self) -> float | None:
        if self.first_product_at is None:
            return None
        return self.first_product_at - self.started_at


def main() -> int:
    args = parse_args()
    body = {
        "query": args.query,
        "limit": args.limit,
        "skip": args.skip,
        "location": args.location,
        "bypass_spellchecker": args.bypass_spellchecker,
        "bypass_relevance_filter": args.bypass_relevance_filter,
        "relevance_quality": args.relevance_quality
    }

    if args.compare_relevance_filter:
        return compare_relevance_filter(args, body)

    stats = run_stream(args.url, body, json_output=args.json, label=None)
    return 0 if stats else 1


def compare_relevance_filter(args: argparse.Namespace, body: dict[str, Any]) -> int:
    print("=== relevance filter enabled ===", flush=True)
    filtered_body = {**body, "bypass_relevance_filter": False}
    filtered = run_stream(args.url, filtered_body, json_output=args.json, label="filtered")
    if filtered is None:
        return 1

    print("=== relevance filter bypassed ===", flush=True)
    bypassed_body = {**body, "bypass_relevance_filter": True}
    bypassed = run_stream(args.url, bypassed_body, json_output=args.json, label="bypassed")
    if bypassed is None:
        return 1

    delta = filtered.elapsed - bypassed.elapsed
    pct = (delta / bypassed.elapsed * 100) if bypassed.elapsed else 0.0
    print(
        "filter_overhead "
        f"filtered={filtered.elapsed:.2f}s "
        f"bypassed={bypassed.elapsed:.2f}s "
        f"delta={delta:+.2f}s "
        f"delta_pct={pct:+.1f}%",
        flush=True,
    )
    return 0


def run_stream(
    url: str,
    body: dict[str, Any],
    *,
    json_output: bool,
    label: str | None,
) -> StreamStats | None:
    stats = StreamStats()
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/x-ndjson",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=None) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    print(f"Bad NDJSON line: {exc}: {line!r}", file=sys.stderr)
                    continue

                if handle_event(event, stats, json_output=json_output, label=label):
                    break
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"Request failed: HTTP {exc.code} {exc.reason}: {detail}", file=sys.stderr)
        return None
    except URLError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return None

    stats.finished_at = stats.finished_at or time.perf_counter()
    print_summary(stats, label=label)
    return stats


def handle_event(event: dict[str, Any], stats: StreamStats, *, json_output: bool, label: str | None) -> bool:
    event_type = event.get("type")
    elapsed = stats.elapsed
    prefix = f"[{label}] " if label else ""

    if event_type == "meta":
        fixed_query = event.get("fixed_query")
        query = fixed_query or event.get("query")
        print(f"{prefix}{elapsed:.2f}s meta query={query!r} fixed_query={fixed_query!r}", flush=True)
        return False

    if event_type == "batch":
        source = str(event.get("source") or "unknown")
        prices = event.get("prices") or []

        for product in prices:
            stats.counts[source] += 1
            if stats.first_product_at is None:
                stats.first_product_at = time.perf_counter()
            print_product(
                source,
                stats.counts[source],
                product,
                elapsed=stats.elapsed,
                json_output=json_output,
                label=label,
            )
        return False

    if event_type == "source_done":
        source = event.get("source") or "unknown"
        error = event.get("error")
        suffix = f" error={error!r}" if error else ""
        print(
            f"{prefix}{elapsed:.2f}s source_done source={source!r} count={stats.counts[str(source)]}{suffix}",
            flush=True,
        )
        return False

    if event_type == "done":
        stats.finished_at = time.perf_counter()
        print(f"{prefix}{stats.elapsed:.2f}s done totals={dict(stats.counts)}", flush=True)
        return True

    print(f"unknown_event {json.dumps(event, ensure_ascii=False)}", file=sys.stderr, flush=True)
    return False


def print_product(
    source: str,
    number: int,
    product: Any,
    *,
    elapsed: float,
    json_output: bool,
    label: str | None,
) -> None:
    prefix = f"[{label}] " if label else ""
    if not isinstance(product, dict):
        print(f"{prefix}{elapsed:.2f}s {source} #{number}: {product!r}", flush=True)
        return

    if json_output:
        payload = {"elapsed_seconds": round(elapsed, 3), "source": source, **product}
        if label:
            payload["run"] = label
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
        return

    name = product.get("name") or "<no name>"
    brand = product.get("brand")
    price = format_price(product.get("price"))
    original_price = product.get("original_price")
    url = product.get("url")

    brand_part = f"{brand} " if brand else ""
    original_part = f" original={format_price(original_price)}" if original_price is not None else ""
    url_part = f" url={url}" if url else ""
    print(
        f"{prefix}{elapsed:.2f}s {source} #{number}: "
        f"{brand_part}{name} price={price}{original_part}{url_part}",
        flush=True,
    )


def print_summary(stats: StreamStats, *, label: str | None) -> None:
    prefix = f"[{label}] " if label else ""
    first_product = stats.first_product_elapsed
    first_product_part = f" first_product={first_product:.2f}s" if first_product is not None else ""
    print(
        f"{prefix}summary elapsed={stats.elapsed:.2f}s{first_product_part} totals={dict(stats.counts)}",
        flush=True,
    )


def format_price(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int | float):
        return f"{value:g}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
