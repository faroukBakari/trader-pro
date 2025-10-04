#!/bin/bash
# Script to generate Vue.js client from OpenAPI specification

set -e

echo "🚀 Generating Vue.js client from OpenAPI specification..."

# Create clients directory if it doesn't exist
mkdir -p clients

# Start the API server temporarily if not running
API_RUNNING=$(curl -s http://localhost:8000/api/v1/health > /dev/null 2>&1 && echo "true" || echo "false")

if [ "$API_RUNNING" = "false" ]; then
    echo "📡 Starting API server..."
    poetry run uvicorn trading_api.main:app --host 0.0.0.0 --port 8000 &
    API_PID=$!
    sleep 3
fi

# Download OpenAPI specification
echo "📥 Downloading OpenAPI specification..."
curl -s http://localhost:8000/api/v1/openapi.json -o openapi.json

# Create OpenAPI 3.0 version for Python client compatibility
echo "🔄 Creating OpenAPI 3.0 compatible version..."
jq '.openapi = "3.0.3"' openapi.json > openapi-3.0.json

# Generate TypeScript/Vue.js client using openapi-generator
echo "🔧 Generating Vue.js TypeScript client..."
npx @openapitools/openapi-generator-cli generate \
  -i openapi.json \
  -g typescript-axios \
  -o ./clients/vue-client \
  --additional-properties=supportsES6=true,typescriptThreePlus=true,withInterfaces=true

# Alternative: Generate using openapi-python-client for comparison
echo "🔧 Generating Python client (for reference)..."
cd clients
if poetry run openapi-python-client generate --path ../openapi-3.0.json; then
    # Rename the generated directory to python-client for consistency
    if [ -d "trading-api-client" ]; then
        mv trading-api-client python-client
    elif [ -d "my-test-api-client" ]; then
        mv my-test-api-client python-client
    fi
    echo "✅ Python client generated successfully"
else
    echo "⚠️  Python client generation failed (likely due to OpenAPI 3.1 compatibility)"
    echo "   Consider using the Vue.js TypeScript client or other generators"
fi
cd ..

# Stop the temporary API server if we started it
if [ "$API_RUNNING" = "false" ] && [ ! -z "$API_PID" ]; then
    echo "🛑 Stopping temporary API server..."
    kill $API_PID
fi

echo "✅ Client generation complete!"
echo "📂 Vue.js client: ./clients/vue-client"
echo "📂 Python client: ./clients/python-client"
echo "📄 OpenAPI spec: ./openapi.json"
