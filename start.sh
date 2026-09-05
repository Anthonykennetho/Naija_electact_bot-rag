#!/bin/bash
# Rebuild the retrieval index from the official Electoral Act when present,
# otherwise use the small synthetic sample for local development.
set -e
if [ -f data/electoral_act_2026.pdf ]; then
	python ingest.py data/electoral_act_2026.pdf "Electoral Act, 2026"
else
	python ingest.py
fi
python bot.py
