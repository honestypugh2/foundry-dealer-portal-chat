#!/bin/bash
# Stop script for Dealer Portal Application

echo "Stopping Dealer Portal Application..."

# Kill backend on port 8000
fuser -k 8000/tcp 2>/dev/null
echo "Backend stopped"

# Kill frontend on port 5173 (Vite)
fuser -k 5173/tcp 2>/dev/null
echo "Frontend stopped"

# Kill frontend alt port 3000
fuser -k 3000/tcp 2>/dev/null

echo "All services stopped!"
