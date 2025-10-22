#!/bin/bash

# Full-stack development script
# Starts backend, waits for it to be ready, generates frontend client, then starts frontend

set -e

# Create a new process group so we can track all child processes
set -m

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

# Global variables for process IDs
BACKEND_PID=""
FRONTEND_PID=""
OPENAPI_WATCHER_PID=""
ASYNCAPI_WATCHER_PID=""
WS_WATCHER_PID=""
SCRIPT_PGID=$$  # Store our process group ID

print_step "🚀 Starting full-stack development environment..."

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

# Function to cleanup background processes
cleanup() {
    print_step "🛑 Shutting down full-stack development environment..."

    # First, kill tracked PIDs and their descendants using SIGTERM
    if [ ! -z "$FRONTEND_PID" ]; then
        print_step "Stopping frontend server and its children (PID: $FRONTEND_PID)..."
        kill_process_tree "$FRONTEND_PID" "TERM"
    fi

    if [ ! -z "$BACKEND_PID" ]; then
        print_step "Stopping backend server and its children (PID: $BACKEND_PID)..."
        kill_process_tree "$BACKEND_PID" "TERM"
    fi

    if [ ! -z "$WS_WATCHER_PID" ]; then
        print_step "Stopping WebSocket router watcher (PID: $WS_WATCHER_PID)..."
        kill_process_tree "$WS_WATCHER_PID" "TERM"
    fi

    if [ ! -z "$OPENAPI_WATCHER_PID" ]; then
        print_step "Stopping OpenAPI watcher (PID: $OPENAPI_WATCHER_PID)..."
        kill_process_tree "$OPENAPI_WATCHER_PID" "TERM"
    fi

    if [ ! -z "$ASYNCAPI_WATCHER_PID" ]; then
        print_step "Stopping AsyncAPI watcher (PID: $ASYNCAPI_WATCHER_PID)..."
        kill_process_tree "$ASYNCAPI_WATCHER_PID" "TERM"
    fi

    # Wait for graceful shutdown
    sleep 2

    # Now kill any remaining processes in our process group (including orphaned/daemon processes)
    print_step "Cleaning up any remaining processes in process group..."
    local remaining_pids=$(get_process_group_pids)
    
    if [ ! -z "$remaining_pids" ]; then
        print_step "Found remaining processes, sending SIGTERM..."
        for pid in $remaining_pids; do
            if is_process_running "$pid"; then
                kill -TERM "$pid" 2>/dev/null || true
            fi
        done
        
        sleep 2
        
        # Force kill any stubborn processes
        remaining_pids=$(get_process_group_pids)
        if [ ! -z "$remaining_pids" ]; then
            print_step "Force killing stubborn processes..."
            for pid in $remaining_pids; do
                if is_process_running "$pid"; then
                    kill -KILL "$pid" 2>/dev/null || true
                fi
            done
        fi
    fi

    print_success "All processes stopped. Environment cleaned up."
    exit 0
}

# Set up trap to cleanup on exit
trap cleanup EXIT INT TERM

# Step 1: Clean up and generate everything before starting servers
print_step "1. Preparing environment..."
print_step "   🧹 Cleaning generated files..."
rm -f backend/openapi.json backend/asyncapi.json
rm -rf frontend/src/clients/*
rm -rf frontend/dist frontend/node_modules/.vite

print_step "   🔧 Generating WebSocket routers..."
if make -f project.mk generate-ws-routers >/dev/null 2>&1; then
    print_success "   WebSocket routers generated"
else
    print_error "   WebSocket router generation failed!"
    exit 1
fi

# Step 2: Start backend server in background
print_step "2. Starting backend server..."
make -f project.mk dev-backend &
BACKEND_PID=$!
print_step "   Backend started with PID: $BACKEND_PID"

# Step 3: Wait for backend to be ready
print_step "3. Waiting for backend to be ready..."
timeout=60
while [ $timeout -gt 0 ]; do
    if curl -f http://localhost:$BACKEND_PORT/api/v1/health >/dev/null 2>&1; then
        print_success "Backend is ready and responding"
        break
    fi
    sleep 1
    timeout=$((timeout - 1))
done

if [ $timeout -eq 0 ]; then
    print_error "Backend failed to start within 60 seconds"
    exit 1
fi

# Step 4: Generate frontend clients
print_step "4. Generating frontend clients..."
if make -f project.mk generate-openapi-client >/dev/null 2>&1 && make -f project.mk generate-asyncapi-types >/dev/null 2>&1; then
    print_success "Frontend clients generated successfully"
else
    print_error "Client generation failed"
    exit 1
fi

# Step 5: Start spec file watchers
print_step "5. Setting up spec file watchers..."

# Define the spec file paths
OPENAPI_FILE="backend/openapi.json"
ASYNCAPI_FILE="backend/asyncapi.json"

if [ -f "$OPENAPI_FILE" ]; then
    OPENAPI_INITIAL_MTIME=$(stat -c %Y "$OPENAPI_FILE" 2>/dev/null || echo "0")
    OPENAPI_LAST_CONTENT=$(cat "$OPENAPI_FILE" 2>/dev/null || echo "")
else
    OPENAPI_INITIAL_MTIME="0"
    OPENAPI_LAST_CONTENT=""
fi

if [ -f "$ASYNCAPI_FILE" ]; then
    ASYNCAPI_INITIAL_MTIME=$(stat -c %Y "$ASYNCAPI_FILE" 2>/dev/null || echo "0")
    ASYNCAPI_LAST_CONTENT=$(cat "$ASYNCAPI_FILE" 2>/dev/null || echo "")
else
    ASYNCAPI_INITIAL_MTIME="0"
    ASYNCAPI_LAST_CONTENT=""
fi

# Start OpenAPI file watcher in background
{
    print_step "Starting OpenAPI file watcher..."
    LAST_MTIME="$OPENAPI_INITIAL_MTIME"

    while true; do
        sleep 1  # Check every 2 seconds

        if [ -f "$OPENAPI_FILE" ]; then
            CURRENT_MTIME=$(stat -c %Y "$OPENAPI_FILE" 2>/dev/null || echo "0")

            # Only check content if modification time changed
            if [ "$CURRENT_MTIME" != "$LAST_MTIME" ] && [ "$CURRENT_MTIME" != "0" ]; then
                CURRENT_CONTENT=$(cat "$OPENAPI_FILE" 2>/dev/null || echo "")
                
                # Compare actual content, not just timestamps
                if [ "$CURRENT_CONTENT" != "$OPENAPI_LAST_CONTENT" ]; then
                    print_warning "OpenAPI file changed! Regenerating REST client..."
                    if SKIP_SPEC_GENERATION=true make -f project.mk generate-openapi-client >/dev/null 2>&1; then
                        print_success "Frontend REST client regenerated successfully"
                    else
                        print_error "Failed to regenerate REST client"
                    fi
                    
                    # Update both timestamp and content
                    LAST_MTIME="$CURRENT_MTIME"
                    OPENAPI_LAST_CONTENT="$CURRENT_CONTENT"
                else
                    # Content unchanged, just update timestamp to avoid repeated checks
                    LAST_MTIME="$CURRENT_MTIME"
                fi
            fi
        fi
    done
} &
OPENAPI_WATCHER_PID=$!

# Start AsyncAPI file watcher in background
{
    print_step "Starting AsyncAPI file watcher..."
    LAST_MTIME="$ASYNCAPI_INITIAL_MTIME"

    while true; do
        sleep 1  # Check every 2 seconds

        if [ -f "$ASYNCAPI_FILE" ]; then
            CURRENT_MTIME=$(stat -c %Y "$ASYNCAPI_FILE" 2>/dev/null || echo "0")

            # Only check content if modification time changed
            if [ "$CURRENT_MTIME" != "$LAST_MTIME" ] && [ "$CURRENT_MTIME" != "0" ]; then
                CURRENT_CONTENT=$(cat "$ASYNCAPI_FILE" 2>/dev/null || echo "")
                
                # Compare actual content, not just timestamps
                if [ "$CURRENT_CONTENT" != "$ASYNCAPI_LAST_CONTENT" ]; then
                    print_warning "AsyncAPI file changed! Regenerating WebSocket types..."
                    if make -f project.mk generate-asyncapi-types >/dev/null 2>&1; then
                        print_success "Frontend WebSocket types regenerated successfully"
                    else
                        print_error "Failed to regenerate WebSocket types"
                    fi
                    
                    # Update both timestamp and content
                    LAST_MTIME="$CURRENT_MTIME"
                    ASYNCAPI_LAST_CONTENT="$CURRENT_CONTENT"
                else
                    # Content unchanged, just update timestamp to avoid repeated checks
                    LAST_MTIME="$CURRENT_MTIME"
                fi
            fi
        fi
    done
} &
ASYNCAPI_WATCHER_PID=$!

# Step 6: Start WebSocket router watcher
print_step "6. Starting WebSocket router watcher..."
(cd backend && ./scripts/watch-ws-routers.sh) &
WS_WATCHER_PID=$!

print_step "7. Starting frontend development server..."
print_step "🌐 Frontend will be available at: $FRONTEND_URL"
print_step "🔧 Backend API is running at: $VITE_API_URL"
print_step ""
print_step "👁️  Active Watchers:"
print_step "   📄 OpenAPI spec → REST client auto-regeneration"
print_step "   📄 AsyncAPI spec → WebSocket types auto-regeneration"
print_step "   🔄 WebSocket handlers → Backend router auto-regeneration"
print_step ""
print_step "💡 How it works:"
print_step "   • Uvicorn --reload watches backend Python files"
print_step "   • On code change → Uvicorn restarts → Specs regenerate"
print_step "   • Spec file watchers detect changes → Regenerate frontend clients"
print_step ""
print_warning "Press Ctrl+C to stop all servers and watchers"
print_step ""

# Start frontend in background and capture PID
make -f project.mk dev-frontend &
FRONTEND_PID=$!

print_step "Frontend started with PID: $FRONTEND_PID"

# Wait for backend or frontend to exit (or be interrupted)
# This keeps the script running until one of the main servers exits
print_step ""
print_step "🎯 All services running. Monitoring backend and frontend..."
print_step ""

# Monitor both backend and frontend processes
while true; do
    # Check if backend is still running
    if [ ! -z "$BACKEND_PID" ] && ! is_process_running "$BACKEND_PID"; then
        print_error "Backend process exited unexpectedly!"
        exit 1
    fi
    
    # Check if frontend is still running  
    if [ ! -z "$FRONTEND_PID" ] && ! is_process_running "$FRONTEND_PID"; then
        print_error "Frontend process exited unexpectedly!"
        exit 1
    fi
    
    # Sleep before next check
    sleep 1
done