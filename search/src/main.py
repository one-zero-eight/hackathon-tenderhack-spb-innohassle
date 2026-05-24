from __future__ import annotations

import json
import random
import uuid
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from query_rewrite import rewrite_query
from yandex_search import (
    YandexCaptchaError,
    close_browser_session,
    init_browser_session,
    search_yandex,
)

NDJSON_MEDIA_TYPE = "application/x-ndjson"
API_PREFIX = "/search-api"
STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

RESPONSES_DIR = Path(__file__).resolve().parent.parent / "responses"
RESPONSES_DIR.mkdir(parents=True, exist_ok=True)


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _print_progress(payload: dict) -> None:
    event_type = payload.get("type")

    if event_type == "meta":
        print(f"meta: query={payload.get('query')!r}", flush=True)
        return

    if event_type == "data":
        sites = payload.get("data", [])
        products = sum(len(site.get("products", [])) for site in sites)
        print(f"data: sites={len(sites)} products={products}", flush=True)
        return

    if event_type == "done":
        print("done", flush=True)
        return

    print(f"{event_type}: {payload}", flush=True)


def _format_update(payload: dict) -> str:
    _print_progress(payload)
    return _ndjson_line(payload)


def _load_response_events(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    events: list[dict] = []
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        event, offset = decoder.raw_decode(text, index)
        events.append(event)
        index = offset
    return events


def _pick_random_response_file() -> Path:
    files = sorted(RESPONSES_DIR.glob("*.json"))
    if not files:
        raise HTTPException(status_code=503, detail="No mock response files in responses/")
    return random.choice(files)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_browser_session()
    yield
    await close_browser_session()


app = FastAPI(lifespan=lifespan, root_path=API_PREFIX)


async def _yandex_search_stream(query: str, region: str) -> AsyncIterator[str]:
    rewritten_query = rewrite_query(query, region)
    yield _format_update({
        "type": "meta",
        "query": query,
        "region": region,
        "rewritten_query": rewritten_query,
    })

    last_sites: list[dict] = []
    try:
        async for sites in search_yandex(query, region):
            last_sites = sites
            yield _format_update({
                "type": "data",
                "data": sites,
            })
    except YandexCaptchaError as error:
        print(error)
        if last_sites:
            yield _format_update({
                "type": "data",
                "data": last_sites,
            })

    yield _format_update({"type": "done"})


async def _log_yandex_search_stream(query: str, region: str) -> AsyncIterator[str]:
    request_path = RESPONSES_DIR / f"{uuid.uuid4()}.json"

    async for event in _yandex_search_stream(query, region):
        yield event
        with request_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(json.loads(event), ensure_ascii=False, indent=2) + "\n")


async def _mock_yandex_search_stream() -> AsyncIterator[str]:
    path = _pick_random_response_file()
    print(f"mock: streaming {path.name}", flush=True)
    for event in _load_response_events(path):   
        time.sleep(random.uniform(1, 5))
        yield _format_update(event)


@app.get("/yandex_search")
async def yandex_search(
    query: str = Query(..., min_length=1),
    region: str = Query("санкт-петербург", min_length=1),
):
    return StreamingResponse(
        _log_yandex_search_stream(query, region),
        media_type=NDJSON_MEDIA_TYPE,
        headers=STREAM_HEADERS,
    )


@app.get("/yandex_search_mock")
async def yandex_search_mock(
    query: str = Query(..., min_length=1),
    region: str = Query("санкт-петербург", min_length=1),
):
    del query, region
    return StreamingResponse(
        _mock_yandex_search_stream(),
        media_type=NDJSON_MEDIA_TYPE,
        headers=STREAM_HEADERS,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9005,
        reload=False,
        root_path=API_PREFIX,
    )
