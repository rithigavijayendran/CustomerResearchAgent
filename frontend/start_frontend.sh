#!/bin/bash

echo "========================================"
echo "  Company Research Assistant - Frontend"
echo "========================================"
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Check if .env.local exists
if [ ! -f ".env.local" ]; then
    echo ""
    echo "Creating .env.local file..."
    echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
    echo ".env.local file created!"
fi

echo ""
echo "Starting frontend development server..."
echo "Frontend will be available at: http://localhost:3000"
echo ""
echo "Press CTRL+C to stop the server"
echo ""

npm run dev

