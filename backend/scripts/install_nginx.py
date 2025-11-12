#!/usr/bin/env python3
"""Install standalone nginx binary for multi-process backend.

This script automatically downloads and installs the latest stable nginx
binary from https://github.com/jirutka/nginx-binaries based on the current OS.

The binary is installed to backend/.local/bin/ and can be used for config
validation and running the multi-process backend in development.

Usage:
    python scripts/install_nginx.py
    python scripts/install_nginx.py --version 1.26.x
    python scripts/install_nginx.py --check-only

Features:
    - Auto-detects OS and architecture
    - Downloads pre-built static binaries (no compilation)
    - No sudo required
    - Works on Linux (x86_64, aarch64), macOS (x86_64), Windows (x86_64)
"""

import argparse
import hashlib
import json
import platform
import sys
import urllib.request
from pathlib import Path
from typing import Optional


class NginxInstaller:
    """Installer for standalone nginx binary."""

    REPO_URL = "https://jirutka.github.io/nginx-binaries"
    INSTALL_DIR = Path(__file__).parent.parent / ".local" / "bin"

    def __init__(self, version: str = "1.28.x"):
        """Initialize installer.

        Args:
            version: Nginx version pattern (e.g., "1.28.x" for latest 1.28.x)
        """
        self.version = version
        self.os_name = self._detect_os()
        self.arch = self._detect_arch()

    def _detect_os(self) -> str:
        """Detect current operating system.

        Returns:
            OS name compatible with nginx-binaries repository
        """
        system = platform.system().lower()
        if system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        else:
            raise RuntimeError(f"Unsupported OS: {system}")

    def _detect_arch(self) -> str:
        """Detect current architecture.

        Returns:
            Architecture name compatible with nginx-binaries repository
        """
        machine = platform.machine().lower()

        # Map Python platform names to nginx-binaries arch names
        arch_map = {
            "x86_64": "x86_64",
            "amd64": "x86_64",
            "arm64": "aarch64",
            "aarch64": "aarch64",
            "armv7l": "armv7",
        }

        arch = arch_map.get(machine)
        if not arch:
            raise RuntimeError(f"Unsupported architecture: {machine}")

        return arch

    def _fetch_index(self) -> list[dict]:
        """Fetch repository index of available binaries.

        Returns:
            List of available binary metadata
        """
        index_url = f"{self.REPO_URL}/index.json"

        try:
            with urllib.request.urlopen(index_url) as response:
                data = response.read()
                index_data = json.loads(data)

                # The index has a 'contents' array
                if isinstance(index_data, dict) and "contents" in index_data:
                    return index_data["contents"]
                elif isinstance(index_data, list):
                    return index_data
                else:
                    raise ValueError(f"Unexpected index format: {type(index_data)}")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch nginx index: {e}")

    def _find_latest_version(self, index: list[dict]) -> Optional[dict]:
        """Find the latest nginx version matching the pattern.

        Args:
            index: Repository index

        Returns:
            Binary metadata or None if not found
        """
        # Filter for nginx binaries matching OS and arch
        # Variant can be empty string or "default"
        candidates = [
            entry
            for entry in index
            if entry["name"] == "nginx"
            and entry["os"] == self.os_name
            and entry["arch"] == self.arch
            and entry.get("variant", "default") in ("", "default")
        ]

        if not candidates:
            return None

        # Parse version pattern (e.g., "1.28.x" -> major=1, minor=28)
        parts = self.version.split(".")
        major = int(parts[0]) if parts[0] != "x" else None
        minor = int(parts[1]) if len(parts) > 1 and parts[1] != "x" else None

        # Filter by version pattern
        if major is not None:
            candidates = [e for e in candidates if e["version"].startswith(f"{major}.")]

        if minor is not None:
            candidates = [
                e for e in candidates if e["version"].startswith(f"{major}.{minor}.")
            ]

        if not candidates:
            return None

        # Sort by version and return the latest
        candidates.sort(
            key=lambda x: tuple(map(int, x["version"].split("."))), reverse=True
        )
        return candidates[0]

    def _download_binary(self, url: str, dest: Path) -> None:
        """Download binary file with progress indication.

        Args:
            url: URL to download from
            dest: Destination file path
        """
        print(f"Downloading from: {url}")

        try:
            with urllib.request.urlopen(url) as response:
                total_size = int(response.headers.get("content-length", 0))
                downloaded = 0
                chunk_size = 8192

                dest.parent.mkdir(parents=True, exist_ok=True)

                with open(dest, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(
                                f"\rProgress: {percent:.1f}% ({downloaded}/{total_size} bytes)",
                                end="",
                            )

                print()  # New line after progress

        except Exception as e:
            if dest.exists():
                dest.unlink()
            raise RuntimeError(f"Failed to download binary: {e}")

    def _verify_checksum(self, binary_path: Path, checksum_url: str) -> bool:
        """Verify downloaded binary checksum.

        Args:
            binary_path: Path to downloaded binary
            checksum_url: URL to SHA1 checksum file

        Returns:
            True if checksum matches
        """
        try:
            # Download checksum
            with urllib.request.urlopen(checksum_url) as response:
                expected_checksum = response.read().decode().strip().split()[0]

            # Calculate actual checksum
            sha1 = hashlib.sha1()
            with open(binary_path, "rb") as f:
                while chunk := f.read(8192):
                    sha1.update(chunk)
            actual_checksum = sha1.hexdigest()

            if actual_checksum != expected_checksum:
                print(f"❌ Checksum mismatch!")
                print(f"   Expected: {expected_checksum}")
                print(f"   Actual:   {actual_checksum}")
                return False

            print(f"✅ Checksum verified: {actual_checksum}")
            return True

        except Exception as e:
            print(f"⚠️  Warning: Could not verify checksum: {e}")
            return True  # Continue anyway if checksum verification fails

    def install(self) -> Path:
        """Install nginx binary.

        Returns:
            Path to installed nginx binary
        """
        print(f"🔍 Detecting system: {self.os_name} {self.arch}")
        print(f"📦 Looking for nginx version: {self.version}")

        # Fetch index
        print("📡 Fetching binary index...")
        index = self._fetch_index()

        # Find matching version
        binary_info = self._find_latest_version(index)
        if not binary_info:
            raise RuntimeError(
                f"No nginx binary found for {self.os_name}/{self.arch} "
                f"matching version {self.version}"
            )

        version = binary_info["version"]
        print(f"✅ Found nginx {version}")

        # Prepare paths
        binary_filename = binary_info["filename"]
        if self.os_name == "windows" and not binary_filename.endswith(".exe"):
            binary_filename += ".exe"

        binary_url = f"{self.REPO_URL}/{binary_filename}"
        checksum_url = f"{binary_url}.sha1"

        dest_filename = "nginx.exe" if self.os_name == "windows" else "nginx"
        dest_path = self.INSTALL_DIR / dest_filename

        # Check if already installed
        if dest_path.exists():
            print(f"⚠️  nginx already installed at: {dest_path}")
            response = input("Overwrite? [y/N] ").strip().lower()
            if response != "y":
                print("Installation cancelled.")
                return dest_path

        # Download binary
        self._download_binary(binary_url, dest_path)

        # Verify checksum
        self._verify_checksum(dest_path, checksum_url)

        # Make executable (Unix-like systems)
        if self.os_name != "windows":
            dest_path.chmod(0o755)

        print(f"✅ nginx {version} installed to: {dest_path}")

        return dest_path

    def check_installation(self) -> Optional[Path]:
        """Check if nginx is already installed.

        Returns:
            Path to nginx binary if installed, None otherwise
        """
        dest_filename = "nginx.exe" if self.os_name == "windows" else "nginx"
        dest_path = self.INSTALL_DIR / dest_filename

        if dest_path.exists():
            return dest_path
        return None


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Install standalone nginx binary for multi-process backend"
    )
    parser.add_argument(
        "--version",
        default="1.28.x",
        help="Nginx version pattern (default: 1.28.x - latest stable)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check if nginx is installed, don't install",
    )

    args = parser.parse_args()

    try:
        installer = NginxInstaller(version=args.version)

        if args.check_only:
            nginx_path = installer.check_installation()
            if nginx_path:
                print(f"✅ nginx is installed at: {nginx_path}")
                # Test execution
                import subprocess

                result = subprocess.run(
                    [str(nginx_path), "-v"],
                    capture_output=True,
                    text=True,
                )
                print(result.stderr.strip())
                return 0
            else:
                print("❌ nginx is not installed")
                print(f"Run: python scripts/install_nginx.py")
                return 1

        # Install nginx
        nginx_path = installer.install()

        # Test installation
        print("\n🧪 Testing nginx installation...")
        import subprocess

        result = subprocess.run(
            [str(nginx_path), "-v"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"✅ {result.stderr.strip()}")
            print(f"\n📍 nginx installed at: {nginx_path}")
            print(f'💡 Add to PATH: export PATH="{nginx_path.parent}:$PATH"')
            return 0
        else:
            print(f"❌ nginx installation failed: {result.stderr}")
            return 1

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
