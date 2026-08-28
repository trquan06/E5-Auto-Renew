"""
Module mã hóa/giải mã AES-GCM cho token và secret an toàn.
Sử dụng AES-256-GCM (Galois/Counter Mode) - mã hóa xác thực (AEAD).
"""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, key: bytes) -> str:
    """
    Mã hóa chuỗi plaintext bằng AES-256-GCM.
    
    Returns:
        Chuỗi base64 chứa: nonce (12 bytes) + ciphertext + tag (16 bytes)
    """
    nonce = os.urandom(12)           # 96-bit nonce ngẫu nhiên
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    combined = nonce + ciphertext    # nonce || ciphertext+tag
    return base64.b64encode(combined).decode("utf-8")


def decrypt(ciphertext_b64: str, key: bytes) -> str:
    """
    Giải mã chuỗi được mã hóa bởi hàm encrypt().
    
    Returns:
        Chuỗi plaintext gốc.
    
    Raises:
        ValueError: Nếu dữ liệu bị hỏng hoặc key sai.
    """
    try:
        combined = base64.b64decode(ciphertext_b64)
        nonce = combined[:12]
        ciphertext = combined[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as exc:
        raise ValueError(f"Không thể giải mã: {exc}") from exc
