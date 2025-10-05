#!/bin/bash

# Smoke test runner script
# Runs the dev-fullstack environment and executes Playwright smoke tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Change to smoke tests directory
cd "$(dirname "$0")"

print_step "🧪 Running Trader Pro Smoke Tests"

# Check if node_modules exists, if not install dependencies
if [ ! -d "node_modules" ]; then
    print_step "Installing smoke test dependencies..."
    npm install
fi

# Install Playwright browsers if not already installed
print_step "Ensuring Playwright browsers are installed..."
npx playwright install --with-deps chromium

print_step "Starting smoke tests..."
print_warning "This will start the full-stack environment and run tests against it"

# Run the tests
if npm test; then
    print_success "All smoke tests passed!"

    print_step "Generating test report..."
    npm run test:report

    exit 0
else
    print_error "Smoke tests failed!"

    print_step "Generating test report for failed tests..."
    npm run test:report

    exit 1
fi