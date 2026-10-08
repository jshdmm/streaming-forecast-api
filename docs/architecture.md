# Architektur (C4-Modell)

Drei Ebenen nach [c4model.com](https://c4model.com/), von grob nach fein:
**Context** (Wer nutzt das System?), **Container** (Welche laufenden Teile gibt es?),
**Component** (Wie ist die API aufgebaut?).

**Stand der Umsetzung:** Gebaut ist die API mit Dummydaten. Airflow-DAGs sind Skizzen
(nur `print`), die PostgreSQL-Datenbank gibt es noch nicht. Solche Teile sind im Text
mit *(geplant)* oder *(Skizze)* gekennzeichnet. Die Diagramme zeigen den Zielzustand.

## Notation

Farbe und Form sind nicht Dekoration, sondern tragen Bedeutung.

**Farbe = Zuständigkeit.** 
**Blauton = Ebene.** 

| Form | Bedeutung | Beispiel hier |
| --- | --- | --- |
| Rechteck mit rundem Kopf | Person | Kapazitätsplanung |
| Rechteck | System, Container oder Komponente | Forecast API |
| Zylinder | Datenspeicher | PostgreSQL, Nutzungs-Datenbank |
| Liegendes Rechteck mit Rundungen | Warteschlange oder Datenstrom | Kafka |
| Gestrichelter Rahmen | Grenze, kein eigenes Bauteil | „Streaming Forecast", „Streaming-Anbieter (Kunde)" |



## Ebene 1: System Context

Das System im Umfeld: Wer benutzt es, und von welchen fremden Systemen hängt es ab?

```mermaid
C4Context
    title System Context: Streaming Forecast

    Person(planer, "Kapazitätsplanung", "Plant Server und Bandbreite")
    System(forecast, "Streaming Forecast", "Prognose der Abrufe von 1.000 Filmen für die nächsten 24 Stunden")

    Enterprise_Boundary(kunde, "Streaming-Anbieter (Kunde)") {
        SystemDb_Ext(usage, "Nutzungs-Datenbank", "Tatsächliche Abrufe, täglich aktualisiert")
        SystemDb_Ext(meta, "Metadaten-Datenbank", "Genre, Release, Film-Stammdaten")
        SystemQueue_Ext(stream, "Datenstrom", "Kafka: Film-Starts in Echtzeit")
    }

    Rel(planer, forecast, "Ruft Prognosen ab", "HTTPS")
    Rel(forecast, usage, "Liest täglich", "SQL")
    Rel(forecast, meta, "Liest täglich", "SQL")
    Rel(forecast, stream, "Liest laufend", "Kafka")

    %% Beschriftungen von den Linien wegschieben, damit sie sich nicht überlagern
    UpdateRelStyle(planer, forecast, $offsetX="-25", $offsetY="-35")
    UpdateRelStyle(forecast, usage, $offsetX="-60", $offsetY="-2")
    UpdateRelStyle(forecast, meta, $offsetX="2", $offsetY="2")
    UpdateRelStyle(forecast, stream, $offsetX="-5", $offsetY="-2")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

| Element | Bedeutung |
| --- | --- |
| Kapazitätsplanung | Hauptnutzer. Plant Serverkapazitäten und braucht dafür vor allem die Summe über alle Filme *(geplant)*. |
| Streaming Forecast | Unser System, das hier gebaut wird. |
| Nutzungs-Datenbank | Historie der tatsächlichen Abrufe. Wird einmal täglich aktualisiert, wir lesen nur. |
| Metadaten-Datenbank | Film-Stammdaten wie Genre und Release. Wir lesen nur. |
| Datenstrom | Kafka-Strom der Film-Starts. Schließt die Lücke zwischen zwei täglichen Importen. |

Die drei Quellen gehören dem Kunden. Der gestrichelte Rahmen fasst sie als fremde Organisation zusammen:
Wir lesen dort nur und können nichts daran ändern.

## Ebene 2: Container

Die Bausteine innerhalb des Systems. „Container“ meint hier einen eigenständig laufenden Teil
(Anwendung oder Datenspeicher), nicht zwingend einen Docker-Container.

```mermaid
C4Container
    title Container: Streaming Forecast

    Person(planer, "Kapazitätsplanung", "Ruft Prognosen ab")
    System_Ext(kunde, "Datenquellen des Kunden", "Nutzungs-DB, Metadaten-DB, Kafka")

    System_Boundary(sys, "Streaming Forecast") {
        Container(api, "Forecast API", "Python, FastAPI", "Liefert die neueste Prognose aus. Rechnet nichts selbst.")
        ContainerDb(db, "Datenbank", "PostgreSQL (geplant)", "film, usage_15min, forecast")
        Container(predict, "Prognose-Job", "Python (Skizze)", "Rechnet alle 15 Minuten 96.000 Werte. Modellierung nicht Teil der Challenge.")
        Container(importjob, "Import-Job", "Python (Skizze)", "Holt täglich Historie und Metadaten.")
        Container(airflow, "Airflow", "Apache Airflow", "Startet die Jobs nach Zeitplan und meldet Fehlschläge.")
        Container(streamer, "Stream-Leser", "Python (geplant)", "Zählt laufende Starts je 15-Minuten-Intervall.")
    }

    Rel(planer, api, "Ruft ab", "HTTPS")
    Rel(api, db, "Liest", "SQL")
    Rel(predict, db, "Liest + schreibt", "SQL")
    Rel(importjob, db, "Schreibt", "SQL")
    Rel(importjob, kunde, "Liest täglich", "SQL")
    Rel(airflow, importjob, "Startet täglich")
    Rel(airflow, predict, "Startet alle 15 Min")
    Rel(streamer, kunde, "Liest laufend", "Kafka")
    Rel(streamer, db, "Schreibt", "SQL")

    %% Beschriftungen verschieben: negativ = links/oben, positiv = rechts/unten (Pixel)
    UpdateRelStyle(planer, api, $offsetX="9", $offsetY="-30")
    UpdateRelStyle(api, db, $offsetX="-10", $offsetY="-30")
    UpdateRelStyle(predict, db, $offsetX="-35", $offsetY="11")
    UpdateRelStyle(importjob, db, $offsetX="-5", $offsetY="0")
    UpdateRelStyle(importjob, kunde, $offsetX="-10", $offsetY="-25")
    UpdateRelStyle(airflow, importjob, $offsetX="-30", $offsetY="10")
    UpdateRelStyle(airflow, predict, $offsetX="-150", $offsetY="15")
    UpdateRelStyle(streamer, kunde, $offsetX="35", $offsetY="-30")
    UpdateRelStyle(streamer, db, $offsetX="-20", $offsetY="12")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

| Container | Aufgabe | Wichtige Entscheidung |
| --- | --- | --- |
| Forecast API | Nimmt Anfragen an, liest die neueste Prognose, liefert JSON. Meldet über `stale`, wenn sie älter als 30 Minuten ist. | Die API **liest nur**. Dadurch ist sie schnell und liefert auch dann den letzten Stand, wenn der Job ausfällt. |
| Airflow | Startet Import und Prognose nach Zeitplan, wiederholt fehlgeschlagene Tasks und meldet Probleme. | Airflow **orchestriert nur**. Die Arbeit und alle Datenbankzugriffe erledigen die Jobs selbst. |
| Import-Job | `daily_import`: kopiert Historie und Metadaten (idempotent: Tag löschen, neu einfügen) und prüft die Datenqualität. | Idempotent, damit ein Retry nichts doppelt schreibt. |
| Stream-Leser | Liest den Kafka-Strom laufend und zählt die Starts je Film und 15-Minuten-Intervall in `usage_15min`. | Läuft **dauerhaft**, nicht nach Zeitplan, deshalb kein Airflow-Job. Schließt die Lücke zwischen zwei täglichen Importen. |
| Prognose-Job | Liest die Features aus `usage_15min` und schreibt 96 Intervalle × 1.000 Filme nach `forecast`. | **Blackbox:** Wie das Modell rechnet, ist laut Challenge nicht Teil der Aufgabe. Für die Architektur zählt nur, dass dieser Job die Tabelle `forecast` füllt. Der Lauf wird in **einer Transaktion** geschrieben. |
| Datenbank | Gemeinsamer Speicher. Jobs schreiben, die API liest. | Entkoppelt Rechnen und Ausliefern. Bis zur Einführung ersetzt `dummy_data.py` die Datenbank. |

### Datenfluss

1. **Laufend:** Der Stream-Leser zählt die Kafka-Ereignisse je Film und 15-Minuten-Intervall und schreibt sie nach `usage_15min`.
2. **Täglich 6:00 UTC:** Airflow startet den Import-Job. Er kopiert die Abrufe von gestern, korrigiert damit die gezählten Werte des Streams, kopiert die Metadaten und prüft, ob für jeden Film alle 96 Intervalle da sind.
3. **Alle 15 Minuten:** Airflow startet den Prognose-Job. Er baut die Features aus `usage_15min` und schreibt 96.000 Werte in die Tabelle `forecast` — in **einer Transaktion**, damit die API entweder den ganzen neuen oder noch den alten Lauf sieht.
4. **Bei jeder Anfrage:** Die API liest den Lauf mit dem größten `generated_at` und gibt ihn seitenweise aus.

Die Prognosen fließen **nicht durch Airflow hindurch**: Airflow startet den Job, und der Job schreibt
selbst in die Datenbank. Das ist bei Airflow wichtig, weil die Daten sonst über XCom liefen, was für
96.000 Werte der falsche Weg wäre.

### Was hier bewusst fehlt

Das Training des Modells und eine Modell-Registry (z. B. MLflow) sind **nicht eingezeichnet**. Die Challenge
nennt die Modellierung ausdrücklich nicht als Teil der Aufgabe. Der Prognose-Job bleibt trotzdem stehen,
weil ohne ihn niemand die Tabelle `forecast` füllt und die API keine Datenquelle hätte. Er ist eine
Blackbox: Dass er rechnet, ist relevant, wie er rechnet, nicht. `docs/KONZEPT.md` beschreibt den ML-Teil
als Ausblick.

## Ebene 3: Component (Forecast API)

Der Aufbau der API aus Dateien und Rollen.

```mermaid
C4Component
    title Component: Forecast API

    Person(planer, "Kapazitätsplanung", "Ruft Prognosen ab")
    ContainerDb(db, "Datenbank", "PostgreSQL (geplant)", "Neueste Prognose")

    Container_Boundary(api, "Forecast API") {
        Component(schemas, "Schemas", "app/schemas.py, Pydantic", "Form und Regeln der Antwort. Erzeugt JSON und /docs.")
        Component(endpoints, "Endpunkte", "app/main.py, FastAPI", "/v1/forecasts und /health. Prüft Parameter, bildet Seiten, setzt stale.")
        Component(data, "Datenzugriff", "app/dummy_data.py", "Liefert die Prognosewerte. Heute Dummydaten, später SQL.")
    }

    Rel(planer, endpoints, "Ruft ab", "HTTPS")
    Rel(endpoints, schemas, "Baut Antwort")
    Rel(endpoints, data, "Holt Werte")
    Rel(data, db, "Liest", "SQL")

    %% Beschriftungen verschieben: negativ = links/oben, positiv = rechts/unten (Pixel)
    UpdateRelStyle(planer, endpoints, $offsetX="-15", $offsetY="-50")
    UpdateRelStyle(endpoints, schemas, $offsetX="-30", $offsetY="8")
    UpdateRelStyle(endpoints, data, $offsetX="-30", $offsetY="8")
    UpdateRelStyle(data, db, $offsetX="45", $offsetY="-25")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

| Komponente | Datei | Verantwortung |
| --- | --- | --- |
| Endpunkte | `app/main.py` | Eingabe prüfen (422 bei falschen Parametern, 404 bei unbekanntem Film), Seiten bilden, `stale` berechnen. |
| Schemas | `app/schemas.py` | Form und Regeln der Antwort, z. B. `predicted_streams >= 0`. |
| Datenzugriff | `app/dummy_data.py` | Einzige Stelle, die Daten liefert. Wird bei der Datenbank-Einführung ausgetauscht, ohne die Endpunkte zu ändern. |

## Ergänzung: Auslieferung (CI/CD)

Kein Teil der C4-Ebenen, aber für das Verständnis nützlich: Wie kommt der Code zum Image?

```mermaid
flowchart LR
    dev["Entwickler:in<br/>Pull Request / Push"] --> gha["GitHub Actions<br/>ruff, pytest"]
    gha --> build["Image bauen<br/>und /health prüfen"]
    build -->|nur auf main| reg[("ghcr.io<br/>Container Registry")]
    reg -.->|geplant| run["Laufzeit-Umgebung<br/>z. B. AWS"]
```

Bei jedem Pull Request laufen Linter und Tests, danach wird das Image gebaut und per `curl` auf
`/health` geprüft. Nur auf `main` wird das Image mit dem Commit-Hash als Tag hochgeladen.


