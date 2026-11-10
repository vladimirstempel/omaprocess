.PHONY: test

# Needs python3 and node. Neither suite touches the real /proc or sends a signal.
test:
	PYTHONPATH=lib python3 -m unittest discover -s tests
	node --test tests/
