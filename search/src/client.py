#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

import httpx


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream Yandex search API responses")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="Call /yandex_search_extended instead of /yandex_search",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:9005",
        help="API base URL (default: http://127.0.0.1:9005)",
    )
    return parser.parse_args()


def _summarize_results(results: list[dict]) -> tuple[int, int, int, int]:
    hostnames = len(results)
    products = 0
    extracted = 0
    non_extracted = 0

    for group in results:
        for product in group.get("products", []):
            products += 1
            if product.get("extracted"):
                extracted += 1
            else:
                non_extracted += 1

    return hostnames, products, extracted, non_extracted


def _print_event_summary(event: dict) -> None:
    event_type = event.get("type")

    if event_type == "meta":
        print(f"meta: query={event.get('query')!r}")
        return

    if event_type == "page":
        hostnames, products, extracted, non_extracted = _summarize_results(event.get("results", []))
        print(
            f"page: "
            f"hostnames={hostnames} "
            f"products={products} "
            f"extracted={extracted} "
            f"non_extracted={non_extracted}"
        )
        return

    if event_type == "done":
        results = event.get("results")
        if results:
            hostnames, products, extracted, non_extracted = _summarize_results(results)
            print(
                f"total: "
                f"hostnames={hostnames} "
                f"products={products} "
                f"extracted={extracted} "
                f"non_extracted={non_extracted}"
            )
        print("done")
        return

    print(f"{event_type}: {event}")


def main() -> None:
    args = _parse_args()
    path = "/yandex_search_extended" if args.extended else "/yandex_search"
    url = f"{args.base_url.rstrip('/')}{path}"

    print(f"GET {url}?query={args.query!r}\n", file=sys.stderr)

    with httpx.stream("GET", url, params={"query": args.query}, timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            event = json.loads(line)
            with open("response.json", "w") as f:
                json.dump(event, f, ensure_ascii=False, indent=2)
            _print_event_summary(event)

            if event.get("type") == "done":
                break


if __name__ == "__main__":
    main()
