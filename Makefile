# BaseAgent MCP Development Makefile
# Contains commonly used commands for development

.PHONY: help setup test test-unit test-integration test-coverage test-file format lint run-code-server run-test-server run-agents clean

# Default target executed when no arguments are given to make
default: help

# Show help
help:
	@echo "BaseAgent MCP Development Commands:"
	@echo ""
	@echo "Setup:"
	@echo "  make setup           Install all dependencies using uv"
	@echo "  make setup-dev       Install dev dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test            Run all tests"
	@echo "  make test-unit       Run only unit tests"
	@echo "  make test-integration Run only integration tests"
	@echo "  make test-coverage   Run tests with coverage report"
	@echo "  make test-file FILE=path/to/test_file.py  Run specific test file"
	@echo ""
	@echo "Code Quality:"
	@echo "  make format          Format code with ruff"
	@echo "  make lint            Lint code with ruff"
	@echo ""
	@echo "Run Servers:"
	@echo "  make run-code-server Run the MCP code analysis server"
	@echo "  make run-test-server Run the MCP test runner server"
	@echo ""
	@echo "Run Agents:"
	@echo "  make run-agent       Run the base agent"
	@echo "  make run-integrated  Run the agent with both MCP integrations"
	@echo ""
	@echo "Clean:"
	@echo "  make clean           Remove build, test, coverage and Python artifacts"

# Setup commands
setup:
	@echo "Installing dependencies with uv..."
	uv pip install -r requirements.txt

setup-dev:
	@echo "Installing development dependencies with uv..."
	uv pip install -r requirements.txt pytest pytest-cov ruff httpx

# Test commands
test:
	@echo "Running all tests..."
	./tests/run_tests.py

test-unit:
	@echo "Running unit tests..."
	./tests/run_tests.py tests/unit

test-integration:
	@echo "Running integration tests..."
	./tests/run_tests.py tests/integration

test-file:
	@echo "Running tests in $(FILE)..."
	./tests/run_tests.py $(FILE)

test-coverage:
	@echo "Running tests with coverage..."
	pytest --cov=agents --cov=examples tests/

# Code quality commands
format:
	@echo "Formatting code with ruff..."
	ruff format agents/ examples/ tests/ src/

lint:
	@echo "Linting code with ruff..."
	ruff check agents/ examples/ tests/ src/

# Run server commands
run-code-server:
	@echo "Starting MCP Code Analysis Server..."
	python agents/mcp_code_server.py

run-test-server:
	@echo "Starting MCP Test Runner Server..."
	python agents/mcp_test_server.py

# Run agent commands
run-agent:
	@echo "Running base agent..."
	python agents/agent.py

run-integrated:
	@echo "Running agent with both MCP integrations..."
	python examples/register_mcps.py

# Clean command
clean:
	@echo "Cleaning project..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
	find . -name "*.pyd" -delete
	find . -name ".DS_Store" -delete 