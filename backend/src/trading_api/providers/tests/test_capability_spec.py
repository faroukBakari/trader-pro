"""Test CapabilitySpec matching logic."""

from trading_api.models.common import CapabilitySpec


def test_capability_spec_matches_any_version() -> None:
    """Service requires auth (any version) → Provider v1 matches."""
    req = CapabilitySpec(name="auth")
    prov = CapabilitySpec(name="auth", version="v1")

    assert req.matches(prov)


def test_capability_spec_version_mismatch() -> None:
    """Service requires v1 → Provider v2 does NOT match."""
    req = CapabilitySpec(name="auth", version="v1")
    prov = CapabilitySpec(name="auth", version="v2")

    assert not req.matches(prov)


def test_capability_spec_name_mismatch() -> None:
    """Service requires auth → Broker provider does NOT match."""
    req = CapabilitySpec(name="auth")
    prov = CapabilitySpec(name="broker")

    assert not req.matches(prov)


def test_capability_spec_exact_version_match() -> None:
    """Service requires v1 → Provider v1 matches."""
    req = CapabilitySpec(name="auth", version="v1")
    prov = CapabilitySpec(name="auth", version="v1")

    assert req.matches(prov)


def test_capability_spec_string_representation() -> None:
    """Test string representation for logging."""
    cap_with_version = CapabilitySpec(name="auth", version="v1")
    cap_without_version = CapabilitySpec(name="auth")

    assert str(cap_with_version) == "auth:v1"
    assert str(cap_without_version) == "auth"


def test_capability_spec_immutable() -> None:
    """CapabilitySpec should be immutable (frozen dataclass)."""
    cap = CapabilitySpec(name="auth", version="v1")

    # Should raise AttributeError when trying to modify
    try:
        cap.name = "auth"  # type: ignore[misc]
        assert False, "Should not be able to modify frozen dataclass"
    except AttributeError:
        pass  # Expected
