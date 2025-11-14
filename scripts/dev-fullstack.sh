#!/bin/bash

# Full-stack development script
# Starts backend, waits for it to be ready, generates frontend client, then starts frontend

set -e

# Create a new process group for this script
# This ensures all child processes belong to the same group
set -o monitor
trap '' SIGTSTP  # Ignore Ctrl+Z

# TODO: refactor to optimize dev / reload flow

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

# Step 0: Check ports availability before doing anything
print_step "0. Checking port availability..."
PORTS_BLOCKED=false

if lsof -Pi :$BACKEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Backend port $BACKEND_PORT is already in use!"
    lsof -Pi :$BACKEND_PORT -sTCP:LISTEN
    PORTS_BLOCKED=true
fi

if lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    print_error "Frontend port $FRONTEND_PORT is already in use!"
    lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN
    PORTS_BLOCKED=true
fi

if [ "$PORTS_BLOCKED" = true ]; then
    print_error ""
    print_error "Cannot start - ports already in use. Stop existing servers first."
    exit 1
fi
print_success "Ports $BACKEND_PORT and $FRONTEND_PORT are available"

# Global variables for process IDs and process group
BACKEND_PID=""
WATCHER_PID=""
FRONTEND_PID=""
SCRIPT_PGID=$$

print_step "🚀 Starting full-stack development environment..."
print_step "   Process Group ID: $SCRIPT_PGID"

# Function to check if a process is running
is_process_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    kill -0 "$pid" 2>/dev/null
}

# Helper function to get all processes in our process group
get_process_group_pids() {
    # Get all PIDs in our process group, excluding the current script
    ps -o pid= -g "$SCRIPT_PGID" 2>/dev/null | grep -v "^[[:space:]]*$$[[:space:]]*$" || true
}

# Helper function to get all descendant PIDs of a given PID (recursive)
get_descendant_pids() {
    local parent_pid=$1
    local pids=""
    
    # Get direct children
    local children=$(pgrep -P "$parent_pid" 2>/dev/null || true)
    
    for child in $children; do
        # Add this child
        pids="$pids $child"
        # Recursively get this child's descendants
        local descendants=$(get_descendant_pids "$child")
        pids="$pids $descendants"
    done
    
    echo "$pids"
}

# Helper function to safely kill a process and all its descendants
kill_process_tree() {
    local pid=$1
    local signal=${2:-TERM}
    
    if [ -z "$pid" ]; then
        return
    fi
    
    # Get all descendant PIDs
    local all_pids=$(get_descendant_pids "$pid")
    all_pids="$all_pids $pid"
    
    # Kill all descendants and the parent
    for p in $all_pids; do
        if is_process_running "$p"; then
            kill -"$signal" "$p" 2>/dev/null || true
        fi
    done
}

# Function to cleanup background processes
cleanup() {
    print_step "🛑 Shutting down full-stack development environment..."

    # Step 1: Kill tracked processes with SIGTERM (graceful)
    # Order: Frontend → Watcher → Backend (dependency order)

    if [ ! -z "$FRONTEND_PID" ]; then
        print_step "Stopping frontend server (PID: $FRONTEND_PID)..."
        kill_process_tree "$FRONTEND_PID" "TERM"
    fi

    if [ ! -z "$WATCHER_PID" ]; then
        print_step "Stopping spec watcher (PID: $WATCHER_PID)..."
        kill_process_tree "$WATCHER_PID" "TERM"
    fi

    if [ ! -z "$BACKEND_PID" ]; then
        print_step "Stopping backend server (PID: $BACKEND_PID)..."
        kill_process_tree "$BACKEND_PID" "TERM"
    fi

    # Step 2: Wait for graceful shutdown
    sleep 1

    # Step 3: Kill remaining process group members
    print_step "Cleaning up any remaining processes..."
    local remaining_pids=$(get_process_group_pids)
    
    if [ ! -z "$remaining_pids" ]; then
        for pid in $remaining_pids; do
            kill -TERM $pid 2>/dev/null || true
        done
        sleep 1
    fi

    # Step 4: Force kill stubborn processes
    remaining_pids=$(get_process_group_pids)
    if [ ! -z "$remaining_pids" ]; then
        for pid in $remaining_pids; do
            kill -KILL $pid 2>/dev/null || true
        done
    fi

    print_success "All processes stopped. Environment cleaned up."
}

# Set up trap to cleanup on exit
trap cleanup EXIT INT TERM

# Step 1: Clean up before starting servers
print_step "1. Preparing environment..."
print_step "   🧹 Cleaning generated files..."
make -C backend clean-generated
make -C frontend clean-generated
print_success "   Environment cleaned"


make -C backend generate

# Step 2: Start backend server in background
print_step "2. Starting backend server..."
make -C backend dev &
BACKEND_PID=$!
print_step "   Backend started with PID: $BACKEND_PID"

RETRY_CTR=0
for ((; RETRY_CTR<30; RETRY_CTR++)); do
    if is_process_running "$BACKEND_PID"; then
        if curl -s "http://localhost:$BACKEND_PORT/api/v1/auth/health" >/dev/null 2>&1; then
            print_success "   Backend is up and running at http://localhost:$BACKEND_PORT"
            break
        else
            print_step "   Waiting for backend to be ready..."
            sleep 1
        fi
    else
        print_error "   Backend process has exited unexpectedly."
        exit 1
    fi
done
if [ $RETRY_CTR -ge 30 ]; then
    print_error "   Backend failed to start within expected time."
    exit 1
fi

make -C frontend generate

print_step "5. Starting frontend development server..."
print_step "🌐 Frontend will be available at: $FRONTEND_URL"
print_step "🔧 Backend API is running at: $VITE_API_URL"
print_step ""
print_step "👁️  Watch Mode Active:"
print_step "   🔄 Backend: Uvicorn --reload (auto-restart on Python file changes)"
print_step "   🔄 Frontend: Vite HMR (hot module replacement)"
print_step "   📄 Spec watcher → Auto-regenerates REST client & WebSocket types"
print_step ""
print_step "💡 Change Flow:"
print_step "   Backend .py change → Uvicorn restart → Specs regenerate → Frontend clients update"
print_step "   Frontend .ts/.vue change → Vite HMR → Browser auto-refresh"
print_step ""
print_warning "Press Ctrl+C to stop all servers and watchers"
print_step ""

# Start frontend in background and capture PID
make -C frontend dev &
FRONTEND_PID=$!

print_step "Frontend started with PID: $FRONTEND_PID"

# Monitor all three processes
print_step ""
print_step "🎯 All services running. Monitoring processes..."
print_step ""


# Start unified watcher in background
# Unified spec watcher function
watch_specs() {
    # Per-module spec watching
    # Backend generates specs per module in: backend/src/trading_api/modules/{module}/specs_generated/
    # Pattern: {module}_openapi.json and {module}_asyncapi.json
    
    BACKEND_MODULES_DIR="backend/src/trading_api/modules"
    
    # Initialize baseline checksums for all module specs
    declare -A OPENAPI_CHECKSUMS
    declare -A ASYNCAPI_CHECKSUMS
    
    # Initial scan of all module specs
    for spec_file in "$BACKEND_MODULES_DIR"/*/specs_generated/*_openapi.json; do
        if [ -f "$spec_file" ]; then
            OPENAPI_CHECKSUMS["$spec_file"]=$(md5sum "$spec_file" 2>/dev/null | cut -d' ' -f1)
        fi
    done
    
    for spec_file in "$BACKEND_MODULES_DIR"/*/specs_generated/*_asyncapi.json; do
        if [ -f "$spec_file" ]; then
            ASYNCAPI_CHECKSUMS["$spec_file"]=$(md5sum "$spec_file" 2>/dev/null | cut -d' ' -f1)
        fi
    done

    # Watch loop (1 second interval)
    while true; do
        sleep 1
        
        SPECS_CHANGED=false

        # Check all OpenAPI specs for changes
        for spec_file in "$BACKEND_MODULES_DIR"/*/specs_generated/*_openapi.json; do
            if [ -f "$spec_file" ]; then
                CURRENT_CHECKSUM=$(md5sum "$spec_file" 2>/dev/null | cut -d' ' -f1)
                LAST_CHECKSUM="${OPENAPI_CHECKSUMS[$spec_file]:-}"
                
                if [ "$CURRENT_CHECKSUM" != "$LAST_CHECKSUM" ]; then
                    MODULE_NAME=$(basename "$spec_file" "_openapi.json")
                    print_warning "OpenAPI spec changed for module: $MODULE_NAME"
                    OPENAPI_CHECKSUMS["$spec_file"]="$CURRENT_CHECKSUM"
                    SPECS_CHANGED=true
                fi
            fi
        done
        
        # Check for new OpenAPI specs
        for spec_file in "$BACKEND_MODULES_DIR"/*/specs_generated/*_openapi.json; do
            if [ -f "$spec_file" ] && [ -z "${OPENAPI_CHECKSUMS[$spec_file]:-}" ]; then
                MODULE_NAME=$(basename "$spec_file" "_openapi.json")
                print_warning "New OpenAPI spec detected for module: $MODULE_NAME"
                OPENAPI_CHECKSUMS["$spec_file"]=$(md5sum "$spec_file" 2>/dev/null | cut -d' ' -f1)
                SPECS_CHANGED=true
            fi
        done

        # Check all AsyncAPI specs for changes
        for spec_file in "$BACKEND_MODULES_DIR"/*/specs_generated/*_asyncapi.json; do
            if [ -f "$spec_file" ]; then
                CURRENT_CHECKSUM=$(md5sum "$spec_file" 2>/dev/null | cut -d' ' -f1)
                LAST_CHECKSUM="${ASYNCAPI_CHECKSUMS[$spec_file]:-}"
                
                if [ "$CURRENT_CHECKSUM" != "$LAST_CHECKSUM" ]; then
                    MODULE_NAME=$(basename "$spec_file" "_asyncapi.json")
                    print_warning "AsyncAPI spec changed for module: $MODULE_NAME"
                    ASYNCAPI_CHECKSUMS["$spec_file"]="$CURRENT_CHECKSUM"
                    SPECS_CHANGED=true
                fi
            fi
        done
        
        # Check for new AsyncAPI specs
        for spec_file in "$BACKEND_MODULES_DIR"/*/specs_generated/*_asyncapi.json; do
            if [ -f "$spec_file" ] && [ -z "${ASYNCAPI_CHECKSUMS[$spec_file]:-}" ]; then
                MODULE_NAME=$(basename "$spec_file" "_asyncapi.json")
                print_warning "New AsyncAPI spec detected for module: $MODULE_NAME"
                ASYNCAPI_CHECKSUMS["$spec_file"]=$(md5sum "$spec_file" 2>/dev/null | cut -d' ' -f1)
                SPECS_CHANGED=true
            fi
        done

        # If any specs changed, regenerate frontend clients
        if [ "$SPECS_CHANGED" = true ]; then
            print_warning "Regenerating frontend clients from per-module specs..."
            if make -C frontend generate >/dev/null 2>&1; then
                print_success "Frontend clients regenerated successfully"
            else
                print_error "Failed to regenerate frontend clients"
            fi
        fi
    done
}
watch_specs &
WATCHER_PID=$!
print_step "   Spec watcher started with PID: $WATCHER_PID"


# Wait for all background processes
wait $FRONTEND_PID
wait $BACKEND_PID
wait $WATCHER_PID