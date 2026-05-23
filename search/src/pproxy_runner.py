"""Start pproxy with a working asyncio loop (``python -m pproxy`` fails on 3.12+)."""

from __future__ import annotations

import asyncio


def main() -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())
    import uvloop  # noqa: PLC0415

    uvloop.install = lambda: None  # type: ignore[misc, assignment]
    from pproxy.server import main as pproxy_main  # noqa: PLC0415

    pproxy_main()


if __name__ == "__main__":
    main()
