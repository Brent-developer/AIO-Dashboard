from datetime import timezone

import pytest

from core.security import BiometricTemplateSecurity
from core.translation_layer import TranslationLayer


def test_template_round_trip_and_user_isolation():
    security = BiometricTemplateSecurity("a sufficiently long test master key")
    stored = security.encrypt("employee-1", b"biometric-template")
    assert stored != b"biometric-template"
    assert security.decrypt("employee-1", stored) == b"biometric-template"
    with pytest.raises(ValueError):
        security.decrypt("employee-2", stored)


def test_zkteco_event_normalization_is_utc_and_deterministic():
    raw = {"device_id": "device-1", "user_id": "42", "timestamp": 1_700_000_000, "status": "0", "verify_mode": "15"}
    event = TranslationLayer.normalize_event("zkteco", raw)
    duplicate = TranslationLayer.normalize_event("zkteco", raw)
    assert event.event_type == "CHECK_IN"
    assert event.verification_method == "FACE"
    assert event.timestamp.tzinfo == timezone.utc
    assert event.event_id == duplicate.event_id
