"""Tests for PathPilot crypto module."""

import pytest
from pathpilot.crypto import CryptoService


class TestCryptoService:
    """Test CryptoService class."""

    def test_singleton_pattern(self):
        service1 = CryptoService()
        service2 = CryptoService()
        assert service1 is service2

    def test_encrypt_decrypt_roundtrip(self):
        service = CryptoService()
        plaintext = "my-secret-value-123"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_deterministic_different(self):
        service = CryptoService()
        plaintext = "test-value"
        enc1 = service.encrypt(plaintext)
        enc2 = service.encrypt(plaintext)
        assert enc1 != enc2
        assert service.decrypt(enc1) == plaintext
        assert service.decrypt(enc2) == plaintext

    def test_encrypt_empty_string(self):
        service = CryptoService()
        encrypted = service.encrypt("")
        decrypted = service.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_unicode(self):
        service = CryptoService()
        plaintext = "🔐秘密パスワード"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_decrypt_invalid_token(self):
        service = CryptoService()
        with pytest.raises(Exception):
            service.decrypt("invalid-token")

    def test_decrypt_wrong_key(self):
        service1 = CryptoService()
        encrypted = service1.encrypt("secret")

        # Create new service with different key
        from pathpilot.crypto import _crypto_service
        import pathpilot.crypto as crypto_module
        crypto_module._crypto_service = None
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("PATHPILOT_FERNET_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDE=")
            service2 = CryptoService()
            with pytest.raises(Exception):
                service2.decrypt(encrypted)

    def test_hash_data(self):
        service = CryptoService()
        data = "test-data"
        hash1 = service.hash_data(data)
        hash2 = service.hash_data(data)
        assert hash1 == hash2
        assert len(hash1) == 64

    def test_hash_different_data(self):
        service = CryptoService()
        hash1 = service.hash_data("data1")
        hash2 = service.hash_data("data2")
        assert hash1 != hash2

    def test_hmac_sign_verify(self):
        service = CryptoService()
        data = "important-data"
        signature = service.hmac_sign(data)
        assert service.hmac_verify(data, signature) is True

    def test_hmac_verify_fail(self):
        service = CryptoService()
        data = "important-data"
        signature = service.hmac_sign(data)
        assert service.hmac_verify("tampered-data", signature) is False

    def test_hmac_verify_wrong_key(self):
        service1 = CryptoService()
        data = "important-data"
        signature = service1.hmac_sign(data)

        from pathpilot.crypto import _crypto_service
        import pathpilot.crypto as crypto_module
        crypto_module._crypto_service = None
        with pytest.MonkeyPatch().context() as mp:
            mp.setenv("PATHPILOT_HMAC_KEY", "different-hmac-key-for-testing-32chars-long")
            service2 = CryptoService()
            assert service2.hmac_verify(data, signature) is False