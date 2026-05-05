#!/bin/bash
# ============================================================================
# JAYCO Dealer Portal - Local Development Setup
# ============================================================================
set -e

echo "🔧 Setting up JAYCO Dealer Portal development environment..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required but not installed."; exit 1; }

# Create .env from example if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env file from .env.example"
    echo "   Please update .env with your Azure credentials."
fi

# Setup Python backend
echo ""
echo "📦 Setting up FastAPI backend..."
cd src/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..

# Setup React frontend
echo ""
echo "📦 Setting up React frontend..."
cd src/frontend
npm install
cd ../..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the application:"
echo "  1. Backend:  cd src/api && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "  2. Frontend: cd src/frontend && npm run dev"
echo ""
echo "The frontend will be available at http://localhost:5173"
echo "The API docs will be available at http://localhost:8000/docs"
