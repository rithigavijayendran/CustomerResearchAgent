#!/bin/bash

echo "========================================"
echo "  Company Research Assistant - Backend"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env file not found!"
    echo "Please create .env file with:"
    echo "  LLM_PROVIDER=gemini"
    echo "  GEMINI_API_KEY=your-api-key"
    echo ""
    read -p "Press enter to continue anyway..."
fi

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Create necessary directories
mkdir -p vector_db
mkdir -p uploads

echo ""
echo "Starting backend server..."
echo "Backend will be available at: http://localhost:8000"
echo "API docs will be available at: http://localhost:8000/docs"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

uvicorn main:app --reload --port 8000

