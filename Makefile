.PHONY: test check build-solver

build-solver:
	cd solver && cargo build --release

test:
	uv run pytest -v

check:
	uv run python -m py_compile engine.py
