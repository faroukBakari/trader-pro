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
GENERATED_DIR="$BACKEND_DIR/src/trading_api/ws/generated"

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

# Step 2: Format generated code
echo -e "${BLUE}🎨 Step 2: Formatting generated code...${NC}"
if poetry run black "$GENERATED_DIR"; then
    echo -e "${GREEN}✅ Black formatting complete${NC}"
else
    echo -e "${RED}❌ Black formatting failed${NC}"
    exit 1
fi
echo ""

# Step 3: Sort imports with isort
echo -e "${BLUE}📦 Step 3: Sorting imports (isort)...${NC}"
if poetry run isort "$GENERATED_DIR"; then
    echo -e "${GREEN}✅ Import sorting complete${NC}"
else
    echo -e "${RED}❌ Import sorting failed${NC}"
    exit 1
fi
echo ""

# Step 4: Format with ruff
echo -e "${BLUE}✨ Step 4: Formatting with ruff...${NC}"
if poetry run ruff format "$GENERATED_DIR"; then
    echo -e "${GREEN}✅ Ruff formatting complete${NC}"
else
    echo -e "${RED}❌ Ruff formatting failed${NC}"
    exit 1
fi
echo ""

# Step 5: Auto-fix linter issues
echo -e "${BLUE}🔧 Step 5: Auto-fixing linter issues...${NC}"
if poetry run ruff check "$GENERATED_DIR" --fix; then
    echo -e "${GREEN}✅ Auto-fixes applied${NC}"
else
    echo -e "${YELLOW}⚠️  Some auto-fixes applied${NC}"
fi
echo ""

# Step 6: Run flake8 linter
echo -e "${BLUE}🔍 Step 6: Running flake8 linter...${NC}"
if poetry run flake8 "$GENERATED_DIR"; then
    echo -e "${GREEN}✅ Flake8 checks passed${NC}"
else
    echo -e "${RED}❌ Flake8 checks failed${NC}"
    exit 1
fi
echo ""

# Step 7: Run final ruff linter checks
echo -e "${BLUE}🔍 Step 7: Running ruff linter checks...${NC}"
if poetry run ruff check "$GENERATED_DIR"; then
    echo -e "${GREEN}✅ All ruff checks passed${NC}"
else
    echo -e "${RED}❌ Ruff checks failed${NC}"
    echo -e "${YELLOW}Run 'make lint-check' for details${NC}"
    exit 1
fi
echo ""

# Step 8: Run type checks
echo -e "${BLUE}🔬 Step 8: Running type checks...${NC}"
if poetry run mypy "$GENERATED_DIR"; then
    echo -e "${GREEN}✅ Type checks passed${NC}"
else
    echo -e "${RED}❌ Type checks failed${NC}"
    exit 1
fi
echo ""

# Step 9: Verify imports work
echo -e "${BLUE}🧪 Step 9: Verifying imports...${NC}"
VERIFY_SCRIPT=$(cat <<'EOF'
import sys
try:
    from trading_api.ws.generated import BarWsRouter
    print("✓ BarWsRouter imported successfully")
    
    # Verify class is callable
    router = BarWsRouter(route="test", tags=["test"])
    print("✓ BarWsRouter instantiation works")
    
    # Verify topic_builder exists
    assert hasattr(router, 'topic_builder'), "topic_builder method missing"
    print("✓ topic_builder method exists")
    
    sys.exit(0)
except Exception as e:
    print(f"✗ Import verification failed: {e}")
    sys.exit(1)
EOF
)

if echo "$VERIFY_SCRIPT" | poetry run python -c "$(cat)"; then
    echo -e "${GREEN}✅ Import verification passed${NC}"
else
    echo -e "${RED}❌ Import verification failed${NC}"
    exit 1
fi
echo ""

# Summary
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 Success! WebSocket routers generated and validated${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Generated files:${NC}"
find "$GENERATED_DIR" -type f -name "*.py" | while read -r file; do
    echo "  📄 $(basename "$file")"
done
echo ""
echo -e "${BLUE}Usage example:${NC}"
echo "  from trading_api.ws.generated import BarWsRouter"
echo "  router = BarWsRouter(route='bars', tags=['datafeed'])"
echo ""
