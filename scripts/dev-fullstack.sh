#!/bin/bash

# Full-stack development script
# Starts backend, waits for it to be ready, generates frontend client, then starts frontend

set -e

# Environment configuration
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export VITE_API_URL="${VITE_API_URL:-http://localhost:$BACKEND_PORT}"
export FRONTEND_PORT="${FRONTEND_PORT:-5173}"
export FRONTEND_URL="${FRONTEND_URL:-http://localhost:$FRONTEND_PORT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to cleanup background processes
cleanup() {
    if [ ! -z "$BACKEND_PID" ]; then
        print_step "Stopping backend server (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$WATCHER_PID" ]; then
        print_step "Stopping OpenAPI watcher (PID: $WATCHER_PID)..."
        kill $WATCHER_PID 2>/dev/null || true
    fi
    exit 0
}

# Set up trap to cleanup on exit
trap cleanup EXIT INT TERM

print_step "🚀 Starting full-stack development environment..."

# Step 0: Clean up generated files for fresh start
print_step "0. Cleaning up generated files..."
print_step "🧹 Removing backend generated files..."
rm -f backend/openapi*.json
print_step "🧹 Removing frontend generated client..."
rm -rf frontend/src/services/generated
print_step "🧹 Removing frontend build artifacts..."
rm -rf frontend/dist frontend/node_modules/.vite
print_success "Clean up complete - fresh start ready"

# Step 1: Start backend server in background
print_step "1. Starting backend server..."
cd backend
poetry run uvicorn trading_api.main:app --reload --host 0.0.0.0 --port $BACKEND_PORT &
BACKEND_PID=$!
cd ..

print_step "Backend started with PID: $BACKEND_PID"

# Step 2: Wait for backend to be ready
print_step "2. Waiting for backend to be ready..."
timeout=60
while [ $timeout -gt 0 ]; do
    if curl -f http://localhost:$BACKEND_PORT/api/v1/health >/dev/null 2>&1; then
        print_success "Backend is ready and responding"
        break
    fi
    echo "⏳ Waiting for backend ($timeout seconds remaining)..."
    sleep 2
    timeout=$((timeout - 2))
done

if [ $timeout -eq 0 ]; then
    print_error "Backend failed to start within 60 seconds"
    exit 1
fi

# Step 3: Generate frontend client
print_step "3. Generating frontend client from live API..."
cd frontend
if npm run client:generate; then
    print_success "Frontend client generated successfully"
else
    print_error "Client generation failed"
    exit 1
fi
cd ..

# Step 4: Start frontend development server with OpenAPI file watching
print_step "4. Setting up OpenAPI file watching..."

# Define the OpenAPI file path
OPENAPI_FILE="backend/openapi.json"

# Generate initial client
print_step "Generating initial frontend client..."
cd frontend
if npm run client:generate >/dev/null 2>&1; then
    print_success "Initial client generated successfully"
else
    print_warning "Initial client generation failed, continuing..."
fi
cd ..

# Get initial file modification time
if [ -f "$OPENAPI_FILE" ]; then
    INITIAL_MTIME=$(stat -c %Y "$OPENAPI_FILE" 2>/dev/null || echo "0")
    print_success "Watching OpenAPI file: $OPENAPI_FILE"
else
    INITIAL_MTIME="0"
    print_warning "OpenAPI file not found, will watch for creation"
fi

# Start file watcher in background
{
    print_step "Starting OpenAPI file watcher..."
    LAST_MTIME="$INITIAL_MTIME"

    while true; do
        sleep 2  # Check every 2 seconds (much less frequent than server polling)

        if [ -f "$OPENAPI_FILE" ]; then
            CURRENT_MTIME=$(stat -c %Y "$OPENAPI_FILE" 2>/dev/null || echo "0")

            if [ "$CURRENT_MTIME" != "$LAST_MTIME" ] && [ "$CURRENT_MTIME" != "0" ]; then
                print_warning "OpenAPI file changed! Regenerating client..."
                cd frontend
                if npm run client:generate >/dev/null 2>&1; then
                    print_success "Frontend client regenerated successfully"
                else
                    print_error "Failed to regenerate client"
                fi
                cd ..
                LAST_MTIME="$CURRENT_MTIME"
            fi
        fi
    done
} &
WATCHER_PID=$!

print_step "5. Starting frontend development server..."
print_step "🌐 Frontend will be available at: $FRONTEND_URL"
print_step "🔧 Backend API is running at: $VITE_API_URL"
print_step "👁️  OpenAPI file watcher is active"
print_step "📄 Watching: backend/openapi.json for changes"
print_step ""
print_warning "Press Ctrl+C to stop all servers and watchers"
print_step ""

cd frontend
npm run dev