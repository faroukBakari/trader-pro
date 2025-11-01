#!/bin/bash
# WebSocket Router Code Generator Wrapper
# This script generates WebSocket router classes and ensures they pass all quality checks

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
LEGACY_GENERATED_DIR="$BACKEND_DIR/src/trading_api/ws/generated"
MODULES_DIR="$BACKEND_DIR/src/trading_api/modules"

echo -e "${BLUE}🔧 WebSocket Router Code Generator${NC}"
echo ""

# Step 1: Run Python generator
echo -e "${BLUE}📝 Step 1: Generating router classes...${NC}"
cd "$BACKEND_DIR"
if poetry run python scripts/generate_ws_router.py; then
    echo -e "${GREEN}✅ Generation successful${NC}"
else
    echo -e "${RED}❌ Generation failed${NC}"
    exit 1
fi
echo ""

# Determine which architecture is in use
if find "$MODULES_DIR" -mindepth 2 -maxdepth 2 -type d -name "ws_generated" 2>/dev/null | grep -q .; then
    echo -e "${BLUE}🏗️  Detected modular architecture${NC}"
    GENERATED_DIRS=($(find "$MODULES_DIR" -mindepth 2 -maxdepth 2 -type d -name "ws_generated"))
    ARCHITECTURE="modular"
elif [[ -d "$LEGACY_GENERATED_DIR" ]]; then
    echo -e "${BLUE}🏗️  Detected legacy architecture${NC}"
    GENERATED_DIRS=("$LEGACY_GENERATED_DIR")
    ARCHITECTURE="legacy"
else
    echo -e "${RED}❌ No generated directories found${NC}"
    exit 1
fi
echo ""

# Step 2-8: Format and validate each generated directory
for GENERATED_DIR in "${GENERATED_DIRS[@]}"; do
    MODULE_NAME=$(basename "$(dirname "$GENERATED_DIR")")
    if [[ "$ARCHITECTURE" == "modular" ]]; then
        echo -e "${BLUE}━━━ Processing module: ${MODULE_NAME} ━━━${NC}"
    fi
    
    # Step 2: Format generated code
    echo -e "${BLUE}🎨 Step 2: Formatting generated code...${NC}"
    if poetry run black "$GENERATED_DIR"; then
        echo -e "${GREEN}✅ Black formatting complete${NC}"
    else
        echo -e "${RED}❌ Black formatting failed${NC}"
        exit 1
    fi
    echo ""

    # Step 3: Format with ruff
    echo -e "${BLUE}✨ Step 3: Formatting with ruff...${NC}"
    if poetry run ruff format "$GENERATED_DIR"; then
        echo -e "${GREEN}✅ Ruff formatting complete${NC}"
    else
        echo -e "${RED}❌ Ruff formatting failed${NC}"
        exit 1
    fi
    echo ""

    # Step 4: Auto-fix linter issues
    echo -e "${BLUE}🔧 Step 4: Auto-fixing linter issues...${NC}"
    if poetry run ruff check "$GENERATED_DIR" --fix; then
        echo -e "${GREEN}✅ Auto-fixes applied${NC}"
    else
        echo -e "${YELLOW}⚠️  Some auto-fixes applied${NC}"
    fi
    echo ""

    # Step 5: Run flake8 linter
    echo -e "${BLUE}🔍 Step 5: Running flake8 linter...${NC}"
    if poetry run flake8 "$GENERATED_DIR"; then
        echo -e "${GREEN}✅ Flake8 checks passed${NC}"
    else
        echo -e "${RED}❌ Flake8 checks failed${NC}"
        exit 1
    fi
    echo ""

    # Step 6: Run final ruff linter checks
    echo -e "${BLUE}🔍 Step 6: Running ruff linter checks...${NC}"
    if poetry run ruff check "$GENERATED_DIR"; then
        echo -e "${GREEN}✅ All ruff checks passed${NC}"
    else
        echo -e "${RED}❌ Ruff checks failed${NC}"
        echo -e "${YELLOW}Run 'make type-check' for details${NC}"
        exit 1
    fi
    echo ""

    # Step 7: Run type checks
    echo -e "${BLUE}🔬 Step 7: Running type checks...${NC}"
    if poetry run mypy "$GENERATED_DIR"; then
        echo -e "${GREEN}✅ Type checks passed${NC}"
    else
        echo -e "${RED}❌ Type checks failed${NC}"
        exit 1
    fi
    echo ""

    # Step 8: Sort imports with isort
    echo -e "${BLUE}📦 Step 8: Sorting imports (isort)...${NC}"
    if poetry run isort "$GENERATED_DIR"; then
        echo -e "${GREEN}✅ Import sorting complete${NC}"
    else
        echo -e "${RED}❌ Import sorting failed${NC}"
        exit 1
    fi
    echo ""
done

# Step 9: Verify imports work
echo -e "${BLUE}🧪 Step 9: Verifying all routers...${NC}"
if poetry run python scripts/verify_ws_routers.py; then
    echo -e "${GREEN}✅ All routers verified successfully${NC}"
else
    echo -e "${RED}❌ Router verification failed${NC}"
    exit 1
fi
echo ""

# Summary
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 Success! WebSocket routers generated and validated${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Generated files:${NC}"

if [[ "$ARCHITECTURE" == "modular" ]]; then
    for GENERATED_DIR in "${GENERATED_DIRS[@]}"; do
        MODULE_NAME=$(basename "$(dirname "$GENERATED_DIR")")
        echo -e "  ${BLUE}Module: ${MODULE_NAME}${NC}"
        find "$GENERATED_DIR" -type f -name "*.py" | while read -r file; do
            echo "    📄 $(basename "$file")"
        done
    done
else
    find "$LEGACY_GENERATED_DIR" -type f -name "*.py" | while read -r file; do
        echo "  📄 $(basename "$file")"
    done
fi

echo ""
echo -e "${BLUE}Usage example:${NC}"
echo ""

# Get example based on architecture
if [[ "$ARCHITECTURE" == "modular" ]]; then
    # Use first module's generated routers
    FIRST_MODULE_DIR="${GENERATED_DIRS[0]}"
    MODULE_NAME=$(basename "$(dirname "$FIRST_MODULE_DIR")")
    GENERATED_INIT="$FIRST_MODULE_DIR/__init__.py"
    
    if [[ -f "$GENERATED_INIT" ]]; then
        # Extract first router class name
        ROUTER=$(grep -oP '"\K[^"]+(?=")' "$GENERATED_INIT" | head -1)
        
        if [[ -n "$ROUTER" ]]; then
            ROUTE_NAME=$(echo "$ROUTER" | sed 's/WsRouter//' | sed 's/\([A-Z]\)/_\L\1/g' | sed 's/^_//' | tr '_' '-')
            
            echo "  # Modular architecture example (${MODULE_NAME} module):"
            echo "  from trading_api.modules.${MODULE_NAME}.ws_generated import ${ROUTER}"
            echo "  from trading_api.modules.${MODULE_NAME} import ${MODULE_NAME^}Module"
            echo "  module = ${MODULE_NAME^}Module()"
            echo "  router = ${ROUTER}(route='${ROUTE_NAME}', service=module.service)"
        fi
    fi
else
    # Legacy architecture
    GENERATED_INIT="$LEGACY_GENERATED_DIR/__init__.py"
    if [[ -f "$GENERATED_INIT" ]]; then
        # Extract all router class names from __all__ list
        ALL_ROUTERS=($(grep -oP '"\K[^"]+(?=")' "$GENERATED_INIT"))
        
        # Pick first router
        RANDOM_ROUTER=${ALL_ROUTERS[0]}
        
        # Determine service type by checking which file defined the TypeAlias
        DATAFEED_FILE="$BACKEND_DIR/src/trading_api/ws/datafeed.py"
        BROKER_FILE="$BACKEND_DIR/src/trading_api/ws/broker.py"
        
        if grep -q "$RANDOM_ROUTER" "$DATAFEED_FILE" 2>/dev/null; then
            SERVICE_TYPE="datafeed"
            SERVICE_CLASS="DatafeedService"
            SERVICE_IMPORT="trading_api.core.datafeed_service"
        elif grep -q "$RANDOM_ROUTER" "$BROKER_FILE" 2>/dev/null; then
            SERVICE_TYPE="broker"
            SERVICE_CLASS="BrokerService"
            SERVICE_IMPORT="trading_api.core.broker_service"
        else
            SERVICE_TYPE="unknown"
            SERVICE_CLASS="UnknownService"
            SERVICE_IMPORT="trading_api.core.unknown_service"
        fi
        
        # Generate route name
        ROUTER_FILE=$(echo "$RANDOM_ROUTER" | sed 's/WsRouter//')
        ROUTE_NAME=$(echo "$ROUTER_FILE" | sed 's/\([A-Z]\)/_\L\1/g' | sed 's/^_//' | tr '_' '-')
        
        echo "  # Legacy architecture example (${SERVICE_TYPE} router):"
        echo "  from trading_api.ws.generated import ${RANDOM_ROUTER}"
        echo "  from ${SERVICE_IMPORT} import ${SERVICE_CLASS}"
        echo "  service = ${SERVICE_CLASS}()"
        echo "  router = ${RANDOM_ROUTER}(route='${ROUTE_NAME}', tags=['${SERVICE_TYPE}'], service=service)"
    else
        echo "  # No routers generated"
    fi
fi
echo ""
