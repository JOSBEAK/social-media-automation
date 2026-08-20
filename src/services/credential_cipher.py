import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipher:
    """Encrypt account secrets before they reach persistent storage."""

    def __init__(self, key: str | bytes | None = None, key_path: str | Path = "data/.credential_key"):
        resolved_key = key.encode() if isinstance(key, str) else key
        if resolved_key is None:
            resolved_key = self._load_or_create_key(Path(key_path))
        try:
            self._fernet = Fernet(resolved_key)
        except (ValueError, TypeError) as exc:
            raise ValueError("SOCIAL_CREDENTIAL_KEY is not a valid Fernet key") from exc

    @staticmethod
    def _load_or_create_key(path: Path) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return path.read_bytes().strip()
        except FileNotFoundError:
            key = Fernet.generate_key()
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as key_file:
                    key_file.write(key)
                return key
            except FileExistsError:
                return path.read_bytes().strip()

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Stored credentials cannot be decrypted with the configured key") from exc
