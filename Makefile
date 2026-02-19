.PHONY: test check

test:
	uv run pytest -v

check:
	uv run python -m py_compile one_shot_solitaire.py one_shot_solitaire_gui.py
