# Streaming Forecast API

Prognose der Abrufzahlen von ca. 1.000 Filmen für die nächsten 24 Stunden in 15-Minuten-Intervallen,
bereitgestellt per REST-API. Lösung zur INWT DevOps/MLOps-Challenge.

Gefordert war eine einfache API mit Dummydaten plus Skizzen für Data Engineering, Deployment und Betrieb.
Lauffähig ist die API, die übrigen Teile sind als Konzept und Diagramme ausgearbeitet.

| Dokument | Inhalt |
| --- | --- |
| **Dieses README** | Setup, Start und die Endpunkte zum Ausprobieren |
| [docs/architecture.md](docs/architecture.md) | Die Diagramme: C4-Modell in drei Ebenen, dazu CI/CD |
| [docs/KONZEPT.md](docs/KONZEPT.md) | Die Begründungen: Data Engineering, Datenmodell, Deployment, Ausfälle |

## Quick-Start

Es gibt drei Wege, die API zu starten. Such dir **einen** aus. Alle drei nutzen Port 8000 und
können deshalb nicht gleichzeitig laufen.

| Weg | Wann sinnvoll | Voraussetzung |
| --- | --- | --- |
| A. Lokal mit Make | Entwickeln: Code-Änderungen greifen sofort | Python 3.12, `make` |
| B. Docker Compose | Prüfen, ob das Image funktioniert | Docker Desktop |
| C. Docker manuell | Verstehen, was Compose im Hintergrund tut | Docker Desktop |

### Weg A: Lokal mit Make

```bash
python -m venv .venv            # einmalig: eigene Python-Umgebung anlegen
source .venv/bin/activate       # aktivieren (in jedem neuen Terminal nötig)
make install                    # Abhängigkeiten installieren (inkl. pytest und ruff)
make run                        # API starten, mit automatischem Neustart bei Code-Änderungen
make test                       # Linter + Tests (unabhängig von make run)
```

Ohne `make`, die Befehle dahinter:

```bash
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
ruff check . && pytest
```

Für den reinen Betrieb ohne Entwicklungswerkzeuge reicht `pip install -r requirements.txt`.

### Weg B: Docker Compose

```bash
docker compose up --build       # Image bauen und Container starten (Strg+C stoppt)
docker compose up --build -d    # dasselbe im Hintergrund
docker compose logs -f api      # Logs ansehen
docker compose down             # stoppen und Container entfernen
```

`make docker` ist eine Abkürzung für `docker compose up --build`.

### Weg C: Docker manuell

```bash
docker build -t forecast-api .                    # Image bauen (der erste Build dauert einige Minuten)
docker run --rm -p 8000:8000 forecast-api         # Container starten
docker run -d --name forecast-api -p 8000:8000 forecast-api   # oder im Hintergrund
docker logs forecast-api                          # Logs ansehen
docker stop forecast-api && docker rm forecast-api            # aufräumen
```

`-p 8000:8000` ist wichtig: Ohne diese Port-Weiterleitung ist die API vom Rechner aus nicht erreichbar.

### Prüfen, ob die API läuft

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Danach im Browser `http://localhost:8000/docs` öffnen. Dort lassen sich alle Endpunkte direkt ausprobieren.
Die Adresse `http://localhost:8000/` allein gibt 404, weil es dort keine Route gibt.

## Endpunkte

Alle Beispiele gehen von `http://localhost:8000` aus.

| Anfrage | Was kommt zurück |
| --- | --- |
| `GET /v1/forecasts` | Die ersten 100 Filme mit je 96 Prognosewerten |
| `GET /v1/forecasts?limit=10` | Nur die ersten 10 Filme |
| `GET /v1/forecasts?limit=100&offset=100` | Filme 101 bis 200 |
| `GET /v1/forecasts?limit=100&offset=900` | Letzte Seite, Filme 901 bis 1000 |
| `GET /v1/forecasts?film_id=7` | Nur Film 7 (`limit` und `offset` werden dann ignoriert) |
| `GET /v1/forecasts/total` | Summe über alle 1.000 Filme je Intervall: 96 Werte, keine Seiten |
| `GET /health` | `{"status": "ok"}`, wenn die API läuft |
| `GET /docs` | Interaktive Swagger-Doku zum Ausprobieren |
| `GET /openapi.json` | Maschinenlesbare API-Beschreibung |

Parameter von `/v1/forecasts`:

| Parameter | Standard | Erlaubt | Bedeutung |
| --- | --- | --- | --- |
| `film_id` | – | 1 bis 1000 | Nur diesen Film zurückgeben |
| `limit` | 100 | 1 bis 1000 | Wie viele Filme pro Seite |
| `offset` | 0 | ab 0 | Wie viele Filme übersprungen werden |

Fehlerfälle:

| Anfrage | Antwort |
| --- | --- |
| `/v1/forecasts?film_id=5000` | 404, der Film existiert nicht |
| `/v1/forecasts?limit=0` oder `limit=2000` | 422, `limit` liegt außerhalb von 1 bis 1000 |
| `/v1/forecasts?offset=-1` | 422, `offset` darf nicht negativ sein |
| `/v1/forecasts?film_id=abc` | 422, keine Zahl |

Mit `curl`. Die Anführungszeichen gehören dazu: `?` und `&` haben in der Shell eine eigene Bedeutung.
In zsh (Standard auf macOS) bricht der Befehl ohne sie mit `no matches found` ab.

```bash
curl "http://localhost:8000/v1/forecasts?film_id=7"
curl "http://localhost:8000/v1/forecasts?limit=100&offset=100"
curl -s "http://localhost:8000/v1/forecasts?limit=2" | python -m json.tool   # lesbar formatiert
```

Oder einfach mit bash, dort geht es auch ohne Anführungszeichen:

```bash
curl http://localhost:8000/v1/forecasts?limit=10
```

Bei mehreren Parametern braucht aber auch bash die Anführungszeichen, sonst startet alles nach dem `&`
als eigener Befehl im Hintergrund.

Die API kennt nur `GET`: Sie liest die fertige Prognose aus, die Daten schreibt der Airflow-Job.

Beispielantwort (gekürzt):

```json
{
  "generated_at": "2026-10-08T09:00:00Z",
  "stale": false,
  "total_films": 1000,
  "films": [
    {"film_id": 7, "points": [
      {"interval_start": "2026-10-08T09:00:00Z", "predicted_streams": 1042.3}
    ]}
  ]
}
```

## Dateien

| Datei | Was sie tut |
| --- | --- |
| `app/main.py` | Die API: zwei Endpunkte und die Prüfung, ob eine Prognose veraltet ist |
| `app/schemas.py` | Die Form der Antwort (Pydantic) |
| `app/dummy_data.py` | Erzeugt Prognosewerte, wie sie der Prognose-Job in die Datenbank schreiben würde |
| `tests/test_api.py` | 4 Tests, je einer pro zentraler Zusage der API |
| `dags/daily_import.py` | Airflow-DAG (Skizze): täglicher Import um 6:00 UTC |
| `dags/forecast.py` | Airflow-DAG (Skizze): Prognose alle 15 Minuten |
| `Dockerfile` | Baut das Image der API |
| `docker-compose.yml` | Startet die API lokal im Container |
| `.github/workflows/ci.yml` | Bei jedem Pull Request: Linter, Tests, Image bauen und prüfen. Auf `main`: Image hochladen |

## Die Challenge

Wo die einzelnen Fragen der Aufgabenstellung beantwortet sind.

### Data Engineering

| Frage | Antwort |
| --- | --- |
| Wie würdest du die Daten aufbereiten? | [KONZEPT, Data Engineering](docs/KONZEPT.md#data-engineering): drei Quellen, eine eigene PostgreSQL, Zählung auf 15-Minuten-Intervalle |
| Welche Prozesse wären nötig? | Täglicher Import, Stream-Leser, Prognose-Job – gezeichnet in [architecture, Ebene 2](docs/architecture.md#ebene-2-container) |
| Wie werden die Daten für die Modellierung bereitgestellt? | [KONZEPT, Datenmodell](docs/KONZEPT.md#datenmodell-unsere-postgresql): `usage_15min JOIN film` ergibt eine Zeile pro Film und Intervall |

### API

| Frage | Antwort |
| --- | --- |
| Welche Endpunkte, welche Aggregationsebenen? | Zwei Ebenen umgesetzt: `GET /v1/forecasts` je Film und `GET /v1/forecasts/total` als Summe über alle. Als Nächstes käme eine Top-10 – [KONZEPT, API](docs/KONZEPT.md#api) |
| Auf welche Ressourcen muss sie zugreifen? | Nur auf die Tabelle `forecast` der eigenen Datenbank – [architecture, Ebene 3](docs/architecture.md#ebene-3-component-forecast-api) |
| Wie bleibt die Prognose möglichst aktuell? | Ein Job rechnet alle 15 Minuten vor, die Antwort enthält `generated_at` und `stale` |
| Skizze der API mit Abhängigkeiten | [architecture, Ebene 3](docs/architecture.md#ebene-3-component-forecast-api) |
| Einfache API mit Dummydaten | Umgesetzt in `app/`, siehe Quick-Start |

### Deployment

| Frage | Antwort |
| --- | --- |
| Wie werden die Prozesse bereitgestellt? | Docker-Container, Airflow startet die Jobs – [KONZEPT, Deployment](docs/KONZEPT.md#deployment) |
| Wie wird die API bereitgestellt? | `Dockerfile` und `docker-compose.yml`, Image über GitHub Actions nach GHCR – [architecture, CI/CD](docs/architecture.md#ergänzung-auslieferung-cicd) |
| Wie geht bei neuen Features nichts kaputt? | Pull Request mit Linter und Tests, Image wird im CI gestartet und geprüft, API-Felder werden nur ergänzt (`test_response_fields_stay_the_same`) |
| Welche Technologien kommen in Frage? | Python, FastAPI, Docker, Airflow, PostgreSQL, Kafka, GitHub Actions – Begründung in [KONZEPT](docs/KONZEPT.md) |

### Drei Entscheidungen, die den Entwurf prägen

- **Die API rechnet nichts.** Ein Job rechnet vor und speichert, die API liest nur. Dadurch antwortet sie in
  Millisekunden und liefert den letzten Stand auch dann, wenn der Job ausfällt.
- **Aktualität wird sichtbar gemacht, nicht versteckt.** Ist die neueste Prognose älter als 30 Minuten,
  steht `stale: true` in der Antwort. Die API liefert trotzdem, sagt es aber dazu.
- **Seitenweise.** Alle 1.000 Filme wären 96.000 Werte in einer Antwort. Standard sind 100 Filme pro Seite.

## Nächste Schritte

- PostgreSQL statt Dummydaten (die Abfragen stehen als Kommentar in `app/dummy_data.py`)
- Top-10-Endpunkt: die Filme mit der höchsten erwarteten Last
- Login per API-Key und Monitoring
