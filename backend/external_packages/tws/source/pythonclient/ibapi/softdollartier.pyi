"""Type stubs for ibapi.softdollartier module."""

from ibapi.object_implem import Object

class SoftDollarTier(Object):
    name: str
    val: str
    displayName: str
    def __init__(
        self, name: str = "", val: str = "", displayName: str = ""
    ) -> None: ...
    def __str__(self) -> str: ...
