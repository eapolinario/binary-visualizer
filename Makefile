INPUT ?=
OUTPUT ?= output.ppm
SCALE ?= log

.PHONY: run test lint
run:
	@if [ -z "$(INPUT)" ]; then \
		echo "Usage: make run INPUT=/path/to/binary [OUTPUT=output.ppm SCALE=log]"; \
		exit 1; \
	fi
	uv run visualize.py --scale $(SCALE) -o $(OUTPUT) $(INPUT)

test:
	PYTHONPATH=. uv run --with pytest pytest tests/test_visualize.py

lint:
	uv run ruff check
