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

.PHONY: setup run-durable verify-durable
PYTHON_DURABLE ?= .venv/bin/python

setup:
	@python3 -m venv .venv
	@.venv/bin/python -m pip install -r requirements.txt

run-durable:
	@$(PYTHON_DURABLE) -B -m scripts.durable_demo --port $(PORT)

verify-durable:
	@$(PYTHON_DURABLE) -B -m scripts.verify_durable

.PHONY: bootstrap
bootstrap:
	@python3 -B -m scripts.lab_platform bootstrap

.PHONY: infra-init infra-plan infra-apply deploy ui
infra-init infra-plan infra-apply deploy:
	@python3 -B -m scripts.lab_platform $@

ui:
	@python3 -B -m scripts.lab_platform ui --port $(PORT)

.PHONY: verify-cluster
verify-cluster:
	@python3 -B -m scripts.verify_cluster

.PHONY: verify-network
verify-network:
	@python3 -B -m scripts.verify_network

.PHONY: dashboards scenario reset logs verify-observability
DASHBOARD_PORT ?= 3000
CASE ?= healthy

dashboards:
	@python3 -B -m scripts.lab_platform dashboards --port $(DASHBOARD_PORT)

scenario:
	@python3 -B -m scripts.scenario --case $(CASE)

reset:
	@python3 -B -m scripts.scenario --case healthy

logs:
	@python3 -B -m scripts.scenario --logs $(RUN_ID)

verify-observability:
	@python3 -B -m scripts.verify_observability

.PHONY: verify-static
verify-static:
	@python3 -B -m scripts.ci_static
