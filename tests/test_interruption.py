import pytest

from backend.audio.interruption import detect_interruption


def test_interruption_detection_is_explicitly_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        detect_interruption()
