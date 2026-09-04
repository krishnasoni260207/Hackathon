import pytest


pytestmark = pytest.mark.skip(
    reason="Stale-response prevention is planned for a later phase."
)


def test_stale_response_prevention_placeholder() -> None:
    pass
