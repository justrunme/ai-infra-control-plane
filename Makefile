PYTHON ?= python3.12

.PHONY: venv test lint docker-build helm-template

venv:
	$(PYTHON) -m venv .venv
	. .venv/bin/activate && pip install -r apps/control-api/requirements.txt

test:
	. .venv/bin/activate && cd apps/control-api && PYTHONPATH=. pytest

lint:
	$(PYTHON) -m compileall apps/control-api/app apps/control-api/tests forecasting/timesfm experiments/inference-autoscaling observability/otel-genai governance/cost governance/approval governance/risk

docker-build:
	docker build -t ai-infra-control-plane:local apps/control-api

helm-template:
	helm template ai-control-plane infra/helm/ai-control-plane
