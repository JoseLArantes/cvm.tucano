from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import configurar_cors


def test_app_responde_preflight_para_origin_configurada() -> None:
    app = FastAPI()
    app.get("/health")(lambda: {"status": "ok"})
    settings = Settings.model_validate(
        {"BACKEND_CORS_ORIGINS": "http://localhost:3000,http://localhost:5173"}
    )
    configurar_cors(app, settings)

    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
