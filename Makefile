# TTS Lab Development Commands
# Uses uv for package management (already in project)

.PHONY: help install dev test test-cov test-parallel lint format typecheck security pre-commit check clean

help:
	@echo "TTS Lab - Development Commands"
	@echo "================================"
	@echo "  make install        - Install project dependencies"
	@echo "  make dev            - Install dev dependencies (all extras)"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage"
	@echo "  make test-parallel  - Run tests in parallel (pytest-xdist)"
	@echo "  make lint           - Run ruff linter"
	@echo "  make format         - Format code with ruff"
	@echo "  make typecheck      - Run mypy type checker"
	@echo "  make security       - Run security checks (bandit, safety, pip-audit)"
	@echo "  make pre-commit     - Run pre-commit hooks on all files"
	@echo "  make check          - Run lint + typecheck + security"
	@echo "  make clean          - Clean artifacts"

install:
	uv sync

dev:
	uv sync --all-extras

test:
	pytest

test-cov:
	pytest --cov=tts_lab --cov-report=term-missing --cov-report=html

test-parallel:
	pytest -n auto

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy src/

security:
	bandit -r src/ -f json || true
	safety check --json || true
	pip-audit --format=json || true

pre-commit:
	pre-commit run --all-files

check: lint typecheck security
	pytest --cov=tts_lab

clean:
	rm -rf .pytest_cache
	rm -rf .coverage htmlcov
	rm -rf src/*.egg-info
	rm -rf .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
