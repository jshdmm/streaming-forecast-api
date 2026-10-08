# Schlankes Python-Image als Basis
FROM python:3.12-slim

# set container working directory
WORKDIR /app

# Erst nur die Abhängigkeiten: Docker merkt sich (cached) diesen Schritt.
# Ändert sich nur der Code, wird pip install beim nächsten Build übersprungen.
COPY requirements.txt .

# pip cache aus dem build raushalten und requirements installieren
RUN pip install --no-cache-dir -r requirements.txt


COPY app ./app

# Least Privilege: Nicht als root user laufen lassen: Angreifer haben keine root user Reche im Container
RUN useradd --create-home appuser
USER appuser

# listens on port 8000
EXPOSE 8000

# auf allen Netzwerk-Interfaces lauschen, damit der Container von außen erreichbar ist
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
