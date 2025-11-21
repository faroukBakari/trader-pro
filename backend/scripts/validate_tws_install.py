#!/usr/bin/env python3
"""TWS API Installation Validation Script.

Validates that the TWS API (ibapi) and protobuf are correctly installed
with proper versions and all required components are accessible.
"""

import sys
from pathlib import Path


def validate_imports() -> bool:
    """Validate core TWS API imports."""
    print("=" * 60)
    print("VALIDATING TWS API INSTALLATION")
    print("=" * 60)
    print()

    # Test 1: Core imports
    print("1. Testing core imports...")
    try:
        from ibapi.client import EClient  # type: ignore[import-not-found]
        from ibapi.common import BarData  # type: ignore[import-not-found]
        from ibapi.contract import Contract  # type: ignore[import-not-found]
        from ibapi.order import Order  # type: ignore[import-not-found]
        from ibapi.wrapper import EWrapper  # type: ignore[import-not-found]

        print("   ✓ All core TWS imports successful")
    except ImportError as e:
        print(f"   ✗ Import failed: {e}")
        return False

    # Test 2: Version validation
    print("\n2. Checking TWS API version...")
    try:
        # Read version from API_VersionNum.txt
        api_version_file = (
            Path(__file__).parent.parent
            / "external_packages"
            / "tws"
            / "API_VersionNum.txt"
        )
        if api_version_file.exists():
            version = api_version_file.read_text().strip()
            print(f"   ✓ TWS API Version: {version}")
            expected_version = "10.37.02"
            if version != expected_version:
                print(
                    f"   ⚠ Warning: Expected version {expected_version}, "
                    f"found {version}"
                )
        else:
            print("   ⚠ Warning: Version file not found")
    except Exception as e:
        print(f"   ⚠ Warning: Could not read version: {e}")

    # Test 3: Protobuf validation
    print("\n3. Checking protobuf installation...")
    try:
        import google.protobuf

        pb_version = google.protobuf.__version__
        print(f"   ✓ Protobuf version: {pb_version}")

        expected_pb_version = "5.29.3"
        if pb_version != expected_pb_version:
            print(
                f"   ⚠ Warning: Expected protobuf {expected_pb_version}, "
                f"found {pb_version}"
            )
            print("   ⚠ TWS API requires protobuf 5.29.3 for compatibility")
    except ImportError as e:
        print(f"   ✗ Protobuf import failed: {e}")
        return False

    # Test 4: Protobuf compiled files
    print("\n4. Checking protobuf compiled files...")
    try:
        from ibapi.protobuf import (  # type: ignore[import-not-found]
            FAMessage_pb2,
            ibkr_acct_summary_pb2,
        )

        print("   ✓ Protobuf compiled files (_pb2.py) accessible")
    except ImportError as e:
        print(f"   ⚠ Warning: Some protobuf files not accessible: {e}")
        print("   (This is usually not critical)")

    # Test 5: Installation path verification
    print("\n5. Verifying installation path...")
    try:
        import ibapi  # type: ignore[import-not-found]

        ibapi_path = Path(ibapi.__file__).parent if ibapi.__file__ else Path("")
        print(f"   ✓ ibapi installed from: {ibapi_path}")

        # Check if it's from external_packages
        external_packages_path = (
            Path(__file__).parent.parent / "external_packages" / "tws"
        )
        if external_packages_path in ibapi_path.parents:
            print("   ✓ Using local TWS API from external_packages")
        else:
            print(
                "   ⚠ Warning: ibapi not loaded from external_packages "
                "(may be using different installation)"
            )
    except Exception as e:
        print(f"   ⚠ Warning: Could not verify path: {e}")

    # Test 6: Test EClient and EWrapper instantiation
    print("\n6. Testing component instantiation...")
    try:
        from ibapi.client import EClient  # pyright: ignore[reportMissingImports]
        from ibapi.wrapper import EWrapper  # pyright: ignore[reportMissingImports]

        class TestWrapper(EWrapper):
            pass

        class TestClient(EClient):
            pass

        # Try to create instances
        wrapper = TestWrapper()
        client = TestClient(wrapper)

        print("   ✓ EClient and EWrapper can be instantiated")
    except Exception as e:
        print(f"   ✗ Instantiation failed: {e}")
        return False

    return True


def main() -> int:
    """Run validation and return exit code."""
    try:
        success = validate_imports()

        print()
        print("=" * 60)
        if success:
            print("✓ ALL VALIDATION CHECKS PASSED")
            print("=" * 60)
            print()
            print("TWS API is correctly installed and ready for use.")
            return 0
        else:
            print("✗ VALIDATION FAILED")
            print("=" * 60)
            print()
            print("Please check the errors above and ensure:")
            print(
                "1. ibapi is installed from external_packages/tws/source/pythonclient"
            )
            print("2. protobuf version 5.29.3 is installed")
            print("3. All dependencies are properly resolved")
            return 1
    except Exception as e:
        print(f"\n✗ VALIDATION ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())
