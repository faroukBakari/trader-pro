#!/bin/bash
# Shared library for Git hooks

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in CI environment
is_ci() {
    [[ "$CI" == "true" ]] || [[ "$GITHUB_ACTIONS" == "true" ]] || [[ "$GITLAB_CI" == "true" ]]
}

# Get list of staged files matching pattern
get_staged_files() {
    local pattern="$1"
    git diff --cached --name-only --diff-filter=ACM | grep -E "$pattern" | grep -v -E "(node_modules/|\.venv/|__pycache__/|\.pytest_cache/|dist/|build/)" || true
}

# Get list of changed files (staged + unstaged) matching pattern
get_changed_files() {
    local pattern="$1"
    git diff --name-only --diff-filter=ACM HEAD | grep -E "$pattern" | grep -v -E "(node_modules/|\.venv/|__pycache__/|\.pytest_cache/|dist/|build/)" || true
}

# Check if directory exists and has files
has_files_in_dir() {
    local dir="$1"
    local pattern="$2"
    [[ -d "$dir" ]] && find "$dir" -name "$pattern" -type f | head -1 | grep -q .
}

# Run command with error handling
run_check() {
    local name="$1"
    local cmd="$2"
    local dir="$3"

    log_info "Running $name..."

    if [[ -n "$dir" ]] && [[ -d "$dir" ]]; then
        cd "$dir" || { log_error "Failed to change to directory $dir"; return 1; }
    fi

    if eval "$cmd"; then
        log_success "$name passed"
        return 0
    else
        log_error "$name failed"
        return 1
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if we should skip hooks (for CI or emergency commits)
should_skip_hooks() {
    [[ "$SKIP_HOOKS" == "true" ]] || [[ "$NO_VERIFY" == "true" ]]
}