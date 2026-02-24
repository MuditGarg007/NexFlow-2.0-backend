"""Tests for app/utils/crypto.py"""
import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet

TEST_KEY = Fernet.generate_key().decode()


def _reset_fernet():
    import app.utils.crypto as c
    c._fernet = None


@pytest.fixture(autouse=True)
def clear_fernet():
    _reset_fernet()
    yield
    _reset_fernet()


def test_encrypt_decrypt_roundtrip():
    with patch("app.utils.crypto.settings") as mock_settings:
        mock_settings.FERNET_KEY = TEST_KEY
        from app.utils.crypto import encrypt_token, decrypt_token
        original = "super-secret-token"
        encrypted = encrypt_token(original)
        assert encrypted != original
        assert decrypt_token(encrypted) == original


def test_encrypt_produces_different_ciphertexts():
    """Fernet uses random IVs so same plaintext → different ciphertext each call."""
    with patch("app.utils.crypto.settings") as mock_settings:
        mock_settings.FERNET_KEY = TEST_KEY
        from app.utils.crypto import encrypt_token
        t1 = encrypt_token("token")
        t2 = encrypt_token("token")
        assert t1 != t2


def test_decrypt_wrong_key_raises():
    with patch("app.utils.crypto.settings") as mock_settings:
        mock_settings.FERNET_KEY = TEST_KEY
        from app.utils.crypto import encrypt_token
        encrypted = encrypt_token("data")

    _reset_fernet()
    other_key = Fernet.generate_key().decode()
    with patch("app.utils.crypto.settings") as mock_settings:
        mock_settings.FERNET_KEY = other_key
        from app.utils.crypto import decrypt_token
        with pytest.raises(Exception):
            decrypt_token(encrypted)


def test_decrypt_garbage_raises():
    with patch("app.utils.crypto.settings") as mock_settings:
        mock_settings.FERNET_KEY = TEST_KEY
        from app.utils.crypto import decrypt_token
        with pytest.raises(Exception):
            decrypt_token("not-valid-fernet-token")
