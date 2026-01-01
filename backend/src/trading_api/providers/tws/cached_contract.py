"""CachedContract - Combined contract description and details for caching.

This module provides a unified contract cache that can be populated from either
ContractDescription (partial, from symbol search) or ContractDetails (full).
"""

from dataclasses import dataclass, field

from ibapi.contract import ContractDescription, ContractDetails

from trading_api.providers.tws.tws_mappers import ticker_name


@dataclass
class CachedContract(ContractDetails):
    """Combined contract description and details for caching.

    Can be created from either ContractDescription (partial) or ContractDetails (full).
    The `has_full_details` flag indicates whether full contract details are available.

    Attributes:
        derivativeSecTypes: List of derivative security types (from ContractDescription)
        has_full_details: True if populated from ContractDetails, False if from ContractDescription
    """

    derivativeSecTypes: list[str] = field(default_factory=list)
    has_full_details: bool = False
    _ticker: str = ""

    # === Factory Methods ===

    @staticmethod
    def from_contract_details(details: ContractDetails) -> "CachedContract":
        """Create a CachedContract from a ContractDetails instance.

        Copies all attributes from the source ContractDetails and marks
        has_full_details=True.

        Args:
            details: The ContractDetails to convert

        Returns:
            A new CachedContract with full details
        """
        instance = CachedContract()
        instance.__dict__.update(details.__dict__)
        instance.has_full_details = True
        instance._ticker = ticker_name(instance.contract)
        return instance

    @staticmethod
    def from_contract_description(desc: ContractDescription) -> "CachedContract":
        """Create a CachedContract from a ContractDescription instance.

        Only copies contract and derivativeSecTypes fields. Other ContractDetails
        fields remain at defaults. Marks has_full_details=False.

        Args:
            desc: The ContractDescription to convert

        Returns:
            A new CachedContract with partial details
        """
        instance = CachedContract()
        instance.contract = desc.contract
        instance.derivativeSecTypes = desc.derivativeSecTypes
        instance.has_full_details = False
        instance._ticker = ticker_name(instance.contract)
        return instance

    # === Conversion Methods ===

    def to_contract_details(self) -> ContractDetails:
        """Export as a ContractDetails instance.

        Creates a new ContractDetails with all inherited attributes copied,
        excluding derivativeSecTypes and has_full_details.

        Returns:
            A new ContractDetails instance
        """
        details = ContractDetails()
        for key, value in self.__dict__.items():
            if key not in ("derivativeSecTypes", "has_full_details") and hasattr(
                details, key
            ):
                setattr(details, key, value)
        return details

    def to_contract_description(self) -> ContractDescription:
        """Export as a ContractDescription instance.

        Creates a new ContractDescription with contract and derivativeSecTypes.

        Returns:
            A new ContractDescription instance
        """
        desc = ContractDescription()
        desc.contract = self.contract
        desc.derivativeSecTypes = self.derivativeSecTypes
        return desc

    def update_from_details(self, details: ContractDetails) -> None:
        """Update this CachedContract with full details.

        Used to upgrade a partial cache entry (from ContractDescription)
        to full details (from ContractDetails).

        Args:
            details: The ContractDetails to merge
        """
        # Preserve derivativeSecTypes before update
        derivative_sec_types = self.derivativeSecTypes
        self.__dict__.update(details.__dict__)
        self.derivativeSecTypes = derivative_sec_types
        self._ticker = ticker_name(self.contract)
        self.has_full_details = True

    @property
    def con_id(self) -> int:
        """Get the contract ID (conId) for cache key purposes."""
        return self.contract.conId

    @property
    def ticker(self) -> str:
        """Get the ticker name for logging purposes."""
        try:
            if not self._ticker:
                self._ticker = ticker_name(self.contract)
        finally:
            return self._ticker

    def matches(self, ticker: str) -> bool:
        """Check if this cached contract matches the given contract.

        Args:
            contract: The Contract to compare against
        Returns:
            True if matches, False otherwise
        """
        return ticker.startswith(self.ticker)
