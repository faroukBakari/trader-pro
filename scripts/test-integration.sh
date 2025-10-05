#!/bin/bash
# Integration Test Script
# Tests the complete flow: Backend API → Client Generation → Frontend Build

set -e

# Environment configuration
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export VITE_API_URL="${VITE_API_URL:-http://localhost:$BACKEND_PORT}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Integration Test - Backend + Frontend${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""

# Clean up generated files for fresh test environment
echo -e "${BLUE}Step 0: Cleaning Generated Files${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧹 Cleaning backend generated files..."
rm -f backend/openapi*.json
echo "🧹 Cleaning frontend generated client..."
rm -rf frontend/src/services/generated
echo "🧹 Cleaning frontend build artifacts..."
rm -rf frontend/dist frontend/node_modules/.vite
echo -e "${GREEN}✅ Clean up complete${NC}"
echo ""

# Track if we started the server
SERVER_STARTED=false
SERVER_PID=""

# Cleanup function
cleanup() {
    if [ "$SERVER_STARTED" = true ] && [ ! -z "$SERVER_PID" ]; then
        echo -e "\n${YELLOW}🛑 Stopping backend server (PID: $SERVER_PID)...${NC}"
        # Try graceful shutdown first
        kill -TERM $SERVER_PID 2>/dev/null || true
        sleep 2
        # Force kill if still running
        if kill -0 $SERVER_PID 2>/dev/null; then
            kill -KILL $SERVER_PID 2>/dev/null || true
        fi
        wait $SERVER_PID 2>/dev/null || true
    fi

    # Also clean up any remaining uvicorn processes
    pkill -TERM -f "uvicorn trading_api.main:app" 2>/dev/null || true
    sleep 1
    pkill -KILL -f "uvicorn trading_api.main:app" 2>/dev/null || true
}

# Register cleanup on exit and signals
trap cleanup EXIT INT TERM

echo -e "${BLUE}Step 1: Testing Backend${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd backend

echo "📦 Installing backend dependencies..."
make install > /dev/null 2>&1

echo "🧪 Running backend tests..."
if make test > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend tests passed${NC}"
else
    echo -e "${RED}❌ Backend tests failed${NC}"
    exit 1
fi

echo "🔍 Running backend linting..."
if make lint-check > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend linting passed${NC}"
else
    echo -e "${RED}❌ Backend linting failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 2: Starting Backend Server${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🚀 Starting backend server..."
make dev-ci > /dev/null 2>&1 &
SERVER_PID=$!
SERVER_STARTED=true

echo "⏳ Waiting for server to be ready..."
for i in {1..20}; do
    if curl -sf http://localhost:$BACKEND_PORT/api/v1/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend server is ready${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e "${RED}❌ Backend server failed to start${NC}"
        exit 1
    fi
    sleep 1
done

echo "🩺 Testing API endpoints..."
if curl -sf http://localhost:$BACKEND_PORT/api/v1/health > /dev/null 2>&1 && \
   curl -sf http://localhost:$BACKEND_PORT/api/v1/version > /dev/null 2>&1 && \
   curl -sf http://localhost:$BACKEND_PORT/api/v1/versions > /dev/null 2>&1; then
    echo -e "${GREEN}✅ All API endpoints responding${NC}"
else
    echo -e "${RED}❌ Some API endpoints failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 3: Testing Frontend (No Backend)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd ../frontend

echo "📦 Installing frontend dependencies..."
npm ci > /dev/null 2>&1

echo "🧹 Cleaning generated client..."
rm -rf src/services/generated

echo "🧪 Running frontend tests (with mocks)..."
if npm run test:unit run > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend tests passed (using mocks)${NC}"
else
    echo -e "${RED}❌ Frontend tests failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 4: Client Generation from Live API${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🔧 Generating client from live API..."
if npm run client:generate > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Client generation successful${NC}"
else
    echo -e "${RED}❌ Client generation failed${NC}"
    exit 1
fi

echo "🔍 Verifying generated client..."
if [ ! -f "src/services/generated/.client-type" ]; then
    echo -e "${RED}❌ No .client-type file found${NC}"
    exit 1
fi

CLIENT_TYPE=$(cat src/services/generated/.client-type)
if [ "$CLIENT_TYPE" != "server" ]; then
    echo -e "${RED}❌ Expected 'server' client but got '$CLIENT_TYPE'${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Generated client type: $CLIENT_TYPE${NC}"

echo "📝 Checking generated files..."
REQUIRED_FILES=(
    "src/services/generated/api.ts"
    "src/services/generated/base.ts"
    "src/services/generated/configuration.ts"
    "src/services/generated/client-config.ts"
    "src/services/generated/index.ts"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Required file missing: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required files present${NC}"

echo ""
echo -e "${BLUE}Step 5: Building Frontend with Generated Client${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🏗️  Building frontend..."
if VITE_API_URL=$VITE_API_URL npm run build > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend build successful${NC}"
else
    echo -e "${RED}❌ Frontend build failed${NC}"
    exit 1
fi

echo "📊 Checking build output..."
if [ ! -d "dist" ]; then
    echo -e "${RED}❌ No dist directory found${NC}"
    exit 1
fi

if [ ! -f "dist/index.html" ]; then
    echo -e "${RED}❌ No index.html in dist${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Build artifacts created${NC}"

echo ""
echo -e "${BLUE}Step 6: Testing Mock Fallback${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🛑 Stopping backend server..."
kill $SERVER_PID 2>/dev/null || true
wait $SERVER_PID 2>/dev/null || true
SERVER_STARTED=false

# Force kill any remaining uvicorn processes
pkill -9 -f "uvicorn trading_api.main:app" 2>/dev/null || true

sleep 3

echo "🧹 Cleaning generated client..."
rm -rf src/services/generated

echo "🎭 Generating client without backend..."
if npm run client:generate > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Mock fallback generation successful${NC}"
else
    echo -e "${RED}❌ Mock fallback generation failed${NC}"
    exit 1
fi

if [ ! -f "src/services/generated/.client-type" ]; then
    echo -e "${RED}❌ No .client-type file found${NC}"
    exit 1
fi

CLIENT_TYPE=$(cat src/services/generated/.client-type)
if [ "$CLIENT_TYPE" != "mock" ]; then
    echo -e "${RED}❌ Expected 'mock' client but got '$CLIENT_TYPE'${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Mock client type: $CLIENT_TYPE${NC}"

echo "🏗️  Building frontend with mocks..."
if npm run build > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend build successful (with mocks)${NC}"
else
    echo -e "${RED}❌ Frontend build failed (with mocks)${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ All Integration Tests Passed!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo "Summary:"
echo "  ✅ Backend tests: passed"
echo "  ✅ Backend server: started and healthy"
echo "  ✅ Frontend tests: passed (with mocks)"
echo "  ✅ Client generation: successful (from live API)"
echo "  ✅ Frontend build: successful (with generated client)"
echo "  ✅ Mock fallback: successful"
echo "  ✅ Frontend build: successful (with mocks)"
echo ""
