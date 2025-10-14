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

# Function to check if a process is running
is_process_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    kill -0 "$pid" 2>/dev/null
}

# Function to cleanup background processes
cleanup() {
    print_step "🛑 Shutting down full-stack development environment..."

    if [ ! -z "$FRONTEND_PID" ] && is_process_running "$FRONTEND_PID"; then
        print_step "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill -TERM $FRONTEND_PID 2>/dev/null || true
        # Wait a bit for graceful shutdown
        sleep 2
        # Force kill if still running
        if is_process_running "$FRONTEND_PID"; then
            kill -KILL $FRONTEND_PID 2>/dev/null || true
        fi
    fi

    if [ ! -z "$BACKEND_PID" ] && is_process_running "$BACKEND_PID"; then
        print_step "Stopping backend server (PID: $BACKEND_PID)..."
        kill -TERM $BACKEND_PID 2>/dev/null || true
        # Wait a bit for graceful shutdown
        sleep 2
        # Force kill if still running
        if is_process_running "$BACKEND_PID"; then
            kill -KILL $BACKEND_PID 2>/dev/null || true
        fi
    fi

    if [ ! -z "$WS_WATCHER_PID" ] && is_process_running "$WS_WATCHER_PID"; then
        print_step "Stopping WebSocket router watcher (PID: $WS_WATCHER_PID)..."
        kill -TERM $WS_WATCHER_PID 2>/dev/null || true
        sleep 1
        if is_process_running "$WS_WATCHER_PID"; then
            kill -KILL $WS_WATCHER_PID 2>/dev/null || true
        fi
    fi

    if [ ! -z "$WATCHER_PID" ] && is_process_running "$WATCHER_PID"; then
        print_step "Stopping OpenAPI watcher (PID: $WATCHER_PID)..."
        kill -TERM $WATCHER_PID 2>/dev/null || true
        # Wait a bit for graceful shutdown
        sleep 1
        # Force kill if still running
        if is_process_running "$WATCHER_PID"; then
            kill -KILL $WATCHER_PID 2>/dev/null || true
        fi
    fi

    print_success "All processes stopped. Environment cleaned up."
    exit 0
}

# Set up trap to cleanup on exit
trap cleanup EXIT INT TERM

# Global variables for process IDs
BACKEND_PID=""
FRONTEND_PID=""
WATCHER_PID=""
WS_WATCHER_PID=""

print_step "🚀 Starting full-stack development environment..."

# Step 0: Clean up generated files for fresh start
print_step "0. Cleaning up generated files..."
print_step "🧹 Removing backend generated files..."
rm -f backend/openapi*.json
print_step "🧹 Removing frontend generated client..."
rm -rf frontend/src/clients/trader-client-generated
print_step "🧹 Removing frontend build artifacts..."
rm -rf frontend/dist frontend/node_modules/.vite
print_success "Clean up complete - fresh start ready"

# Step 0.5: Generate WebSocket routers initially
print_step "0.5. Generating WebSocket routers..."
cd backend
if ./scripts/generate-ws-routers.sh >/dev/null 2>&1; then
    print_success "WebSocket routers generated"
else
    print_warning "WebSocket router generation failed, continuing..."
fi
cd ..

# Step 1: Start backend server in background
print_step "1. Starting backend server..."
cd backend
make dev &
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
if make client-generate; then
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
if make client-generate >/dev/null 2>&1; then
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
                if make client-generate >/dev/null 2>&1; then
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

# Step 4.5: Start WebSocket router watcher
print_step "4.5. Starting WebSocket router watcher..."
cd backend
./scripts/watch-ws-routers.sh &
WS_WATCHER_PID=$!
cd ..
print_success "WebSocket router watcher active (PID: $WS_WATCHER_PID)"

print_step "5. Starting frontend development server..."
print_step "🌐 Frontend will be available at: $FRONTEND_URL"
print_step "🔧 Backend API is running at: $VITE_API_URL"
print_step "👁️  OpenAPI file watcher is active"
print_step "📄 Watching: backend/openapi.json for changes"
print_step "🔄 WebSocket router watcher is active"
print_step "📂 Watching: backend/src/trading_api/ws/*.py for changes"
print_step ""
print_warning "Press Ctrl+C to stop all servers and watchers"
print_step ""

# Start frontend in background and capture PID
cd frontend
make dev &
FRONTEND_PID=$!
cd ..

print_step "Frontend started with PID: $FRONTEND_PID"

# Wait for frontend process to finish (or be interrupted)
wait $FRONTEND_PID