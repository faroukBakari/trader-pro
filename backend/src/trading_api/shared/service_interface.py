from abc import ABC
from datetime import datetime
from pathlib import Path

from trading_api.models.health import HealthResponse
from trading_api.models.versioning import APIMetadata, VersionInfo


class ServiceInterface(ABC):
    def __init__(self, module_dir: Path) -> None:
        super().__init__()
        self.module_dir = module_dir

        api_dir = self.module_dir / "api"
        available_versions: dict[str, VersionInfo] = {}
        current_version = "v1"  # Default

        if api_dir.exists() and api_dir.is_dir():
            # Discover version directories (v1, v2, etc.)
            version_dirs = [d.stem for d in api_dir.iterdir() if d.stem.startswith("v")]

            # Sort versions to find latest
            version_dirs.sort(key=lambda v: int(v[1:]))

            if version_dirs:
                current_version = version_dirs[-1]

                # Build VersionInfo for each discovered version
                for version in version_dirs:
                    available_versions[version] = VersionInfo(
                        version=version,
                        release_date="TBD",  # TODO: date of the last commit in that version file
                        status="stable" if version == current_version else "stable",
                        breaking_changes=[],
                        deprecation_notice=None,
                        sunset_date=None,
                    )

        self._api_metadata = APIMetadata(
            current_version=current_version,
            available_versions=available_versions,
            documentation_url=f"/api/{current_version}/{self.module_name}/docs",
            support_contact="support@trading-pro.nodomainyet",
        )

    @property
    def module_name(self) -> str:
        """Get the name of the module this service belongs to.

        Returns:
            str: The module name
        """
        return self.module_dir.name

    @property
    def api_metadata(self) -> APIMetadata:
        """Get the API metadata.

        Returns:
            APIMetadata: The API metadata
        """
        return self._api_metadata

    def get_health(self, current_version: str) -> HealthResponse:
        """Get the current health status of the API.

        Returns:
            HealthResponse: Health status with version information
        """

        return HealthResponse(
            status="ok",
            timestamp=datetime.utcnow().isoformat() + "Z",
            module_name=self.module_name,
            api_version=current_version,
        )

    def get_current_version_info(self, current_version: str) -> VersionInfo:
        """Get information about the current API version.

        Returns:
            VersionInfo: Current API version information
        """

        return self.api_metadata.available_versions[current_version]
