# The Shelf Report — Kesari Foods

A competitive-shelf analysis service for Indian biscuit/snack products. Ingests
product data from [Open Food Facts](https://world.openfoodfacts.org/), stores it
in a normalized SQLite database, and answers three shelf-analysis questions for
Priya's October launch.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your GEMINI_API_KEY
```

## Usage

```bash
# Ingest data from Open Food Facts (idempotent — safe to run multiple times)
python -m src.ingest

# Print Priya's three answers
python -m src.queries

# Interactive English follow-ups
python -m src.chat
```

## Tests

```bash
pytest tests/ -v
```

## Project Structure

```
src/
├── config.py          # Constants: API URL, categories, DB path
├── schema.sql         # SQLite DDL (products + product_categories)
├── api_client.py      # Open Food Facts API client with retry/backoff
├── loader.py          # Idempotent database loader (upsert on barcode)
├── ingest.py          # Orchestrator: fetch → load for all categories
├── queries.py         # Priya's three analytical queries
└── chat.py            # Natural-language query interface (Gemini)
tests/
├── test_idempotency.py
├── test_answers.py
├── test_evals.py
└── test_guardrail.py
REVIEW.md              # Agency defect analysis (Task A)
NOTES.md               # Where AI got it wrong (Task D)
```

## Data Source

[Open Food Facts](https://world.openfoodfacts.org/) — a public, crowd-sourced
database of food products. Scoped to India, covering: biscuits, cookies,
salty-snacks, chips-and-fries, and chocolates.