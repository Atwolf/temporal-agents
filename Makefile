.PHONY: help install seed temporal worker ui run clean db-reset

PYTHON ?= python

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

install: ## Install all dependencies
	pip install -e ".[ui,dev]"

seed: ## Seed the agent definitions DB with demo configs
	$(PYTHON) -m temporal_agents.db.seed

db-reset: ## Delete and re-seed both databases
	rm -f temporal_agents.db agent_definitions.db
	$(MAKE) seed

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------

temporal: ## Start local Temporal dev server (in-memory)
	@echo "Starting Temporal dev server at localhost:7233 ..."
	@echo "Web UI: http://localhost:8233"
	temporal server start-dev

worker: ## Start the Temporal worker
	$(PYTHON) -m temporal_agents.worker

ui: ## Start the LangGraph Agent Chat UI (localhost:2024)
	@echo "Starting LangGraph dev server + Agent Chat UI ..."
	@echo "Chat UI will be available at the URL printed below"
	langgraph dev

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

run: ## Run a workflow via CLI (usage: make run TASK="your task here")
	$(PYTHON) -m temporal_agents.main $(TASK)

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

test: ## Run tests
	pytest tests/ -v

clean: ## Remove generated files
	rm -f temporal_agents.db agent_definitions.db
	rm -rf __pycache__ src/**/__pycache__ .pytest_cache
	find /tmp/temporal_agents_flaky -delete 2>/dev/null || true
