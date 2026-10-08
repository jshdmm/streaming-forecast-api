# Konzept: Streaming-Prognose für ca. 1.000 Filme

Die Lösung in einem Satz: Die Abrufzahlen werden in einer eigenen Datenbank gesammelt, alle 15 Minuten
wird eine neue Prognose für die nächsten 24 Stunden gerechnet und gespeichert, und die API gibt nur die
neueste gespeicherte Prognose aus.

> **Die Diagramme stehen in [architecture.md](architecture.md)** (C4-Modell, drei Ebenen). Dieses Dokument
> begründet die Entscheidungen dahinter und geht auf Datenmodell, Betrieb und Ausfälle ein.

## Überblick

Die Kundendaten landen über zwei Wege in unserer PostgreSQL: der tägliche Import holt die bereinigte
Historie und die Metadaten, der Stream-Leser zählt laufend die Kafka-Ereignisse. Airflow startet Import
und Prognose-Job nach Zeitplan, erledigt die Arbeit aber nicht selbst – die Jobs lesen und schreiben
direkt in der Datenbank. Der Prognose-Job füllt die Tabelle `forecast`, und die API liest nur daraus.

## Data Engineering

Drei Quellen, eine eigene PostgreSQL-Datenbank als Ziel.

| Quelle | Wie oft | Was passiert |
| --- | --- | --- |
| Nutzungs-DB (Historie) | einmal täglich | per Job in die eigene Datenbank kopieren und auf 15-Minuten-Intervalle zählen |
| Metadaten-DB (Genre, Release) | einmal täglich | per Job kopieren |
| Kafka (Echtzeit) | laufend | Stream-Leser zählt Starts pro Film und 15 Minuten |

- **Kopieren statt direkt beim Kunden abfragen:** So wird seine Datenbank nicht belastet, und unser System
  läuft weiter, wenn seine einmal nicht erreichbar ist.
- **Eine zentrale Tabelle:** `usage_15min (film_id, interval_start, streams, source)`. Eine Zeile = ein Film
  in einem 15-Minuten-Intervall. Zeiten in UTC, fehlende Intervalle bekommen 0.
- **Historie vor Echtzeit:** Für abgeschlossene Tage gelten die bereinigten Daten aus dem täglichen Import
  (`source = 'batch'`). Der Stream (`source = 'stream'`) füllt nur die Lücke bis jetzt.
- **Prognose-Job:** Läuft alle 15 Minuten, rechnet die nächsten 24 Stunden für alle Filme
  (96 Intervalle × 1.000 Filme = 96.000 Werte) und schreibt sie mit Zeitstempel in `forecast`.
- **Zeitplanung:** Airflow startet alle Jobs nach Zeitplan: den Import täglich um 6:00 UTC, den Prognose-Job
  alle 15 Minuten und das Training wöchentlich. Im Repo liegen die ersten beiden als DAGs (`dags/`).
  Airflow wiederholt fehlgeschlagene Tasks und zeigt jeden Lauf in seiner Oberfläche.
- **Idempotent laden:** Ein Job, der zweimal läuft, darf nichts doppelt schreiben. Deshalb wird immer ein
  ganzer Tag ersetzt: löschen und neu einfügen in einer Transaktion.

### Datenmodell (unsere PostgreSQL)

```sql
film         (film_id PK, title, genre, release_date)                     -- aus der Metadaten-DB
usage_15min  (film_id, interval_start, streams, source)                   -- PK (film_id, interval_start)
forecast     (generated_at, film_id, interval_start, predicted_streams)   -- PK (generated_at, film_id, interval_start)
```

`film_id` verbindet alle Tabellen. Für die Modellierung: `usage_15min JOIN film USING (film_id)` ergibt eine
Zeile pro Film und Intervall mit Abrufzahl und Metadaten. Aus den Kundendaten werden nur Zählungen
übernommen, keine `user_id` – es landen keine personenbezogenen Daten in unserer Datenbank.

## ML-Teil (nicht Teil der Challenge)

Das Modell ist kein dauerhaft laufender Service, sondern zwei Airflow-Jobs. Beide lesen nur aus unserer
PostgreSQL, nie direkt beim Kunden.

- **Training** (z. B. wöchentlich): liest `usage_15min` und `film`, trainiert das Modell und speichert es mit
  Versionsnummer (z. B. in MLflow). Freigegeben wird es nur, wenn es auf vergangenen Daten besser abschneidet
  als das aktuelle.
- **Prognose-Job** (alle 15 Minuten): lädt das freigegebene Modell, baut die Features mit demselben Code wie
  im Training, rechnet 96.000 Werte und schreibt sie in `forecast`.
- **Kein ML-Service mit eigener API:** Das Modell muss nicht auf Anfragen antworten, sondern nur alle
  15 Minuten rechnen. Ein Job, der startet, rechnet und sich beendet, braucht keinen dauerhaft laufenden Server.

## API

Die API rechnet nichts. Sie liest die neueste fertige Prognose aus der Datenbank und gibt sie als JSON zurück.

- **Endpunkt:** `GET /v1/forecasts?film_id=7` liefert für Film 7 die 96 Werte der nächsten 24 Stunden. Ohne
  `film_id` kommen alle Filme, seitenweise über `limit` (Standard 100) und `offset`.
- **Vorberechnet:** Die Antwort dauert Millisekunden. Fällt der Prognose-Job aus, liefert die API immer noch
  den letzten Stand.
- **Aktualität sichtbar:** Jede Antwort enthält, wann die Prognose gerechnet wurde (`generated_at`) und ob sie
  veraltet ist (`stale`, älter als 30 Minuten).
- **Health-Check:** `GET /health` antwortet `{"status": "ok"}`, solange die API läuft.
- **Zwei Aggregationsebenen:** `GET /v1/forecasts` liefert die Prognose je Film, `GET /v1/forecasts/total` die
  Summe über alle Filme pro Intervall. Die gröbere Ebene braucht die Kapazitätsplanung am meisten, denn die
  Server tragen die Gesamtlast. Sie kommt zudem ohne Blättern aus: 96 Werte statt 96.000.
- **Weitere sinnvolle Ebenen** (noch nicht umgesetzt): die Top-10-Filme nach erwarteter Last und eine Summe
  je Genre, sobald die Metadaten angebunden sind.
- **Werkzeuge:** FastAPI, Pydantic, Uvicorn. Die Doku entsteht automatisch unter `/docs`.

## Deployment

Stream-Leser und API laufen als eigene Docker-Container. Import, Training und Prognose-Job startet Airflow,
das ebenfalls in Containern läuft.

**Weg einer Änderung:**

1. Änderung als Pull Request auf GitHub.
2. GitHub Actions prüft automatisch: Linter (ruff), Tests (pytest), Docker-Image bauen und kurz starten.
3. Nach dem Merge auf `main`: Image mit der Commit-ID als Namen in eine Registry hochladen.
4. Auf dem Server das neue Image starten. Gibt es Probleme, wieder das vorherige Image starten (Rollback).

**Betrieb:** Start mit Docker Compose auf einem Server (Cloud oder On-Premise-Linux-VM). Braucht die API mehr
Ausfallsicherheit, ist der nächste Schritt Kubernetes mit zwei API-Instanzen.

**Sicher ändern:**

- Code und Datenaufbereitung: nur per Pull Request mit grünen Tests.
- Neues Modell: Es muss auf vergangenen Daten besser abschneiden als das aktuelle. Die alte Version bleibt
  gespeichert und lässt sich zurückholen.
- API: Bestehende Felder werden nicht geändert, Neues kommt nur dazu. Ein Test prüft, dass die Antwort
  weiterhin dieselben Felder hat.

## Was passiert, wenn etwas ausfällt?

| Was fällt aus | Folge | Was hilft |
| --- | --- | --- |
| Stream-Leser stürzt ab | Keine neuen Echtzeitdaten | Kafka hebt die Nachrichten auf. Nach dem Neustart liest der Stream-Leser ab seiner letzten Position (Offset) weiter. |
| Prognose-Job fällt aus | Keine neue Prognose | Die API liefert die letzte weiter, markiert als veraltet. Ein Alarm geht los. |
| Täglicher Import kommt nicht | Historie unvollständig | Alarm. Bis dahin überbrücken die Echtzeitdaten. |
| Datenbank nicht erreichbar | API hat keine Daten | Die API antwortet mit Fehler 503 statt mit falschen Zahlen. |
| Neues Modell ist schlechter | Prognosen werden ungenauer | Vorherige Modellversion wieder aktivieren. |

Überwacht werden drei Dinge: wie alt die neueste Prognose ist, wie oft die API Fehler liefert und wie weit die
Prognose von den echten Zahlen abweicht.
