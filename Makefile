SHELL := /bin/bash
PYTHON ?= python3
BACKEND_DIR := backend
FRONTEND_DIR := frontend
BACKEND_PY := .venv/bin/python
BACKEND_PIP := .venv/bin/pip
BACKEND_UVICORN := .venv/bin/uvicorn

.PHONY: install install-backend install-frontend ensure-backend-env ensure-frontend-deps init-db dev backend frontend worker build clean repair-db repair-processing

install: install-backend install-frontend

ensure-backend-env:
	@test -x $(BACKEND_DIR)/$(BACKEND_PY) || (cd $(BACKEND_DIR) && $(PYTHON) -m venv .venv)
	@test -x $(BACKEND_DIR)/$(BACKEND_PIP) || (echo "Backend venv was not created correctly" && exit 1)

install-backend: ensure-backend-env
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m pip install -r requirements.txt
	@test -f $(BACKEND_DIR)/.env || cp $(BACKEND_DIR)/.env.example $(BACKEND_DIR)/.env

install-frontend:
	cd $(FRONTEND_DIR) && npm install
	@test -f $(FRONTEND_DIR)/.env || cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env

ensure-frontend-deps:
	@test -d $(FRONTEND_DIR)/node_modules || $(MAKE) install-frontend

init-db: install-backend
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.db.init_db

repair-db: install-backend
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.db.init_db

repair-processing: install-backend
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.db.repair_processing

backend: init-db
	cd $(BACKEND_DIR) && $(BACKEND_UVICORN) app.main:app --reload

worker: init-db
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.worker

frontend: ensure-frontend-deps
	cd $(FRONTEND_DIR) && npm run dev

dev: install-backend ensure-frontend-deps init-db
	@echo "Starting backend, worker, and frontend. Press Ctrl+C to stop all."
	@(cd $(BACKEND_DIR) && $(BACKEND_UVICORN) app.main:app --reload) & \
	BACKEND_PID=$$!; \
	(cd $(BACKEND_DIR) && $(BACKEND_PY) -m app.worker) & \
	WORKER_PID=$$!; \
	(cd $(FRONTEND_DIR) && npm run dev) & \
	FRONTEND_PID=$$!; \
	trap 'kill $$BACKEND_PID $$WORKER_PID $$FRONTEND_PID 2>/dev/null' INT TERM EXIT; \
	wait

build: install-backend ensure-frontend-deps
	cd $(FRONTEND_DIR) && npm run build
	cd $(BACKEND_DIR) && $(BACKEND_PY) -m compileall app

clean:
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/node_modules $(BACKEND_DIR)/.venv $(BACKEND_DIR)/__pycache__ $(BACKEND_DIR)/app/**/__pycache__
