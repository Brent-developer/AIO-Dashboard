from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class BiometricTemplateSecurity:
    """Per-user encryption for biometric material at rest."""

    def __init__(self, master_key: str | bytes) -> None:
        self._master_key = master_key.encode() if isinstance(master_key, str) else master_key
        if len(self._master_key) < 16:
            raise ValueError("master_key must contain at least 16 bytes")

    def _fernet(self, user_id: str) -> Fernet:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=user_id.encode("utf-8"),
            iterations=100_000,
        )
        return Fernet(base64.urlsafe_b64encode(kdf.derive(self._master_key)))

    def encrypt(self, user_id: str, template_data: bytes) -> bytes:
        """Encrypt, then base64 encode for database storage."""
        token = self._fernet(user_id).encrypt(template_data)
        return base64.b64encode(token)

    def decrypt(self, user_id: str, stored_data: bytes) -> bytes:
        try:
            token = base64.b64decode(stored_data, validate=True)
            return self._fernet(user_id).decrypt(token)
        except (ValueError, InvalidToken) as exc:
            raise ValueError("template data is invalid or belongs to another user") from exc

    def encrypt_secret(self, name: str, value: str) -> bytes:
        return self.encrypt(f"secret:{name}", value.encode("utf-8"))

    def decrypt_secret(self, name: str, value: bytes) -> str:
        return self.decrypt(f"secret:{name}", value).decode("utf-8")
