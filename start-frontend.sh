#!/bin/bash
# Starts the React frontend on http://localhost:5174.  Usage:  bash start-frontend.sh
cd "$(dirname "$0")/frontend" || exit 1
[ -d node_modules ] || npm install
exec npm run dev
