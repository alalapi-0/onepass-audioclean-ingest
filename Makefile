.PHONY: help test check venv

help:
	@echo "Available targets:"
	@echo "  make test    - Run pytest tests"
	@echo "  make check   - Run check-deps and verify CLI works"
	@echo "  make venv    - Create virtual environment (optional)"

test:
	pytest -q

check:
	@echo "Checking dependencies..."
	@python -m onepass_audioclean_ingest.cli --help > /dev/null 2>&1 || (echo "ERROR: CLI not available. Run 'pip install -e .' first." && exit 1)
	@onepass-ingest check-deps --json > /dev/null 2>&1 || (echo "WARNING: check-deps failed. Install ffmpeg/ffprobe." && exit 1)
	@echo "Check passed"

venv:
	python3 -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

