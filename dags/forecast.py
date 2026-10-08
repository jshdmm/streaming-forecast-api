"""Airflow-DAG: alle 15 Minuten eine neue Prognose für die nächsten 24 Stunden rechnen.

Skizze: Die Tasks zeigen, was passieren würde, und geben nur eine Meldung aus.

In Echtbetrieb schreibt dieser Job die Prognosewerte selbst in die Tabelle forecast, und die API holt
sie sich von dort. Airflow startet den Job nur, die Daten laufen nicht durch Airflow hindurch.
"""

# packages
from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task  # spart Python Operator Config


@dag(
    schedule="*/15 * * * *",  # alle 15 Minuten: :00, :15, :30, :45 (cron-expression)
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,  # verpasste Läufe nicht nachholen, eine alte Prognose braucht niemand
    max_active_runs=1,  # nie zwei Läufe gleichzeitig
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)}, # 1 retry nach 2 Minuten, falls ein Task fehlschlägt
)
def forecast():
    @task
    def build_features():
        # Aus usage_15min: Abrufe der letzten Stunden, gleiche Uhrzeit gestern
        # und vor einer Woche, Uhrzeit, Wochentag.
        print("Baue Features für 1.000 Filme ...")

    @task
    def predict():
        # Freigegebenes Modell laden und 96 Intervalle x 1.000 Filme vorhersagen.
        print("Rechne 96.000 Prognosewerte ...")

    @task
    def save_forecast():
        # Alle Werte in EINER Transaktion in die Tabelle forecast schreiben:
        # Die API sieht entweder den ganzen neuen Lauf oder noch den alten.
        print("Speichere die Prognose ...")

    # dependencies, downstream: erst Features bauen, dann vorhersagen, dann speichern
    build_features() >> predict() >> save_forecast()


forecast()
