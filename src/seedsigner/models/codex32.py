"""Codex32 validation and conversion helpers."""

from __future__ import annotations

from .codex32_min import Codex32String, CodexError
from embit import bip39

ERROR_HEADER = "header"
ERROR_DATA = "data"
ERROR_CHECKSUM = "checksum"
ERROR_LENGTH = "length"
ERROR_UNKNOWN = "unknown"


class Codex32InputError(ValueError):
    """Raised when Codex32 input fails validation."""

    def __init__(self, message: str, error_type: str = ERROR_UNKNOWN) -> None:
        super().__init__(message)
        self.error_type = error_type


def sanitize_codex32_input(raw: str | None) -> str:
    """Normalize user input by removing whitespace and separators."""
    if raw is None:
        return ""
    compact = "".join(raw.split())
    return compact.replace("-", "")


def normalize_codex32_display(raw: str | None) -> str:
    """Normalize Codex32 input for display (uppercase, no separators)."""
    return sanitize_codex32_input(raw).upper()


def _is_single_case(value: str) -> bool:
    return value == value.lower() or value == value.upper()


def _classify_codex_error(exc: CodexError) -> str:
    message = str(exc).lower()
    if "checksum" in message:
        return ERROR_CHECKSUM
    if "hrp" in message or "prefix" in message or "header" in message:
        return ERROR_HEADER
    if "length" in message:
        return ERROR_LENGTH
    return ERROR_DATA


def parse_codex32_share(codex_str: str, expected_len: int | None = 48) -> Codex32String:
    """Parse and validate a codex32 share string (checksum + header)."""
    cleaned = sanitize_codex32_input(codex_str)
    if not cleaned:
        raise Codex32InputError("Codex32 input is empty", ERROR_DATA)
    if expected_len is not None and len(cleaned) != expected_len:
        raise Codex32InputError(
            f"Expected {expected_len} characters for a 128-bit codex32 share, got {len(cleaned)}",
            ERROR_LENGTH,
        )
    if not _is_single_case(cleaned):
        raise Codex32InputError("Codex32 input must be single-case", ERROR_HEADER)
    if cleaned[:3].lower() != "ms1":
        raise Codex32InputError("Codex32 shares must start with MS1", ERROR_HEADER)
    try:
        codex = Codex32String(cleaned)
    except CodexError as exc:
        raise Codex32InputError(str(exc), _classify_codex_error(exc)) from exc
    if codex.hrp != "ms":
        raise Codex32InputError(f"Unsupported HRP '{codex.hrp}', expected 'ms'", ERROR_HEADER)
    return codex


def validate_codex32_s_share(codex_str: str, expected_len: int | None = 48) -> Codex32String:
    """Validate a codex32 S-share string and return a Codex32String object."""
    codex = parse_codex32_share(codex_str, expected_len)
    if codex.share_idx.lower() != "s":
        raise Codex32InputError(
            f"Share index must be 's' for an unshared secret, got '{codex.share_idx}'",
            ERROR_HEADER,
        )
    if len(codex.data) != 16:
        raise Codex32InputError(
            f"Expected 16-byte (128-bit) master seed, got {len(codex.data)} bytes",
            ERROR_DATA,
        )
    return codex


def codex32_to_seed_bytes(codex_str: str) -> bytes:
    """Convert a codex32 S-share string into 16 bytes of seed entropy."""
    codex = validate_codex32_s_share(codex_str)
    return codex.data


def seed_bytes_to_mnemonic(seed_bytes: bytes) -> str:
    """Convert 16 bytes of entropy to a 12-word BIP39 mnemonic (display only)."""
    if len(seed_bytes) != 16:
        raise Codex32InputError(
            f"Expected 16 bytes of entropy for a 12-word mnemonic, got {len(seed_bytes)}",
            ERROR_DATA,
        )
    return bip39.mnemonic_from_bytes(seed_bytes)


def codex32_to_mnemonic(codex_str: str) -> str:
    """Convert a codex32 S-share into a 12-word BIP39 mnemonic (display only)."""
    return seed_bytes_to_mnemonic(codex32_to_seed_bytes(codex_str))


def recover_secret_share(shares: list[Codex32String]) -> Codex32String:
    """Recover the secret share (index 's') from a set of codex32 shares."""
    if not shares:
        raise Codex32InputError("No shares provided for recovery", ERROR_DATA)
    try:
        return Codex32String.interpolate_at(shares, target="s")
    except CodexError as exc:
        raise Codex32InputError(str(exc), _classify_codex_error(exc)) from exc
