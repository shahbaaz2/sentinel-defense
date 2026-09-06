.PHONY: bootstrap dev-up dev-down api dashboard missionnet missionnet-console mlx test lint health reset-lab offline-check migrate-missionnet migrate-sentinel migrate-democontrol ingest-once ingest-watch sentinel-reset demo-control demo-control-console reset-demo

VENV := .venv/bin

bootstrap:
	bash scripts/bootstrap-mac.sh

dev-up:
	bash scripts/dev-up.sh

dev-down:
	bash scripts/dev-down.sh

api:
	$(VENV)/uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8080 --app-dir .

dashboard:
	cd apps/dashboard && pnpm dev

missionnet:
	$(VENV)/uvicorn apps.missionnet.main:app --reload --host 127.0.0.1 --port 8090 --app-dir .

missionnet-console:
	cd apps/missionnet-console && pnpm dev

demo-control:
	$(VENV)/uvicorn apps.demo_control.main:app --reload --host 127.0.0.1 --port 8100 --app-dir .

demo-control-console:
	cd apps/demo-control-console && pnpm dev

mlx:
	@echo "uv tool install mlx-lm"
	@echo "mlx_lm.server --model mlx-community/Qwen3-4B-Instruct-2507-4bit"

test:
	$(VENV)/pytest -q
	@if [ -f apps/dashboard/package.json ]; then cd apps/dashboard && pnpm test; fi

lint:
	$(VENV)/ruff check .
	$(VENV)/mypy . || true
	@if [ -f apps/dashboard/package.json ]; then cd apps/dashboard && pnpm lint; fi

health:
	bash scripts/healthcheck.sh

reset-lab:
	bash scripts/reset-lab.sh

reset-demo:
	bash scripts/reset-lab.sh
	$(VENV)/python -m apps.demo_control.reset

migrate-missionnet:
	$(VENV)/alembic -c infrastructure/migrations/missionnet/alembic.ini upgrade head

migrate-sentinel:
	$(VENV)/alembic -c infrastructure/migrations/sentinel/alembic.ini upgrade head

migrate-democontrol:
	$(VENV)/alembic -c infrastructure/migrations/demo_control/alembic.ini upgrade head

ingest-once:
	$(VENV)/python -m services.event_ingestor.cli run-once

ingest-watch:
	$(VENV)/python -m services.event_ingestor.cli run-watch

sentinel-reset:
	$(VENV)/python -m services.event_ingestor.reset

offline-check:
	bash scripts/offline-check.sh
