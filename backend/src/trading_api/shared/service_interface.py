from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from trading_api.models.common import CapabilitySpec
from trading_api.models.health import HealthResponse
from trading_api.models.versioning import APIMetadata, VersionInfo
from trading_api.shared.provider_interface import Provider


class ServiceInterface(ABC):
    def __init__(
        self,
        module_dir: Path,
        *,  # Force keyword-only
        providers: list["Provider"] | None = None,
    ) -> None:
        """Initialize service.

        Args:
            module_dir: Module directory path
            providers: Provider instances for required capabilities

        Raises:
            CapabilityNotFoundError: If required capability not satisfied
        """
        super().__init__()
        self.module_dir = module_dir
        self._providers = providers or []

        # Build capability map and fail-fast validate
        self._capability_map: dict[str, "Provider"] = {}
        self._resolve_capabilities()

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

    @classmethod
    @abstractmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Return required capabilities for this service.

        [CLASSMETHOD]: Static declaration for app startup analysis.

        Returns:
            List of capability requirements

        Examples:
            >>> AuthService.capabilities()
            [CapabilitySpec(name="auth")]
        """
        ...

    def _resolve_capabilities(self) -> None:
        """Resolve and cache capability → provider mapping.

        [FAIL-FAST]: Validates at initialization, not at request time.

        Raises:
            CapabilityNotFoundError: If required capability not found
        """
        from trading_api.models.common import CapabilityNotFoundError

        required_capabilities = self.capabilities()

        for req_cap in required_capabilities:
            matched = False

            for provider in self._providers:
                # Check if provider offers matching capability
                for prov_cap in provider.capabilities():
                    if req_cap.matches(prov_cap):
                        self._capability_map[req_cap.name] = provider
                        matched = True
                        break

                if matched:
                    break

            if not matched:
                raise CapabilityNotFoundError(
                    f"Service '{self.module_name}' requires capability "
                    f"'{req_cap}' but no provider found. "
                    f"Available providers: {[p.name for p in self._providers]}"
                )

    def get_capability_provider(self, capability_name: str) -> Provider:
        """Get provider for specific capability (cached lookup).

        Args:
            capability_name: Name of capability to get

        Returns:
            Provider instance

        Raises:
            RuntimeError: If capability not in map (should never happen)

        [PERFORMANCE]: O(1) lookup after initialization.
        """
        provider = self._capability_map.get(capability_name)
        if provider is None:
            raise RuntimeError(
                f"Capability '{capability_name}' not initialized. "
                "This should never happen - validation should occur at init."
            )
        return provider

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

    def shutdown(self) -> None:
        """Perform any necessary cleanup on service shutdown."""
