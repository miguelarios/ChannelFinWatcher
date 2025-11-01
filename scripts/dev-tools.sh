#!/bin/bash
# Development tooling script for ChannelFinWatcher
# Run via: docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh <command>

set -e

COMMAND=${1:-help}

case $COMMAND in
  "format-python")
    echo "🐍 Formatting Python code with Black..."
    black /app --check --diff
    echo "✅ Formatting complete"
    ;;
    
  "format-python-fix")
    echo "🐍 Auto-fixing Python code formatting..."
    black /app
    echo "📦 Sorting imports with isort..."
    isort /app
    echo "✅ Python formatting complete"
    ;;
    
  "lint-python")
    echo "🔍 Linting Python code with Flake8..."
    flake8 /app
    echo "✅ Python linting complete"
    ;;
    
  "format-frontend")
    echo "🎨 Checking frontend formatting..."
    cd /app && npm run format:check
    echo "✅ Frontend formatting check complete"
    ;;
    
  "format-frontend-fix")
    echo "🎨 Auto-fixing frontend formatting..."
    cd /app && npm run format
    echo "✅ Frontend formatting complete"
    ;;
    
  "lint-frontend")
    echo "🔍 Linting frontend code..."
    cd /app && npm run lint
    echo "✅ Frontend linting complete"
    ;;
    
  "lint-frontend-fix")
    echo "🔧 Auto-fixing frontend linting issues..."
    cd /app && npm run lint:fix
    echo "✅ Frontend linting fixes complete"
    ;;
    
  "check-all")
    echo "🚀 Running all code quality checks..."
    echo "🐍 Python formatting check..."
    black /app --check --diff
    echo "🔍 Python linting..."
    flake8 /app
    echo "✅ All checks passed!"
    ;;
    
  "fix-all")
    echo "🛠️  Auto-fixing all code quality issues..."
    echo "🐍 Fixing Python formatting..."
    black /app
    isort /app
    echo "✅ All fixes applied!"
    ;;
    
  "help"|*)
    echo "ChannelFinWatcher Development Tools"
    echo "====================================="
    echo ""
    echo "Python Commands:"
    echo "  format-python      - Check Python code formatting"
    echo "  format-python-fix  - Auto-fix Python formatting and imports"
    echo "  lint-python        - Lint Python code with Flake8"
    echo ""
    echo "Frontend Commands (run from frontend container):"
    echo "  format-frontend     - Check frontend formatting"
    echo "  format-frontend-fix - Auto-fix frontend formatting"
    echo "  lint-frontend       - Lint frontend code"
    echo "  lint-frontend-fix   - Auto-fix frontend linting issues"
    echo ""
    echo "Combined Commands:"
    echo "  check-all          - Run all quality checks"
    echo "  fix-all            - Auto-fix all issues (Python only)"
    echo ""
    echo "Usage Examples:"
    echo "  docker compose -f docker-compose.dev.yml exec backend /app/scripts/dev-tools.sh format-python-fix"
    echo "  docker compose -f docker-compose.dev.yml exec frontend /app/scripts/dev-tools.sh lint-frontend"
    ;;
esac