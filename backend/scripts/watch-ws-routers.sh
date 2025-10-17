#!/bin/bash
# WebSocket Router Watcher
# Monitors ws/*.py files and regenerates routers on changes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
WS_DIR="$BACKEND_DIR/src/trading_api/ws"
MODELS_DIR="$BACKEND_DIR/src/trading_api/models"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[WS-WATCHER]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[WS-WATCHER]${NC} ✅ $1"
}

print_warning() {
    echo -e "${YELLOW}[WS-WATCHER]${NC} ⚠️  $1"
}

regenerate_routers() {
    print_info "Changes detected, regenerating routers..."
    cd "$BACKEND_DIR"
    if ./scripts/generate-ws-routers.sh >/dev/null 2>&1; then
        print_success "Routers updated"
    else
        print_warning "Router regeneration had issues"
    fi
}

# Initial setup
print_info "Starting WebSocket router watcher..."
print_info "Monitoring: $WS_DIR"
print_info "Monitoring: $MODELS_DIR"
# Don't regenerate on startup - let the dev server handle initial generation
# regenerate_routers

# Check if inotifywait is available
if command -v inotifywait >/dev/null 2>&1; then
    print_info "Using inotifywait for efficient file watching"
    
    # Watch for modifications, creates, and deletes in both directories
    # Exclude generated directory and __pycache__
    while true; do
        inotifywait -q -e modify,create,delete \
            --exclude '(generated|__pycache__|\.pyc$)' \
            -r "$WS_DIR" "$MODELS_DIR" >/dev/null 2>&1
        
        # Debounce: wait a bit for multiple rapid changes
        sleep 1
        regenerate_routers
    done
else
    print_warning "inotifywait not found, using polling mode"
    print_info "Install inotify-tools for better performance: sudo apt install inotify-tools"
    
    # Polling fallback - monitor both directories
    LAST_HASH=""
    
    while true; do
        # Get hash of all .py files from both directories (excluding generated/)
        CURRENT_HASH=$(find "$WS_DIR" "$MODELS_DIR" -name "*.py" \
            -not -path "*/generated/*" \
            -not -path "*/__pycache__/*" \
            -type f -exec md5sum {} \; 2>/dev/null | sort | md5sum | cut -d' ' -f1)
        
        if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "$LAST_HASH" ] && [ -n "$LAST_HASH" ]; then
            regenerate_routers
        fi
        
        LAST_HASH="$CURRENT_HASH"
        sleep 3  # Check every 3 seconds
    done
fi
