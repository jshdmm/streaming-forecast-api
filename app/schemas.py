"""Die Form der API-Antwort.

Pydantic prüft die Daten (z. B. keine negativen Werte), wandelt sie in JSON um
und FastAPI erzeugt daraus die Doku unter /docs.
"""

# packages
from datetime import datetime

from pydantic import BaseModel, Field

# define Pydantic models for the API response

# ein einzelner Prognosewert für einen Film in einem 15-Minuten-Intervall
class ForecastPoint(BaseModel):
    interval_start: datetime  # Beginn des 15-Minuten-Intervalls (UTC)
    predicted_streams: float = Field(ge=0)  # Field-Constraint: erwartete Anzahl Streams: Soll: ge (greater-or-equal >=) 0 -> keine negativen Werte erlaubt

# Prognosewert für einen Film über alle Intervalle hinweg
class FilmForecast(BaseModel):
    film_id: int
    points: list[ForecastPoint] # sollte 96 Prognosen enthalten, eine für jedes 15-Minuten-Intervall der nächsten 24 Stunden, mit den Pydantic-Regeln eines einzelnen Films (ForecastPoint)

# Gesamte Antwort für alle Filme über alle Intervalle in den nächsten 24h
class ForecastResponse(BaseModel):
    generated_at: datetime  # wann die Prognose gerechnet wurde
    stale: bool  # True, wenn die Prognose älter als 30 Minuten ist
    total_films: int  # wie viele Filme es insgesamt gibt (für das Blättern)
    films: list[FilmForecast]

# Summe über alle Filme je Intervall. Gleiche Kopffelder wie ForecastResponse,
# damit ein Client beide Antworten gleich behandeln kann.
class TotalResponse(BaseModel):
    generated_at: datetime
    stale: bool
    total_films: int  # über wie viele Filme summiert wurde
    points: list[ForecastPoint]
