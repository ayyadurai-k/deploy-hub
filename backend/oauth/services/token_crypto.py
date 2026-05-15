from cryptography.fernet import Fernet
from django.conf import settings


def _cipher() -> Fernet:
    return Fernet(settings.FERNET_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _cipher().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _cipher().decrypt(ciphertext.encode()).decode()
