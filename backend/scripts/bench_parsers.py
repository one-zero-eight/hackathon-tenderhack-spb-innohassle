"""Замер WB/Ozon через пул (после prewarm)."""
import asyncio
import time

from src.api.parsers.browser_session_pool import init_browser_session_pool


async def main() -> None:
    query = "наушники беспроводные"
    limit = 5
    pool = init_browser_session_pool()

    t0 = time.perf_counter()
    await pool.prewarm()
    print(f"prewarm: {time.perf_counter() - t0:.1f}s")

    t1 = time.perf_counter()
    wb, ozon = await asyncio.gather(
        pool.parse_wildberries(query, limit),
        pool.parse_ozon(query, limit),
    )
    elapsed = time.perf_counter() - t1
    print(f"parallel parse: {elapsed:.1f}s  wb={len(wb)} ozon={len(ozon)}")

    t2 = time.perf_counter()
    wb2, ozon2 = await asyncio.gather(
        pool.parse_wildberries(query, limit),
        pool.parse_ozon(query, limit),
    )
    elapsed2 = time.perf_counter() - t2
    print(f"2nd parallel parse: {elapsed2:.1f}s  wb={len(wb2)} ozon={len(ozon2)}")

    await pool.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
