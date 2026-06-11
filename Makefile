# ENCORE reproducibility targets (guide Section 11, Phase 6).
# Windows: run via git-bash/WSL, or call the python entry points directly.
PY ?= python

.PHONY: figures figures-fast test

figures:            ## regenerate every Phase-6 figure/table + provenance manifest
	$(PY) experiments/make_figures.py

figures-fast:       ## same, skipping the ~35-min 20-seed main-table run
	$(PY) experiments/make_figures.py --skip-table

test:
	$(PY) -m pytest tests -q
