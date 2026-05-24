"""Run pproxy without uvloop (avoids asyncio.get_event_loop failures on 3.13+)."""

from __future__ import annotations

import asyncio
import sys
import types


def main() -> None:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    uvloop = types.ModuleType("uvloop")
    uvloop.install = lambda: None  # type: ignore[attr-defined]
    sys.modules["uvloop"] = uvloop

    from pproxy.server import main as pproxy_main

    pproxy_main()


if __name__ == "__main__":
    main()
