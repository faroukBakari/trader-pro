#!/bin/bash
# AsyncAPI Types Generator - Per-Module
# Generates TypeScript types from per-module AsyncAPI specifications.
#
# Usage:
#   ./scripts/generate-asyncapi-types.sh

set -e

# Configuration
BACKEND_DIR="../backend"
BACKEND_MODULES_DIR="$BACKEND_DIR/src/trading_api/modules"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 AsyncAPI Types Generator - Per-Module${NC}"
echo ""

# Find all module AsyncAPI specs (UPDATED PATH PATTERN)
ASYNCAPI_SPECS=$(find "$BACKEND_MODULES_DIR" -type f -path "*/specs_generated/*_asyncapi.json" 2>/dev/null || echo "")

if [ -z "$ASYNCAPI_SPECS" ]; then
    echo -e "${RED}❌ No AsyncAPI specifications found in: $BACKEND_MODULES_DIR${NC}"
    echo ""
    echo -e "${YELLOW}Backend specs must be generated first. Run:${NC}"
    echo -e "${BLUE}  cd backend && make generate${NC}"
    echo -e "${BLUE}  # OR from project root:${NC}"
    echo -e "${BLUE}  make -f project.mk generate${NC}"
    echo ""
    exit 1
fi

# Count modules
MODULE_COUNT=$(echo "$ASYNCAPI_SPECS" | wc -l)
echo -e "${BLUE}📦 Found $MODULE_COUNT module(s) with AsyncAPI specs${NC}"
echo ""

# Track success/failure
GENERATED_MODULES=()
FAILED_MODULES=()

# Generate types for each module
while IFS= read -r SPEC_PATH; do
    # Extract module name from filename: {module}_asyncapi.json (UPDATED)
    MODULE_NAME=$(basename "$SPEC_PATH" "_asyncapi.json")
    OUTPUT_DIR="./src/clients/ws-types-${MODULE_NAME}"
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}📦 Processing module: ${MODULE_NAME}${NC}"
    echo -e "${BLUE}   Spec: ${SPEC_PATH}${NC}"
    echo -e "${BLUE}   Output: ${OUTPUT_DIR}${NC}"
    
    # Clean up previous types for this module
    echo -e "${BLUE}🧹 Cleaning previous types...${NC}"
    rm -rf "$OUTPUT_DIR"
    mkdir -p "$OUTPUT_DIR"
    
    # Generate WebSocket types
    echo -e "${BLUE}🔧 Generating WebSocket types from AsyncAPI...${NC}"
    
    if node "./scripts/generate-ws-types.mjs" "$SPEC_PATH" "$OUTPUT_DIR"; then
        GENERATED_MODULES+=("$MODULE_NAME")
        echo -e "${GREEN}✅ Module '${MODULE_NAME}' types generated successfully${NC}"
    else
        echo -e "${RED}❌ Type generation failed for module: ${MODULE_NAME}${NC}"
        FAILED_MODULES+=("$MODULE_NAME")
    fi
    
    echo ""
done <<< "$ASYNCAPI_SPECS"

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Generation Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ ${#GENERATED_MODULES[@]} -gt 0 ]; then
    echo -e "${GREEN}✅ Successfully generated types for ${#GENERATED_MODULES[@]} module(s):${NC}"
    for module in "${GENERATED_MODULES[@]}"; do
        echo -e "${GREEN}   - ws-types-${module}${NC}"
    done
fi

if [ ${#FAILED_MODULES[@]} -gt 0 ]; then
    echo -e "${RED}❌ Failed to generate types for ${#FAILED_MODULES[@]} module(s):${NC}"
    for module in "${FAILED_MODULES[@]}"; do
        echo -e "${RED}   - ${module}${NC}"
    done
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Success! Generated all WebSocket types from per-module AsyncAPI specifications${NC}"
echo -e "${GREEN}📁 Output: ./src/clients/ws-types-*/${NC}"
echo -e "${GREEN}   - Import: import { Bar, SubscriptionRequest } from '@/clients/ws-types-{module}'${NC}"
echo ""
exit 0
