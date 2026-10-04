.PHONY: help all test lint docs

help: ## Show the targets
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*## /\t/'

all: ## Run the full pipeline from the cache, with the model
	uv run python -m authors_db run --offline --adjudicate

test: ## Run the tests
	uv run pytest

lint: ## Check the code style
	uv run ruff check . && uv run ruff format --check .

docs: ## Check the style of the documents
	uv run python scripts/check_ste.py
