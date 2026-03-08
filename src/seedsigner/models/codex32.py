"""Codex32 validation and conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from .codex32_min import Codex32String, CodexError
from embit import bip39

ERROR_HEADER = "header"
ERROR_DATA = "data"
ERROR_CHECKSUM = "checksum"
ERROR_LENGTH = "length"
ERROR_UNKNOWN = "unknown"

CODEX32_QR_CANONICAL_PREFIX = "MS1"
CODEX32_QR_CANONICAL_LENGTH = 48
CODEX32_QR_MODULE_TARGET = 29
CODEX32_QR_EC_LEVEL = "L"
CODEX32_MAX_SPLIT_SHARES = 5


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


def wipe_codex32_share(share: Codex32String | None) -> None:
    """
    Best-effort wipe of a Codex32String object's sensitive fields.

    Because Python strings/bytes are immutable, this cannot guarantee all copies are
    erased, but it reduces live references and buffers we control.
    """
    if share is None:
        return

    if hasattr(share, "value") and isinstance(share.value, str):
        share.value = "\x00" * len(share.value)
        share.value = ""

    if hasattr(share, "data") and isinstance(share.data, (bytes, bytearray)):
        wipe_buf = bytearray(share.data)
        for i in range(len(wipe_buf)):
            wipe_buf[i] = 0
        share.data = b""

    if hasattr(share, "_payload_values") and isinstance(share._payload_values, list):
        for i in range(len(share._payload_values)):
            share._payload_values[i] = 0
        share._payload_values = []

    if hasattr(share, "_data_part_values") and isinstance(share._data_part_values, list):
        for i in range(len(share._data_part_values)):
            share._data_part_values[i] = 0
        share._data_part_values = []


def recover_secret_share(shares: list[Codex32String]) -> Codex32String:
    """Recover the secret share (index 's') from a set of codex32 shares."""
    if not shares:
        raise Codex32InputError("No shares provided for recovery", ERROR_DATA)
    try:
        return Codex32String.interpolate_at(shares, target="s")
    except CodexError as exc:
        raise Codex32InputError(str(exc), _classify_codex_error(exc)) from exc


def _parse_threshold(value: str) -> int:
    try:
        threshold = int(value)
    except ValueError as exc:
        raise Codex32InputError("Invalid threshold value in share header.", ERROR_HEADER) from exc
    if threshold < 2:
        raise Codex32InputError("Threshold must be >= 2 for split shares.", ERROR_HEADER)
    return threshold


@dataclass
class Codex32ShareCollection:
    threshold: int
    ident: str
    case: str
    shares: list[Codex32String] = field(default_factory=list)

    @classmethod
    def from_first_share(cls, share: Codex32String) -> "Codex32ShareCollection":
        threshold = _parse_threshold(share.k)
        return cls(threshold=threshold, ident=share.ident, case=share.case, shares=[share])

    @property
    def share_indices(self) -> set[str]:
        return {share.share_idx.lower() for share in self.shares}

    @property
    def split_share_count(self) -> int:
        return len([share for share in self.shares if share.share_idx.lower() != "s"])

    @property
    def ready(self) -> bool:
        return len(self.shares) >= self.threshold

    @property
    def ready_for_export(self) -> bool:
        return self.recovered_secret_share() is not None

    def prefix(self) -> str:
        prefix = f"ms1{self.threshold}{self.ident}"
        if self.case == "upper":
            return prefix.upper()
        return prefix

    def get_share(self, share_idx: str) -> Codex32String | None:
        target = share_idx.lower()
        for share in self.shares:
            if share.share_idx.lower() == target:
                return share
        return None

    def validate_share(self, share: Codex32String) -> None:
        if share.k != str(self.threshold) or share.ident != self.ident:
            raise Codex32InputError("Share header mismatch (k/identifier).", ERROR_HEADER)
        if share.share_idx.lower() in self.share_indices:
            raise Codex32InputError("Duplicate share index entered.", ERROR_HEADER)
        if share.share_idx.lower() != "s" and self.split_share_count >= CODEX32_MAX_SPLIT_SHARES:
            raise Codex32InputError(
                f"A maximum of {CODEX32_MAX_SPLIT_SHARES} split shares is supported.",
                ERROR_HEADER,
            )

    def recovered_secret_share(self) -> Codex32String | None:
        if not self.ready:
            return None
        try:
            secret_share = recover_secret_share(self.shares)
            return validate_codex32_s_share(secret_share.s, expected_len=CODEX32_QR_CANONICAL_LENGTH)
        except Codex32InputError:
            return None

    def export_shares(self) -> tuple[dict[str, str], dict[str, str]]:
        share_map: dict[str, str] = {}
        source_map: dict[str, str] = {}

        for share in self.shares:
            share_idx = share.share_idx.lower()
            share_map[share_idx] = normalize_codex32_display(share.s)
            source_map[share_idx] = "entered"

        secret_share = self.recovered_secret_share()
        if secret_share is not None and "s" not in share_map:
            share_map["s"] = normalize_codex32_display(secret_share.s)
            source_map["s"] = "derived"

        return share_map, source_map

    @staticmethod
    def ordered_share_indices(share_map: dict[str, str]) -> list[str]:
        if not share_map:
            return []

        split_indices = sorted(idx for idx in share_map.keys() if idx != "s")
        if "s" in share_map:
            return ["s"] + split_indices
        return split_indices

    def add_share(self, share: Codex32String, replace_existing: bool = False) -> str:
        if share.k != str(self.threshold) or share.ident != self.ident:
            raise Codex32InputError("Share header mismatch (k/identifier).", ERROR_HEADER)

        existing = self.get_share(share.share_idx)
        if existing is not None:
            if existing.s.lower() == share.s.lower():
                return "unchanged"
            if not replace_existing:
                raise Codex32InputError(
                    "Conflicting share index entered. Confirm replacement to continue.",
                    ERROR_HEADER,
                )

            for i, cur_share in enumerate(self.shares):
                if cur_share.share_idx.lower() == share.share_idx.lower():
                    self.shares[i] = share
                    return "replaced"

        if share.share_idx.lower() != "s" and self.split_share_count >= CODEX32_MAX_SPLIT_SHARES:
            raise Codex32InputError(
                f"A maximum of {CODEX32_MAX_SPLIT_SHARES} split shares is supported.",
                ERROR_HEADER,
            )

        self.shares.append(share)
        return "added"


    def wipe(self) -> None:
        """Best-effort wipe of in-memory share collection state."""
        for share in self.shares:
            wipe_codex32_share(share)

        self.shares = []
        self.threshold = 0
        self.ident = ""
        self.case = "lower"
