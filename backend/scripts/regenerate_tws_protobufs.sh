#!/bin/bash
# Regenerate protobuf Python files and type stubs (.pyi) using grpcio-tools + mypy-protobuf
# This ensures type checkers (Pylance/Pyright) can properly validate protobuf imports
# Uses bundled protoc from grpcio-tools (no system protoc required)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/.."
TWS_SOURCE_DIR="$BACKEND_DIR/external_packages/tws/source"
PROTOBUF_DIR="$TWS_SOURCE_DIR/pythonclient/ibapi/protobuf"

echo "=========================================="
echo "Regenerating Protobuf Files with Type Stubs"
echo "=========================================="
echo

# Ensure we're in backend directory for all Poetry commands
cd "$BACKEND_DIR"

# Get Poetry venv paths
POETRY_VENV=$(poetry env info -p 2>/dev/null)
if [ -z "$POETRY_VENV" ]; then
    echo "✗ Error: Poetry virtual environment not found"
    echo "  Run: poetry install"
    exit 1
fi

POETRY_PYTHON="$POETRY_VENV/bin/python"
export PATH="$POETRY_VENV/bin:$PATH"

# Check if grpcio-tools is available
if ! "$POETRY_PYTHON" -c "import grpc_tools.protoc" 2>/dev/null; then
    echo "✗ Error: grpcio-tools not installed in Poetry environment"
    echo "  Install it with: poetry add --group dev grpcio-tools"
    exit 1
fi

echo "✓ grpcio-tools found (bundled protoc)"

# Check if mypy-protobuf is available
if ! "$POETRY_PYTHON" -c "import mypy_protobuf" 2>/dev/null; then
    echo "✗ Error: mypy-protobuf not installed in Poetry environment"
    echo "  Install it with: poetry add --group dev mypy-protobuf"
    exit 1
fi

echo "✓ mypy-protobuf found"

# Get versions
PROTOBUF_VERSION=$("$POETRY_PYTHON" -c "import google.protobuf; print(google.protobuf.__version__)")
GRPCIO_VERSION=$("$POETRY_PYTHON" -c "import grpc; print(grpc.__version__)")

echo "  - protobuf: $PROTOBUF_VERSION"
echo "  - grpcio-tools: $GRPCIO_VERSION"
echo

# Clean old generated files
echo "Cleaning old generated files..."
if [ -d "$PROTOBUF_DIR" ]; then
    rm -f "$PROTOBUF_DIR"/*_pb2.py
    rm -f "$PROTOBUF_DIR"/*_pb2.pyi
    echo "✓ Removed existing *_pb2.py and *_pb2.pyi files"
else
    mkdir -p "$PROTOBUF_DIR"
    echo "✓ Created protobuf directory"
fi

# Ensure __init__.py exists
if [ ! -f "$PROTOBUF_DIR/__init__.py" ]; then
    echo "Creating __init__.py..."
    touch "$PROTOBUF_DIR/__init__.py"
    echo "✓ Created __init__.py"
fi
echo

# Generate protobuf files WITH type stubs using grpcio-tools
echo "Generating protobuf files..."
cd "$TWS_SOURCE_DIR"

"$POETRY_PYTHON" -m grpc_tools.protoc \
  --proto_path=./proto \
  --python_out=./pythonclient/ibapi/protobuf \
  --mypy_out=./pythonclient/ibapi/protobuf \
  ./proto/*.proto

echo "✓ Generated protobuf files"
echo

# Fix imports: Convert absolute imports to relative imports in generated files
echo "Fixing import statements to use relative imports..."
for file in "$PROTOBUF_DIR"/*_pb2.py "$PROTOBUF_DIR"/*_pb2.pyi; do
    if [ -f "$file" ]; then
        # Replace "import XXX_pb2" with "from . import XXX_pb2"
        sed -i 's/^import \([A-Z][A-Za-z]*_pb2\)/from . import \1/g' "$file"
    fi
done

echo "✓ Fixed imports to use relative imports"
echo

# List generated files
echo "Generated Python files (.py):"
ls -1 "$PROTOBUF_DIR"/*_pb2.py 2>/dev/null | sed 's|.*/||' || echo "  (none found)"
echo

echo "Generated Type Stub files (.pyi):"
ls -1 "$PROTOBUF_DIR"/*_pb2.pyi 2>/dev/null | sed 's|.*/||' || echo "  (none found)"
echo

echo "=========================================="
echo "✓ Protobuf regeneration complete!"
echo "=========================================="
echo
echo "Type checkers (Pylance/Pyright) can now properly validate protobuf imports."
