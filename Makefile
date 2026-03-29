PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: setup lint typecheck test smoke baseline loop-once dashboard ingest

setup:
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check src tests scripts

typecheck:
	$(PYTHON) -m mypy src

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $(PYTHON) -m pytest

smoke:
	$(PYTHON) -m prosperity.cli audit

baseline:
	$(PYTHON) -m prosperity.cli baselines run legacy_newalgo --dataset submission

loop-once:
	$(PYTHON) -m prosperity.cli loop once

dashboard:
	$(PYTHON) -m prosperity.cli dashboard serve

ingest:
	$(PYTHON) scripts/import_sources.py
