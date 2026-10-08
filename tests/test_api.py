"""Tests der API: vier Tests, je einer für eine zentrale Zusage.

1. Die Prognose deckt 24 Stunden in 15-Minuten-Schritten ab.
2. Falsche Anfragen werden sauber abgewiesen (404 und 422). 404: Anfrage ist gültig, aber den Film gibt es nicht. 422: Anfrage selbst ist fehlerhaft (z. B. limit=0).
3. Die Prognose ist aktuell, und veraltete Prognosen werden gemeldet.
4. Die Felder der Antwort ändern sich nicht.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app, is_stale

# Rufe die FastAPI-App direkt im Python-Prozess auf
# -> Tests laufen schnell ohne Uvicorn und ohne Netzwerk
client = TestClient(app)


def test_forecast_covers_24_hours_in_15_minute_steps():
    """Die Kernzusage der Aufgabe: 96 Werte, lückenlos im 15-Minuten-Raster."""
    response = client.get("/v1/forecasts", params={"limit": 5})
    assert response.status_code == 200

    films = response.json()["films"]
    assert len(films) == 5
    for film in films:
        assert len(film["points"]) == 96

    times = [datetime.fromisoformat(p["interval_start"]) for p in films[0]["points"]]
    for i in range(1, len(times)):
        assert times[i] - times[i - 1] == timedelta(minutes=15)

    # Die gröbere Aggregationsebene: gleiches Raster, aber Summe über alle Filme.
    # Sie muss größer sein als der beliebteste Einzelfilm.
    total = client.get("/v1/forecasts/total")
    assert total.status_code == 200
    points = total.json()["points"]
    assert len(points) == 96
    assert points[0]["predicted_streams"] > films[0]["points"][0]["predicted_streams"]


def test_invalid_requests():
    """404 und 422 bedeuten Unterschiedliches und kommen aus unterschiedlichen Quellen."""
    # 404: Die Anfrage ist gültig, den Film gibt es nicht. Das lösen wir selbst aus.
    assert client.get("/v1/forecasts", params={"film_id": 9999}).status_code == 404

    # 422: Die Anfrage selbst ist fehlerhaft, der Wert verletzt ge/le.
    # Das macht FastAPI über Query, bevor unsere Funktion startet.
    assert client.get("/v1/forecasts", params={"limit": 0}).status_code == 422
    assert client.get("/v1/forecasts", params={"limit": 5000}).status_code == 422


def test_forecast_is_fresh_and_reports_staleness():
    """Die API liefert den neuesten Lauf und sagt dazu, wenn er veraltet ist."""
    body = client.get("/v1/forecasts", params={"film_id": 1}).json()
    # 16 statt 15 Minuten: generated_at wird auf die letzte Viertelstunde abgerundet.
    age = datetime.now(UTC) - datetime.fromisoformat(body["generated_at"])
    assert age < timedelta(minutes=16)
    assert body["stale"] is False

    # Die 30-Minuten-Grenze direkt auf der Funktion: Die Dummydaten sind immer
    # frisch, über die API wäre stale=True gar nicht herstellbar.
    now = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
    assert is_stale(now - timedelta(minutes=45), now) is True
    assert is_stale(now - timedelta(minutes=10), now) is False


def test_response_fields_stay_the_same():
    """Clients verlassen sich auf diese Felder. Benennt jemand eins um, schlägt der Test fehl."""
    body = client.get("/v1/forecasts", params={"limit": 1}).json()
    assert set(body) == {"generated_at", "stale", "total_films", "films"}
    assert set(body["films"][0]) == {"film_id", "points"}
    assert set(body["films"][0]["points"][0]) == {"interval_start", "predicted_streams"}

    total = client.get("/v1/forecasts/total").json()
    assert set(total) == {"generated_at", "stale", "total_films", "points"}
    assert set(total["points"][0]) == {"interval_start", "predicted_streams"}
