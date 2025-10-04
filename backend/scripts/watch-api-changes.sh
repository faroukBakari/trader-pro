#!/bin/bash
# Watch mode for automatic client regeneration on API changes

set -e

echo "👀 Starting API change watcher..."
echo "📁 Monitoring: src/ directory for Python changes"
echo "🔄 Will regenerate frontend client on changes"
echo "⏹️  Press Ctrl+C to stop"
echo ""

# Function to regenerate client
regenerate_client() {
    echo "🔄 Changes detected, regenerating client..."
    if ./scripts/generate-frontend-client.sh --force; then
        echo "✅ Client regenerated successfully at $(date)"
    else
        echo "❌ Client regeneration failed at $(date)"
    fi
    echo ""
}

# Function to check if fswatch is available
check_fswatch() {
    if command -v fswatch >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to check if inotifywait is available
check_inotify() {
    if command -v inotifywait >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to install fswatch on macOS
install_fswatch_macos() {
    if command -v brew >/dev/null 2>&1; then
        echo "📦 Installing fswatch via Homebrew..."
        brew install fswatch
        return $?
    else
        echo "❌ Homebrew not found. Please install fswatch manually:"
        echo "   https://github.com/emcrisostomo/fswatch"
        return 1
    fi
}

# Function to install inotify-tools on Linux
install_inotify_linux() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "📦 Installing inotify-tools via apt..."
        sudo apt-get update && sudo apt-get install -y inotify-tools
        return $?
    elif command -v yum >/dev/null 2>&1; then
        echo "📦 Installing inotify-tools via yum..."
        sudo yum install -y inotify-tools
        return $?
    elif command -v dnf >/dev/null 2>&1; then
        echo "📦 Installing inotify-tools via dnf..."
        sudo dnf install -y inotify-tools
        return $?
    else
        echo "❌ Package manager not found. Please install inotify-tools manually"
        return 1
    fi
}

# Main watch function using fswatch (macOS/Linux)
watch_with_fswatch() {
    echo "🔍 Using fswatch for file monitoring..."
    fswatch -o src/ | while read -r; do
        regenerate_client
    done
}

# Main watch function using inotifywait (Linux)
watch_with_inotify() {
    echo "🔍 Using inotifywait for file monitoring..."
    while true; do
        inotifywait -r -e modify,create,delete src/ && regenerate_client
    done
}

# Fallback polling method
watch_with_polling() {
    echo "🔍 Using polling method (fallback)..."
    echo "⚠️  This method checks for changes every 5 seconds"
    
    local last_checksum=""
    
    while true; do
        # Create a checksum of all Python files
        local current_checksum=$(find src/ -name "*.py" -type f -exec sha256sum {} \; 2>/dev/null | sha256sum | cut -d' ' -f1)
        
        if [ "$current_checksum" != "$last_checksum" ] && [ ! -z "$last_checksum" ]; then
            regenerate_client
        fi
        
        last_checksum="$current_checksum"
        sleep 5
    done
}

# Main function
main() {
    # Generate initial client
    echo "🚀 Generating initial client..."
    ./scripts/generate-frontend-client.sh
    echo ""
    
    # Determine which watch method to use
    if check_fswatch; then
        watch_with_fswatch
    elif check_inotify; then
        watch_with_inotify
    else
        echo "⚠️  No file watching tools found"
        echo "💡 Installing file watching tools..."
        
        case "$(uname -s)" in
            Darwin*)
                if install_fswatch_macos; then
                    watch_with_fswatch
                else
                    echo "📊 Falling back to polling method"
                    watch_with_polling
                fi
                ;;
            Linux*)
                if install_inotify_linux; then
                    watch_with_inotify
                else
                    echo "📊 Falling back to polling method"
                    watch_with_polling
                fi
                ;;
            *)
                echo "📊 Unknown OS, using polling method"
                watch_with_polling
                ;;
        esac
    fi
}

# Cleanup function
cleanup() {
    echo ""
    echo "🛑 Stopping API change watcher..."
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Run main function
main