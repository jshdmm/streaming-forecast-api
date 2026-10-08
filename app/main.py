"""Forecast-API: Prognose der Abrufe je Film für die nächsten 24 Stunden.

Starten:  uvicorn app.main:app --reload
Doku:     http://localhost:8000/docs
"""

# packages
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException, Query

from app.dummy_data import N_FILMS, forecast_for_film, latest_run_time, total_forecast
from app.schemas import FilmForecast, ForecastResponse, TotalResponse

# initialize FastAPI app
app = FastAPI(title="Streaming Forecast API", version="0.1.0")

# Der Prognose-Job läuft alle 15 Minuten. Ist die neueste Prognose älter als
# 30 Minuten, ist mindestens ein Lauf ausgefallen.
MAX_AGE = timedelta(minutes=30)

# Hilfsfunktion: Ist die Prognose veraltet?
def is_stale(generated_at: datetime, now: datetime) -> bool:
    """Ist die Prognose veraltet?"""
    return now - generated_at > MAX_AGE

# Checken ob die API läuft
@app.get("/health")
def health() -> dict:
    """API antwortet?"""
    return {"status": "ok"}

# Haupt Forecast-Endpoint: Gibt die Prognosewerte für alle Filme zurück, oder nur für einen Film.
@app.get("/v1/forecasts", response_model=ForecastResponse)
def get_forecasts(
    film_id: int | None = Query(None, description="Nur diesen Film zurückgeben"), # set query parameters for the url
    limit: int = Query(100, ge=1, le=1000, description="Wie viele Filme pro Seite"),
    offset: int = Query(0, ge=0, description="Wie viele Filme überspringen"),
):
    # Die API rechnet nichts: Sie holt die neueste fertige Prognose.
    now = datetime.now(UTC)
    generated_at = latest_run_time(now)

    # Film Anfrage handeln
    if film_id is not None:
        if not 1 <= film_id <= N_FILMS:
            # 404: Die Anfrage ist gültig, aber den Film gibt es nicht. Das lösen wir selbst aus.
            raise HTTPException(status_code=404, detail=f"Film {film_id} gibt es nicht")
        film_ids = [film_id]
    else:
        # Seitenweise: alle 1.000 Filme auf einmal wären 96.000 Werte.
        film_ids = list(range(1, N_FILMS + 1))[offset : offset + limit]

    # ANTWORT: Wann gerechnet, wie alt, wie viele Filme insgesamt, und die Prognosewerte
    return ForecastResponse(
        generated_at=generated_at,
        stale=is_stale(generated_at, now),
        total_films=N_FILMS,
        films=[
            FilmForecast(film_id=fid, points=forecast_for_film(fid, generated_at))
            for fid in film_ids
        ],
    )


# Gröbere Aggregationsebene: nicht je Film, sondern die Summe über alle.
# Für die Kapazitätsplanung ist das die eigentlich wichtige Größe, denn die
# Server tragen die Gesamtlast. 96 Werte statt 96.000, also keine Seiten nötig.
@app.get("/v1/forecasts/total", response_model=TotalResponse)
def get_total():
    now = datetime.now(UTC)
    generated_at = latest_run_time(now)

    return TotalResponse(
        generated_at=generated_at,
        stale=is_stale(generated_at, now),
        total_films=N_FILMS,
        points=total_forecast(generated_at),
    )
