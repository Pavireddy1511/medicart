import re

MOBILE_RE = re.compile(r"^[6-9]\d{9}$")
PINCODE_RE = re.compile(r"^[1-9]\d{5}$")


def normalise_mobile(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not MOBILE_RE.match(digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return digits


def validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value) > 128:
        raise ValueError("Password is too long")
    if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain at least one letter and one number")
    return value


def validate_pincode(value: str) -> str:
    value = (value or "").strip()
    if not PINCODE_RE.match(value):
        raise ValueError("Enter a valid 6-digit PIN code")
    return value
