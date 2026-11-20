"""Servico de criptografia e integridade."""

import base64
import hashlib
import hmac
import os
from cryptography.fernet import Fernet
from pathlib import Path

from .config import settings
from .utils import print_error, print_warning, print_info


class CryptoService:
    """Servico de criptografia (Fernet) e assinatura (HMAC)."""

    def __init__(self, key: bytes | None = None):
        if key is None:
            key = self._get_or_generate_key()
        self._fernet = Fernet(key)
        self._hmac_key = hashlib.sha256(key).digest()[:32]

    def _get_or_generate_key(self) -> bytes:
        """Pega chave do .env ou gera nova."""
        if settings.fernet_key:
            try:
                key = settings.fernet_key.strip().encode()
                # Fernet expects base64-encoded 32-byte key
                # The key from .env is already base64, so just validate it
                if len(key) not in (43, 44):  # 32 bytes = 43-44 chars base64
                    raise ValueError(f"Invalid key length: {len(key)}")
                return key
            except Exception as e:
                print_warning(f"FERNET_KEY invalida no .env: {e}, gerando nova...")

        # Gera nova chave
        key = Fernet.generate_key()
        print_warning(f"Nova chave Fernet gerada: {key.decode()}")
        print_info("Adicione ao .env: FERNET_KEY=<chave>")
        return key

    # ==================== FERNET ENCRYPTION ====================

    def encrypt(self, plaintext: str) -> str:
        """Criptografa string (retorna base64)."""
        if not plaintext:
            return ""
        token = self._fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(token).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Descriptografa string (base64 -> plaintext)."""
        if not ciphertext:
            return ""
        try:
            token = base64.urlsafe_b64decode(ciphertext.encode())
            return self._fernet.decrypt(token).decode()
        except Exception as e:
            raise ValueError(f"Falha ao descriptografar: {e}")

    def encrypt_bytes(self, data: bytes) -> bytes:
        return self._fernet.encrypt(data)

    def decrypt_bytes(self, token: bytes) -> bytes:
        return self._fernet.decrypt(token)

    # ==================== HASH / INTEGRITY ====================

    def hash_sha256(self, data: str | bytes) -> str:
        """SHA-256 hex digest."""
        if isinstance(data, str):
            data = data.encode()
        return hashlib.sha256(data).hexdigest()

    def hash_sha256_b64(self, data: str | bytes) -> str:
        """SHA-256 base64."""
        if isinstance(data, str):
            data = data.encode()
        return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode()

    # ==================== HMAC SIGNING ====================

    def sign(self, data: str | bytes) -> str:
        """Assina dados com HMAC-SHA256 (retorna base64)."""
        if isinstance(data, str):
            data = data.encode()
        sig = hmac.new(self._hmac_key, data, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(sig).decode()

    def verify(self, data: str | bytes, signature: str) -> bool:
        """Verifica assinatura HMAC."""
        if isinstance(data, str):
            data = data.encode()
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)

    # ==================== KEY MANAGEMENT ====================

    @staticmethod
    def generate_key() -> str:
        """Gera nova chave Fernet (base64)."""
        return Fernet.generate_key().decode()

    @staticmethod
    def generate_key_file(path: str = ".fernet_key") -> str:
        """Gera chave e salva em arquivo."""
        key = Fernet.generate_key().decode()
        Path(path).write_text(key)
        print_info(f"Chave salva em: {path}")
        return key


# Instancia global (lazy)
_crypto_instance: CryptoService | None = None


def get_crypto() -> CryptoService:
    """Singleton do CryptoService."""
    global _crypto_instance
    if _crypto_instance is None:
        _crypto_instance = CryptoService()
    return _crypto_instance