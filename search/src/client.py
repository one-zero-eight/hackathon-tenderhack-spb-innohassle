#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import textwrap

import httpx

SECTION = "═" * 72


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stream Yandex search API responses")
    parser.add_argument("query", help="Search query")
    parser.add_argument(
        "--region",
        default="санкт-петербург",
        help="Search region (default: санкт-петербург)",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:9005",
        help="API base URL (default: http://127.0.0.1:9005)",
    )
    return parser.parse_args()


def _shop_meta(site: dict) -> str:
    parts: list[str] = []
    if site.get("rating"):
        parts.append(f"★ {site['rating']}")
    if site.get("reviews"):
        parts.append(str(site["reviews"]))
    if site.get("delivery"):
        parts.append(str(site["delivery"]))
    return " · ".join(parts)


def _print_meta(event: dict) -> None:
    print(SECTION)
    print("  META")
    print(SECTION)
    for label, key in (
        ("Query", "query"),
        ("Region", "region"),
        ("Rewritten", "rewritten_query"),
    ):
        value = event.get(key)
        if value:
            print(f"  {label:<11} {value}")
    print()


def _print_product(product: dict, index: int) -> None:
    title = product.get("title") or "—"
    price = product.get("price")
    href = product.get("href")
    thumbnail = product.get("thumbnail")
    description = product.get("description")

    print(f"    {index}. {title}")
    if price:
        print(f"       price     {price}")
    if description:
        wrapped = textwrap.fill(
            description,
            width=68,
            initial_indent="       desc      ",
            subsequent_indent="                 ",
        )
        print(wrapped)
    if href:
        print(f"       url       {href}")
    if thumbnail:
        wrapped = textwrap.fill(
            thumbnail,
            width=68,
            initial_indent="       image     ",
            subsequent_indent="                 ",
        )
        print(wrapped)


def _print_site(site: dict) -> None:
    hostname = site.get("hostname") or "?"
    meta = _shop_meta(site)
    header = f"  ▸ {hostname}"
    if meta:
        header = f"{header}  ({meta})"
    print(header)

    href = site.get("href")
    if href:
        print(f"       url       {href}")

    favicon = site.get("favicon")
    if favicon:
        wrapped = textwrap.fill(
            favicon,
            width=68,
            initial_indent="       favicon   ",
            subsequent_indent="                 ",
        )
        print(wrapped)

    items = site.get("products", [])
    if not items:
        print("    (no products yet)")
        print()
        return

    for index, product in enumerate(items, start=1):
        _print_product(product, index)
    print()


def _print_data(event: dict) -> None:
    sites = event.get("data", [])
    products = sum(len(site.get("products", [])) for site in sites)

    print(SECTION)
    print(f"  DATA   {len(sites)} shop(s), {products} product(s)")
    print(SECTION)

    if not sites:
        print("  (empty)")
        print()
        return

    for site in sites:
        _print_site(site)


def _print_done() -> None:
    print(SECTION)
    print("  DONE")
    print(SECTION)
    print()


def _print_event(event: dict) -> None:
    event_type = event.get("type")

    if event_type == "meta":
        _print_meta(event)
        return

    if event_type == "data":
        _print_data(event)
        return

    if event_type == "done":
        _print_done()
        return

    print(f"unknown event: {json.dumps(event, ensure_ascii=False)}")


def main() -> None:
    args = _parse_args()
    url = f"{args.base_url.rstrip('/')}/yandex_search"
    params = {"query": args.query, "region": args.region}

    with httpx.stream("GET", url, params=params, timeout=None) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            event = json.loads(line)
            _print_event(event)

            if event.get("type") == "done":
                break


if __name__ == "__main__":
    main()
