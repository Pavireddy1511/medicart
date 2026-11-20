import re
import unicodedata

STRENGTH_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(mg|mcg|µg|ug|g|gm|ml|iu|%|units?|u)\b(?:\s*/\s*(\d+(?:[.,]\d+)?)\s*(mg|mcg|g|ml))?",
    re.IGNORECASE,
)

FORMULATION_WORDS = {
    "tab": "tablet",
    "tabs": "tablet",
    "tablet": "tablet",
    "tablets": "tablet",
    "t": "tablet",
    "cap": "capsule",
    "caps": "capsule",
    "capsule": "capsule",
    "capsules": "capsule",
    "syp": "syrup",
    "syr": "syrup",
    "syrup": "syrup",
    "inj": "injection",
    "injection": "injection",
    "oint": "ointment",
    "ointment": "ointment",
    "cream": "cream",
    "gel": "gel",
    "lotion": "lotion",
    "spray": "spray",
    "drop": "drops",
    "drops": "drops",
    "e/d": "eye drops",
    "susp": "suspension",
    "suspension": "suspension",
    "soln": "solution",
    "solution": "solution",
    "sachet": "sachet",
    "powder": "powder",
    "patch": "patch",
    "inhaler": "inhaler",
}

# Words that mark the end of a medicine name and the start of dosing instructions.
DOSING_WORDS = {
    "morning",
    "night",
    "evening",
    "afternoon",
    "noon",
    "bedtime",
    "daily",
    "day",
    "days",
    "week",
    "weeks",
    "month",
    "months",
    "od",
    "bd",
    "bid",
    "tds",
    "tid",
    "qid",
    "hs",
    "sos",
    "stat",
    "prn",
    "qd",
    "once",
    "twice",
    "thrice",
    "after",
    "before",
    "with",
    "food",
    "meal",
    "meals",
    "breakfast",
    "lunch",
    "dinner",
    "x",
    "for",
    "tot",
    "total",
    "times",
    "every",
    "each",
    "hourly",
    "hrs",
    "hours",
    "tab",
    "tabs",
    "cap",
    "caps",
    "tsp",
    "ml",
    "drops",
    "puff",
    "puffs",
    "sachet",
    "sachets",
    "apply",
    "locally",
}

PHARMACOPOEIA_WORDS = {"ip", "bp", "usp", "ph", "eur"}

FREQUENCY_PATTERNS = [
    r"\b\d\s*-\s*\d\s*-\s*\d(?:\s*-\s*\d)?\b",  # 1-0-1
    r"\b(?:od|bd|bid|tds|tid|qid|hs|sos|stat|qd|q\d+h|prn)\b",
    r"\b(?:once|twice|thrice|three times|four times)\s+(?:a|per)?\s*(?:day|daily|week)\b",
    r"\b(?:every|each)\s+\d+\s*(?:hours?|hrs?|days?)\b",
    r"\b\d?\s*(?:morning|night|bedtime|evening|afternoon)(?:\s*,?\s*\d?\s*(?:morning|night|evening|afternoon))*\b",
    r"\b(?:before|after)\s+(?:food|meals?|breakfast|lunch|dinner)\b",
]
FREQUENCY_RE = re.compile("|".join(FREQUENCY_PATTERNS), re.IGNORECASE)

DURATION_RE = re.compile(
    r"\b(?:x|for)?\s*([1-9]\d*)\s*(days?|weeks?|wks?|months?|mon|d|w|m)\b",
    re.IGNORECASE,
)

DOSAGE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?|half|one|two|½|1/2)\s*(tab(?:let)?s?|cap(?:sule)?s?|ml|tsp|tbsp|drops?|puffs?|sachets?)\b",
    re.IGNORECASE,
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SPACES = re.compile(r"\s+")

_LETTER_DIGIT = re.compile(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z][a-z])")
_FORM_DOT = re.compile(r"\b(tab|cap|syp|syr|inj|oint|susp|soln)\.(?=\S)", re.IGNORECASE)
_UNIT_TOKEN = re.compile(r"^([0-9OSIl]{1,4}(?:[.,][0-9OSIl]{1,3})?)(mg|mcg|ml|gm|g|iu)$", re.IGNORECASE)
_SQUASHED_GENERIC = re.compile(
    r"^([A-Za-z]{5,}?)(IP|BP|USP)?([0-9OSIl]{1,4}(?:[.,][0-9OSIl]{1,3})?)(MG|MCG|ML|G)$", re.IGNORECASE
)
_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "S": "5", "s": "5", "I": "1", "l": "1"})
_OCR_FIXES = [
    (re.compile(r"\b0[Dd]\b"), "OD"),
    (re.compile(r"\bB0\b"), "BD"),
    (re.compile(r"[　（]"), " ("),
    (re.compile(r"）"), ") "),
    (re.compile(r"[·•]"), " "),
]


def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch))


def _fix_token(token: str) -> str:
    """Repair OCR digit confusions inside strength tokens such as 'SOOMG' or '2.SMG'."""
    match = _UNIT_TOKEN.match(token)
    if match:
        return match.group(1).translate(_DIGIT_FIXES) + " " + match.group(2).lower()
    match = _SQUASHED_GENERIC.match(token)
    if match:
        name, pharmacopoeia, amount, unit = match.groups()
        parts = [name, pharmacopoeia or "", amount.translate(_DIGIT_FIXES), unit.lower()]
        return " ".join(p for p in parts if p)
    return token


def clean_ocr_line(value: str) -> str:
    """Undo common OCR damage: squashed spaces, 0/O confusion, glued prefixes."""
    text = value or ""
    for pattern, replacement in _OCR_FIXES:
        text = pattern.sub(replacement, text)
    text = re.sub(r"^(\d{1,2}[.)])(?=\S)", lambda m: m.group(1) + " ", text.strip())
    text = _FORM_DOT.sub(lambda m: m.group(1) + ". ", text)
    text = " ".join(_fix_token(token) for token in text.split())
    text = _LETTER_DIGIT.sub(" ", text)
    text = _CAMEL.sub(" ", text)
    text = re.sub(r"\b([1-9])\s*-\s*(\d)\s*-\s*(\d)\b", r"\1-\2-\3", text)
    text = re.sub(r"(\d)\s*,\s*(\d)", r"\1, \2", text)
    return _SPACES.sub(" ", text).strip()


def normalise_name(value: str) -> str:
    """Lower-case a medicine name and drop strength / formulation noise for matching."""
    text = strip_accents(value or "").lower()
    text = STRENGTH_RE.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text)
    tokens = [
        t
        for t in text.split()
        if t not in FORMULATION_WORDS
        and t not in PHARMACOPOEIA_WORDS
        and t not in {"rx", "tab"}
        and not t.isdigit()
    ]
    return _SPACES.sub(" ", " ".join(tokens)).strip()


def slugify(value: str) -> str:
    text = strip_accents(value).lower()
    text = _NON_ALNUM.sub("-", text).strip("-")
    return text or "item"


def extract_strength(value: str) -> str | None:
    match = STRENGTH_RE.search(value or "")
    if not match:
        return None
    return _SPACES.sub(" ", match.group(0)).strip()


def extract_formulation(value: str) -> str | None:
    for token in _NON_ALNUM.sub(" ", (value or "").lower()).split():
        if token in FORMULATION_WORDS:
            return FORMULATION_WORDS[token]
    return None


def extract_frequency(value: str) -> str | None:
    matches = [m.strip() for m in FREQUENCY_RE.findall(value or "") if m and m.strip()]
    if not matches:
        return None
    return ", ".join(dict.fromkeys(matches))


def extract_duration(value: str) -> str | None:
    match = DURATION_RE.search(value or "")
    return match.group(0).strip() if match else None


def extract_dosage(value: str) -> str | None:
    match = DOSAGE_RE.search(value or "")
    return match.group(0).strip() if match else None


def mask_mobile(value: str) -> str:
    if not value or len(value) < 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]
