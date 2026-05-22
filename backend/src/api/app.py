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

from src.api.auth.routes import router as auth_router  # noqa: E402
from src.api.user.routes import router as user_router  # noqa: E402

app.include_router(auth_router)
app.include_router(user_router)
