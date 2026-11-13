from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import create_app

LEAD = {"sender": "amaka@glowskin.ng", "subject": "Quote for deliveries",
        "body": "Hi, what are your rates for 40 deliveries a week? Budget N800k.", "channel": "web_form"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["engine"] == "rules"


def test_ingest_requires_api_key(client):
    assert client.post("/api/messages", json=LEAD).status_code == 401
    assert client.post("/api/messages", json=LEAD, headers={"X-API-Key": "wrong"}).status_code == 401


def test_ingest_triages_and_stores(client, auth):
    r = client.post("/api/messages", json=LEAD, headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert body["triage"]["category"] == "sales_lead"
    assert body["triage"]["amount"] == 800_000
    assert body["triage"]["currency"] == "NGN"
    assert body["engine"] == "rules"

    listed = client.get("/api/messages", headers=auth).json()
    assert len(listed) == 1 and listed[0]["id"] == body["id"]
    assert client.get(f"/api/messages/{body['id']}", headers=auth).status_code == 200
    assert client.get("/api/messages/999", headers=auth).status_code == 404

    stats = client.get("/api/stats", headers=auth).json()
    assert stats["total"] == 1 and stats["by_category"] == {"sales_lead": 1}


def test_filter_by_category(client, auth):
    client.post("/api/messages", json=LEAD, headers=auth)
    spam = {"sender": "x@lotto.biz", "body": "Congratulations, you have won! Click here to claim your prize."}
    client.post("/api/messages", json=spam, headers=auth)
    only_spam = client.get("/api/messages?category=spam", headers=auth).json()
    assert [m["triage"]["category"] for m in only_spam] == ["spam"]


def test_validation_errors(client, auth):
    assert client.post("/api/messages", json={"sender": "a@b.c"}, headers=auth).status_code == 422
    assert client.post("/api/messages", json={**LEAD, "channel": "pigeon"}, headers=auth).status_code == 422


def test_body_too_long(settings, auth):
    c = TestClient(create_app(replace(settings, max_message_chars=20)))
    assert c.post("/api/messages", json=LEAD, headers=auth).status_code == 413


def test_demo_endpoints_hidden_when_demo_off(client):
    assert client.post("/api/try", json=LEAD).status_code == 404
    assert client.get("/api/messages").status_code == 401


def test_demo_mode_public_and_rate_limited(settings):
    c = TestClient(create_app(replace(settings, demo_mode=True, demo_rate_per_minute=2)))
    assert c.get("/api/messages").status_code == 200
    assert "Inbox-to-" in c.get("/").text
    assert c.post("/api/try", json=LEAD).status_code == 200
    assert c.post("/api/try", json=LEAD).status_code == 200
    assert c.post("/api/try", json=LEAD).status_code == 429
    assert c.get("/api/stats").json()["total"] == 0  # /api/try never stores
