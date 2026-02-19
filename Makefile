.PHONY: test check

test:
	python3 -m unittest -v

check:
	python3 -m py_compile one_shot_solitaire.py one_shot_solitaire_gui.py
