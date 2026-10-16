"""utils/security.py - Password hashing (PBKDF2-SHA256, Python standard library)."""
import base64
import hashlib
import hmac
import secrets

ITERATIONS = 310_000
MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, digest_b64 = str(stored).split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def password_problem(password: str):
    """Returns a message if the password is too weak, else None."""
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if password.isdigit() or password.isalpha():
        return "Mix letters with numbers or symbols."
    return None
