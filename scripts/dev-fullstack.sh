#!/bin/bash

# Full-stack development script
# Starts backend, waits for it to be ready, generates frontend client, then starts frontend

set -e

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

# Step 1: Start backend server in background
print_step "1. Starting backend server..."
cd backend
poetry run uvicorn trading_api.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

print_step "Backend started with PID: $BACKEND_PID"

# Step 2: Wait for backend to be ready
print_step "2. Waiting for backend to be ready..."
timeout=60
while [ $timeout -gt 0 ]; do
    if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
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

# Step 4: Start frontend development server with OpenAPI watching
print_step "4. Setting up OpenAPI schema watching..."

# Function to generate client and get hash
generate_client_and_hash() {
    cd frontend
    if npm run client:generate >/dev/null 2>&1; then
        cd ..
        # Get hash of the OpenAPI spec
        curl -s http://localhost:8000/openapi.json | sha256sum | cut -d' ' -f1
    else
        cd ..
        echo "error"
    fi
}

# Get initial OpenAPI hash
OPENAPI_HASH=$(generate_client_and_hash)
if [ "$OPENAPI_HASH" = "error" ]; then
    print_error "Failed to get initial OpenAPI hash"
    exit 1
fi

print_success "Initial OpenAPI schema hash: ${OPENAPI_HASH:0:8}..."

# Start OpenAPI watcher in background
{
    print_step "Starting OpenAPI schema watcher..."
    while true; do
        sleep 5  # Check every 5 seconds
        NEW_HASH=$(curl -s http://localhost:8000/openapi.json 2>/dev/null | sha256sum | cut -d' ' -f1 2>/dev/null || echo "error")

        if [ "$NEW_HASH" != "error" ] && [ "$NEW_HASH" != "$OPENAPI_HASH" ]; then
            print_warning "OpenAPI schema changed! Regenerating client..."
            cd frontend
            if npm run client:generate >/dev/null 2>&1; then
                print_success "Frontend client regenerated (hash: ${NEW_HASH:0:8}...)"
                OPENAPI_HASH="$NEW_HASH"
            else
                print_error "Failed to regenerate client"
            fi
            cd ..
        fi
    done
} &
WATCHER_PID=$!

print_step "5. Starting frontend development server..."
print_step "🌐 Frontend will be available at: http://localhost:5173"
print_step "🔧 Backend API is running at: http://localhost:8000"
print_step "👁️  OpenAPI schema watcher is active"
print_step ""
print_warning "Press Ctrl+C to stop all servers and watchers"
print_step ""

cd frontend
npm run dev