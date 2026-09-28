.PHONY: doctor test run verify-local

PORT ?= 8080

doctor:
	@python3 -B scripts/doctor.py

test:
	@python3 -B -m unittest discover -s tests -v

run:
	@python3 -B -m app.server --port $(PORT)

verify-local:
	@python3 -B -m scripts.verify_local
