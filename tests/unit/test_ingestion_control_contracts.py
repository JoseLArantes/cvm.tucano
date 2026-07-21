from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_dispatch_plan_is_confirmed_idempotently_and_exposes_work_item(client: TestClient, db_session: Session) -> None:
    del db_session
    plan_response = client.post(
        "/ingestion/dispatch/plan",
        json={"scopes": [{"fonte": "dfp", "ano": 2025}], "strategy": "direct", "force_reimport": False},
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["valid_scopes"][0]["fonte"] == "dfp"

    payload = {"scopes": [{"fonte": "dfp", "ano": 2025}], "strategy": "direct", "force_reimport": False, "plan_token": plan["plan_token"]}
    headers = {"Idempotency-Key": "network-retry-001"}
    first = client.post("/ingestion/dispatch", json=payload, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "accepted"
    assert first.json()["work_items"][0]["id"] == "dfp:2025"

    retry = client.post("/ingestion/dispatch", json=payload, headers=headers)
    assert retry.status_code == 200
    assert retry.json()["idempotent_replay"] is True

    work_items = client.get("/ingestion/work-items?fonte=dfp&ano=2025")
    assert work_items.status_code == 200
    assert work_items.json()["dados"][0]["id"] == "dfp:2025"
