import importlib
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"

    database = importlib.import_module("app.database")
    monkeypatch.setattr(database, "DB_PATH", db_path)

    main = importlib.import_module("app.main")
    with TestClient(main.app) as test_client:
        yield test_client


def test_store_and_verify(client):
    response = client.post(
        "/records",
        json={
            "request": "What is Python?",
            "response": "Python is a programming language.",
        },
    )

    assert response.status_code == 201
    record_id = response.json()["id"]

    verification = client.get(f"/verify/{record_id}")

    assert verification.status_code == 200
    assert verification.json()["valid"] is True
    assert verification.json()["broken"] == []


def test_tampering_is_detected(client):
    created = client.post(
        "/records",
        json={"request": "2 + 2?", "response": "4"},
    )
    assert created.status_code == 201
    record_id = created.json()["id"]

    database = importlib.import_module("app.database")

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            "UPDATE records SET response = ? WHERE id = ?",
            ("5", record_id),
        )
        conn.commit()

    verification = client.get(f"/verify/{record_id}")

    assert verification.status_code == 200
    body = verification.json()
    assert body["valid"] is False
    assert "content_hash" in body["broken"]


def test_chain_link_tampering_is_detected(client):
    first = client.post(
        "/records",
        json={"request": "A", "response": "B"},
    )
    second = client.post(
        "/records",
        json={"request": "C", "response": "D"},
    )

    assert first.status_code == 201
    assert second.status_code == 201

    second_id = second.json()["id"]

    database = importlib.import_module("app.database")

    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute(
            "UPDATE records SET previous_hash = ? WHERE id = ?",
            ("tampered", second_id),
        )
        conn.commit()

    verification = client.get(f"/verify/{second_id}")

    assert verification.status_code == 200
    body = verification.json()
    assert body["valid"] is False
    assert "content_hash" in body["broken"]
    assert "previous_hash" in body["broken"]
