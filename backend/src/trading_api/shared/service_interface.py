from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from trading_api.models.common import (
    CapabilitySpec,
    DatastoreCapabilitySpec,
    ProviderCapabilitySpec,
)
from trading_api.models.exceptions import CommonException
from trading_api.models.health import HealthResponse
from trading_api.models.versioning import APIMetadata, VersionInfo
from trading_api.shared import DatastoreInterface
from trading_api.shared.provider_interface import Provider


class ServiceInterface(ABC):
    def __init__(
        self,
        module_dir: Path,
        *,  # Force keyword-only
        providers: list[Provider] | None = None,
        datastores: list[DatastoreInterface] | None = None,
    ) -> None:
        """Initialize service.

        Args:
            module_dir: Module directory path
            providers: Provider instances for required capabilities
            datastores: Optional shared datastores for repository injection

        Raises:
            CommonException: If required capability not satisfied
        """
        providers = providers or []
        datastores = datastores or []

        assert (
            datastores
        ), "At least one datastore must be provided to the service layer."

        super().__init__()
        self.module_dir = module_dir
        self.datastores = datastores

        # Build capability map and fail-fast validate
        self._capability_map = self._resolve_provider_capabilities(providers or [])

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
    def provider_capabilities(cls) -> list[ProviderCapabilitySpec]:
        """Return required provider capabilities for this service.

        [CLASSMETHOD]: Static declaration for app startup analysis.

        Returns:
            List of provider capability requirements

        Examples:
            >>> AuthService.provider_capabilities()
            [ProviderCapabilitySpec(name="auth")]
        """
        ...

    @classmethod
    def datastore_capabilities(cls) -> list[DatastoreCapabilitySpec]:
        """Return required datastore capabilities for this service.

        [CLASSMETHOD]: Static declaration for app startup analysis.
        [DEFAULT]: Returns empty list - no special capabilities required.

        Override in services that need specific datastore features:
        - "persistence": Data survives restarts
        - "transactions": Atomic multi-operation support
        - "timeseries": Time-range queries (get_time_range, set_batch)
        - "rangequery": Gap detection (get_missing_ranges)
        - "exclusion": Database-level exclusion constraints

        Returns:
            List of datastore capability requirements

        Examples:
            >>> DatafeedService.datastore_capabilities()
            [DatastoreCapabilitySpec(name="timeseries")]
        """
        return []

    # Backward compatibility alias - will be deprecated
    @classmethod
    def capabilities(cls) -> list[CapabilitySpec]:
        """Deprecated: Use provider_capabilities() instead."""
        return cls.provider_capabilities()

    def _resolve_provider_capabilities(
        self, providers: list[Provider]
    ) -> dict[str, list[Provider]]:
        """Resolve and cache capability → provider mapping.

        [FAIL-FAST]: Validates at initialization, not at request time.

        Raises:
            CommonException: If required capability not found
        """

        capability_map: dict[str, list[Provider]] = {}

        for req_cap in self.provider_capabilities():
            provs = [
                provider
                for provider in providers
                if any(
                    req_cap.matches(prov_cap) for prov_cap in provider.capabilities()
                )
            ]

            if not provs:
                raise CommonException(
                    code="COMMON_CAPABILITY_NOT_FOUND",
                    message=(
                        f"Service '{self.module_name}' requires capability "
                        f"'{req_cap}' but no provider found. "
                        f"Available providers: {[p.name for p in providers]}"
                    ),
                )

            capability_map[req_cap.name] = provs

        return capability_map

    def _resolve_datastore_capabilities(self) -> DatastoreInterface | None:
        """Select datastore based on capability requirements.

        [FAIL-FAST]: Validates at initialization, not at request time.

        Returns:
            Best matching datastore, or None if no requirements

        Raises:
            CommonException: If required capability not found
        """
        required_caps = self.datastore_capabilities()

        # No requirements? Return None (caller can use default)
        if not required_caps:
            return None

        # Score each datastore by how many required capabilities it provides
        best_datastore: DatastoreInterface | None = None
        best_score = -1

        for datastore in self.datastores:
            provided_caps = datastore.capabilities()
            score = 0
            missing_required: list[str] = []

            for req_cap in required_caps:
                matched = any(req_cap.matches(prov_cap) for prov_cap in provided_caps)
                if matched:
                    score += 1
                elif not req_cap.optional:
                    missing_required.append(req_cap.name)

            # If missing any required capabilities, skip this datastore
            if missing_required:
                continue

            # Best score wins
            if score > best_score:
                best_score = score
                best_datastore = datastore

        if best_datastore is None:
            required_names = [c.name for c in required_caps if not c.optional]
            available_caps = {
                type(ds).__name__: [c.name for c in ds.capabilities()]
                for ds in self.datastores
            }
            raise CommonException(
                code="COMMON_DATASTORE_CAPABILITY_NOT_FOUND",
                message=(
                    f"Service '{self.module_name}' requires datastore capabilities "
                    f"{required_names} but no matching datastore found. "
                    f"Available: {available_caps}"
                ),
            )

        return best_datastore

    def get_capability_provider(
        self, capability_name: str, preferred_provider: str | None = None
    ) -> Provider:
        """Get provider for specific capability (cached lookup).

        Args:
            capability_name: Name of capability to get

        Returns:
            Provider instance

        Raises:
            RuntimeError: If capability not in map (should never happen)

        [PERFORMANCE]: O(1) lookup after initialization.
        """
        providers = self._capability_map.get(capability_name)
        if not providers:
            raise RuntimeError(
                f"Capability '{capability_name}' not initialized. "
                "This should never happen - validation should occur at init."
            )
        if preferred_provider:
            providers = [
                provider
                for provider in providers
                if provider.name == preferred_provider
            ]
            if not providers:
                raise RuntimeError(
                    f"Preferred provider '{preferred_provider}' for capability "
                    f"'{capability_name}' not found."
                )
        return next(iter(providers))

    def get_featured_datastore(self, *required_capabilities: str) -> DatastoreInterface:
        """Get a datastore that provides specific capabilities.

        Args:
            *required_capabilities: Capability names needed (e.g., "timeseries", "transactions")

        Returns:
            DatastoreInterface: First datastore matching all requirements

        Raises:
            CommonException: If no datastore provides all required capabilities

        Examples:
            >>> ds = self.get_featured_datastore("timeseries")
            >>> ds = self.get_featured_datastore("transactions", "persistence")
        """
        for datastore in self.datastores:
            provided = {cap.name for cap in datastore.capabilities()}
            if all(req in provided for req in required_capabilities):
                return datastore

        available_caps = {
            type(ds).__name__: [c.name for c in ds.capabilities()]
            for ds in self.datastores
        }
        raise CommonException(
            code="COMMON_DATASTORE_CAPABILITY_NOT_FOUND",
            message=(
                f"No datastore provides capabilities {list(required_capabilities)}. "
                f"Available: {available_caps}"
            ),
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

    def shutdown(self) -> None:
        """Perform any necessary cleanup on service shutdown."""
        """Perform any necessary cleanup on service shutdown."""
