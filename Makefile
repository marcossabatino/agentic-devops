.PHONY: doctor test

doctor:
	@python3 -B scripts/doctor.py

test:
	@python3 -B -m unittest discover -s tests -v
