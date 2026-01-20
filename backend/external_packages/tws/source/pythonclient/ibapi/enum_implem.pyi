"""Type stubs for ibapi.enum_implem module."""

class Enum:
    """Simple enum implementation."""

    idx2name: dict[int, str]

    def __init__(self, *args: str) -> None: ...
    def __getattr__(self, name: str) -> int: ...
    def toStr(self, idx: int | None) -> str: ...
