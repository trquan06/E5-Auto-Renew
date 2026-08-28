"""
Test suite cho module mã hóa AES-GCM (crypto.py).
"""
import pytest
from app.config import settings
from app.crypto import encrypt, decrypt


def test_encryption_decryption():
    """Kiểm tra mã hóa và giải mã chuỗi plaintext bình thường."""
    original_text = "test_azure_client_secret_xyz123!@#"
    encrypted = encrypt(original_text, settings.AES_KEY)
    
    assert encrypted != original_text
    assert len(encrypted) > len(original_text)
    
    decrypted = decrypt(encrypted, settings.AES_KEY)
    assert decrypted == original_text


def test_unique_ciphertexts_for_same_plaintext():
    """Đảm bảo mỗi lần mã hóa sinh nonce ngẫu nhiên mới (ciphertexts khác nhau)."""
    text = "my_refresh_token_string"
    c1 = encrypt(text, settings.AES_KEY)
    c2 = encrypt(text, settings.AES_KEY)
    
    assert c1 != c2
    assert decrypt(c1, settings.AES_KEY) == text
    assert decrypt(c2, settings.AES_KEY) == text


def test_invalid_key_or_tampered_ciphertext():
    """Đảm bảo lỗi khi ciphertext bị can thiệp hoặc dùng sai key."""
    text = "secret_data"
    encrypted = encrypt(text, settings.AES_KEY)
    
    # Sai key
    wrong_key = b"0" * 32
    with pytest.raises(ValueError):
        decrypt(encrypted, wrong_key)
    
    # Ciphertext bị hỏng
    with pytest.raises(ValueError):
        decrypt(encrypted[:-4] + "AAAA", settings.AES_KEY)
