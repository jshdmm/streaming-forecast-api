install:
	pip install -r requirements-dev.txt

test:
	ruff check .
	pytest

run:
	uvicorn app.main:app --reload

docker:
	docker compose up --build
