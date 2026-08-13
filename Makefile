# OpenOncology developer task runner.
# Targets are POSIX-sh friendly (the project uses Git Bash on Windows).
#
# Common:
#   make test            run everything (backend + frontend unit + e2e)
#   make test-backend    pytest (both suites, with coverage gate)
#   make test-frontend   Vitest unit tests
#   make test-e2e        Playwright E2E (boots app in demo mode)
#   make coverage        backend coverage report (term-missing + xml)
#   make lint            ruff (backend) + eslint + tsc (frontend)

.PHONY: help test test-backend test-frontend test-e2e coverage lint lint-backend lint-frontend install

PYTEST := PYTHONPATH=. pytest
COV := --cov=ai --cov=api

help:
	@grep -E '^#   make' Makefile | sed 's/^#   //'

install:
	cd api && pip install -r requirements.txt
	cd web && npm install

# ── Tests ──────────────────────────────────────────────────────────────────────

# The api and ai suites run as separate pytest invocations on purpose: both the
# top-level ai/ package and the app's api/ai/ package claim the import name `ai`,
# so one interpreter can't load both. Coverage is combined via --cov-append.
#
# Keep --cov-fail-under in step with .github/workflows/ci.yml. They disagreed
# (62 here, 63 there), so a local `make test-backend` could pass something CI
# would reject.
test-backend:
	$(PYTEST) api/tests/ $(COV) --cov-report= --cov-fail-under=0
	$(PYTEST) ai/tests/ $(COV) --cov-append --cov-report=term-missing --cov-fail-under=52

test-frontend:
	cd web && npm run test:run

test-e2e:
	cd web && npm run test:e2e

test: test-backend test-frontend test-e2e

coverage:
	$(PYTEST) api/tests/ $(COV) --cov-report= --cov-fail-under=0
	$(PYTEST) ai/tests/ $(COV) --cov-append --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=52

# ── Lint / type-check ──────────────────────────────────────────────────────────

lint: lint-backend lint-frontend

lint-backend:
	cd api && ruff check .

lint-frontend:
	cd web && npx eslint . --ext .ts,.tsx --max-warnings 0 && npx tsc --noEmit
