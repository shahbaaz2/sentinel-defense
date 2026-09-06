.PHONY: bootstrap dev-up dev-down api dashboard missionnet missionnet-console mlx test lint scenario health reset-lab offline-check migrate-missionnet

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

scenario:
	$(VENV)/python -m services.scenario_controller.cli start $(ID)

health:
	bash scripts/healthcheck.sh

reset-lab:
	bash scripts/reset-lab.sh

migrate-missionnet:
	$(VENV)/alembic -c infrastructure/migrations/missionnet/alembic.ini upgrade head

offline-check:
	bash scripts/offline-check.sh
