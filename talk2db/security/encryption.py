from typing import Optional
from cryptography.fernet import Fernet


class CredentialVault:
    """Ephemeral session-scoped credential store; keys are held in memory only."""

    def __init__(self, key: Optional[bytes] = None):
        self._key = key or Fernet.generate_key()
        self._cipher = Fernet(self._key)
        self._encrypted_store: dict[str, bytes] = {}

    def store_secret(self, identifier: str, secret_val: str) -> None:
        if not secret_val:
            return
        if self._cipher is None:
            self._key = Fernet.generate_key()
            self._cipher = Fernet(self._key)
        self._encrypted_store[identifier] = self._cipher.encrypt(secret_val.encode("utf-8"))

    def get_secret(self, identifier: str) -> Optional[str]:
        if self._cipher is None:
            return None
        token = self._encrypted_store.get(identifier)
        if not token:
            return None
        return self._cipher.decrypt(token).decode("utf-8")

    def purge(self) -> None:
        self._encrypted_store.clear()
        self._key = Fernet.generate_key()
        self._cipher = Fernet(self._key)
