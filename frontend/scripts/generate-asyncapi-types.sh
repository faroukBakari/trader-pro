#!/bin/bash
# AsyncAPI Types Generator
# Generates TypeScript types from backend AsyncAPI specification.
#
# Usage:
#   ./scripts/generate-asyncapi-types.sh

set -e

# Configuration
OUTPUT_DIR="./src/clients/ws-types-generated"
BACKEND_DIR="../backend"
ASYNCAPI_SPEC="$BACKEND_DIR/asyncapi.json"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 AsyncAPI Types Generator${NC}"
echo ""

# Verify AsyncAPI spec exists
if [ ! -f "$ASYNCAPI_SPEC" ]; then
    echo -e "${RED}❌ AsyncAPI specification not found at: $ASYNCAPI_SPEC${NC}"
    echo -e "${YELLOW}💡 Generate it first: cd ../backend && make export-asyncapi-spec${NC}"
    exit 1
fi

# Clean up previous types
echo -e "${BLUE}🧹 Cleaning previous AsyncAPI types...${NC}"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}✅ Cleanup complete${NC}"
echo ""

# Generate WebSocket types
echo -e "${BLUE}🔧 Generating WebSocket types from AsyncAPI...${NC}"

if node "./scripts/generate-ws-types.mjs" "$ASYNCAPI_SPEC" "$OUTPUT_DIR"; then
    echo ""
    echo -e "${GREEN}🎉 Success! Generated WebSocket types from AsyncAPI specification${NC}"
    echo -e "${GREEN}📁 Output: $OUTPUT_DIR${NC}"
    echo -e "${GREEN}   - Import: import { Bar, SubscriptionRequest, WS_OPERATIONS } from '@/clients/ws-types-generated'${NC}"
    echo ""
    exit 0
else
    echo -e "${RED}❌ WebSocket types generation failed${NC}"
    exit 1
fi
