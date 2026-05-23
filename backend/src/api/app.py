from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from fastapi_swagger import patch_fastapi

import src.api.logging_  # noqa: F401
from src.api.lifespan import lifespan
from src.config import api_settings

app = FastAPI(
    docs_url=None, swagger_ui_oauth2_redirect_url=None, root_path=api_settings.app_root_path, lifespan=lifespan
)
app.router.route_class = AutoDeriveResponsesAPIRoute

patch_fastapi(app)


def _openapi_servers() -> list[dict[str, str]]:
    servers = list(app.servers)
    root_path = app.root_path.rstrip("/")
    if root_path and app.root_path_in_servers:
        root_path_server = {"url": root_path}
        if root_path_server not in servers:
            servers.insert(0, root_path_server)
    return servers


def _fix_response_headers(node: object) -> None:
    """HTTPException headers are serialized as plain strings; OpenAPI expects Header objects."""
    if isinstance(node, dict):
        headers = node.get("headers")
        if isinstance(headers, dict):
            for name, value in list(headers.items()):
                if isinstance(value, str):
                    headers[name] = {
                        "description": value,
                        "schema": {"type": "string", "example": value},
                    }
        for value in node.values():
            _fix_response_headers(value)
    elif isinstance(node, list):
        for item in node:
            _fix_response_headers(item)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        servers=_openapi_servers(),
    )
    _fix_response_headers(schema)
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=api_settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.prices.routes import router as prices_router  # noqa: E402

app.include_router(prices_router)
