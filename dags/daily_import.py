"""Airflow-DAG: Historie und Metadaten einmal täglich vom Kunden in unsere Datenbank kopieren.

Skizze: Die Tasks zeigen, was passieren würde, und geben nur eine Meldung aus.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task


@dag(
    schedule="0 6 * * *",  # jeden Morgen um 6:00 UTC, wenn der Kunde den Vortag fertig hat
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,  # verpasste Tage aus der Vergangenheit nicht automatisch nachholen
    default_args={"retries": 3, "retry_delay": timedelta(minutes=10)},
)
def daily_import():
    @task
    def copy_usage_history():
        # Gestern aus der Nutzungs-DB lesen, auf 15-Minuten-Intervalle zählen und in
        # usage_15min schreiben. Idempotent: erst den Tag löschen, dann neu einfügen,
        # beides in einer Transaktion. Ein Retry schreibt so nichts doppelt.
        print("Kopiere die Abrufe von gestern ...")

    @task
    def copy_metadata():
        print("Kopiere die Film-Metadaten (Genre, Release) ...")

    @task
    def check_data():
        # Sind für jeden Film alle 96 Intervalle da? Keine negativen Werte?
        # Schlägt die Prüfung fehl, schlägt der Task fehl und Airflow meldet es.
        print("Prüfe die Datenqualität ...")

    # Dependencies, Downstream: Erst beide Kopien (parallel), dann die Prüfung
    [copy_usage_history(), copy_metadata()] >> check_data()


daily_import()
