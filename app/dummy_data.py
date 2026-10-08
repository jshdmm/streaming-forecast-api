"""Dummydaten: simuliert, was der Prognose-Job alle 15 Minuten in die Datenbank schreibt.

In Produktion stünde hier eine SQL Datenbankabfrage, ungefähr so:

    SELECT film_id, interval_start, predicted_streams
    FROM forecast
    WHERE generated_at = (SELECT max(generated_at) FROM forecast)


In diesem Skript werden Daten generiert, die so auch in der Kunden-Datenbank stehen könnten. Die API holt sich die Daten hierher, 
anstatt sie wie im realen Setting aus der DB zu lesen. Die Modellierung ist nicht Teil der Challenge. 
Ich gehe aber hier davon aus, dass ein ML-Service Prognosen basierend auf den Kundendaten in unsere System-Datenbank geschrieben hat.
"""

# packages
import random
from datetime import datetime, timedelta

# Anzahl der Filme im Katalog
N_FILMS = 1000

# 15-minute interval 
INTERVAL = timedelta(minutes=15)

# Intervalle pro Tag
N_INTERVALS = 96  # 24 Stunden x 4 Intervalle pro Stunde

# Ein Wert pro Stunde für die Auslastung des Streaming-services
# Multiplikator * UTC (Standard) Index für die jeweilige Stunde
# Simuliert den Tagesverlauf: Morgens wenig, abends viel Abrufe. Summe = 12,5, damit der Mittelwert über 24h = 1 ist.
HOURLY_PROFILE = [
    0.35, 0.22, 0.15, 0.12, 0.12, 0.18, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
    0.52, 0.55, 0.58, 0.62, 0.70, 0.80, 0.92, 1.00, 1.00, 0.90, 0.75, 0.55,
]  # fmt: skip

# Film 1 ist der beliebteste. Film k bekommt 1/k davon (wenige Hits, viele Nischenfilme).
PEAK_STREAMS_FILM_1 = 20_000


def floor_to_interval(ts: datetime) -> datetime:
    """Rundet auf den Beginn des 15-Minuten-Intervalls ab, z. B. 13:07 -> 13:00."""
    return ts.replace(minute=ts.minute - ts.minute % 15, second=0, microsecond=0)


def latest_run_time(now: datetime) -> datetime:
    """Startzeit des neuesten Prognoselaufs. Der Job läuft alle 15 Minuten."""
    return floor_to_interval(now)

# Funktion, die die Forecast-Werte simuliert. Sie simuliert, dass der Prognose-Job alle 15 Minuten neue Werte in die Datenbank schreibt.
def forecast_for_film(film_id: int, start: datetime) -> list[dict]:
    """96 Prognosewerte für einen Film, ab `start` in 15-Minuten-Schritten."""
    
    # Fester Seed je Film und Lauf: Dieselbe Anfrage liefert dieselben Zahlen.
    rng = random.Random(f"{film_id}-{start.isoformat()}")

    points = []
    for i in range(N_INTERVALS):
        interval_start = start + i * INTERVAL
        expected = PEAK_STREAMS_FILM_1 * HOURLY_PROFILE[interval_start.hour] / film_id
        with_noise = expected * rng.uniform(0.9, 1.1)
        points.append({"interval_start": interval_start, "predicted_streams": round(with_noise, 1)})
    return points


def total_forecast(start: datetime) -> list[dict]:
    """Summe über alle Filme je Intervall: die Gesamtlast auf den Servern.

    In Produktion macht das die Datenbank, nicht die API:

        SELECT interval_start, sum(predicted_streams)
        FROM forecast
        WHERE generated_at = (SELECT max(generated_at) FROM forecast)
        GROUP BY interval_start
    """
    totals = [0.0] * N_INTERVALS
    for film_id in range(1, N_FILMS + 1):
        for i, point in enumerate(forecast_for_film(film_id, start)):
            totals[i] += point["predicted_streams"]

    return [
        {"interval_start": start + i * INTERVAL, "predicted_streams": round(total, 1)}
        for i, total in enumerate(totals)
    ]
