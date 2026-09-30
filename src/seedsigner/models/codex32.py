"""Codex32 validation and conversion helpers."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from itertools import combinations
from dataclasses import dataclass, field

from .codex32_min import Codex32String, CodexError, _is_single_case
from embit import bip39

logger = logging.getLogger(__name__)

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
    """Normalize user input by removing whitespace (per Codex32QR spec 3.2)."""
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise Codex32InputError("Codex32 input must be text", ERROR_DATA)
    compact = "".join(raw.split())
    if "-" in compact:
        raise Codex32InputError(
            "Hyphens are not permitted in codex32 input",
            ERROR_DATA,
        )
    return compact


def normalize_codex32_display(raw: str | None) -> str:
    """Normalize Codex32 input for display (uppercase, no separators)."""
    return sanitize_codex32_input(raw).upper()


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
    if codex.k != "0":
        _parse_threshold(codex.k)
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
    Best-effort release of a Codex32String object's sensitive fields.

    Immutable bytes/strings cannot be scrubbed safely in place in Python. Clear
    mutable lists and drop this object's references without mutating potentially
    aliased immutable objects.
    """
    if share is None:
        return

    if hasattr(share, "value") and isinstance(share.value, str):
        share.value = "\x00" * len(share.value)
        share.value = ""

    if hasattr(share, "data") and isinstance(share.data, (bytes, bytearray)):
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

    first_share = shares[0]
    threshold = _parse_threshold(first_share.k)
    if len(shares) != threshold:
        raise Codex32InputError(
            f"Recovery requires exactly {threshold} shares, got {len(shares)}",
            ERROR_DATA,
        )

    indices = {s.share_idx.lower() for s in shares}
    if len(indices) != len(shares):
        raise Codex32InputError("Duplicate share indices detected", ERROR_DATA)
    for share in shares:
        if share.k != first_share.k or share.ident != first_share.ident:
            raise Codex32InputError(
                "Shares must have matching thresholds and identifiers",
                ERROR_HEADER,
            )
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
    if threshold > CODEX32_MAX_SPLIT_SHARES:
        raise Codex32InputError(
            f"Thresholds above {CODEX32_MAX_SPLIT_SHARES} are not supported.",
            ERROR_HEADER,
        )
    return threshold


@dataclass
class Codex32RecoveryResult:
    secret: Codex32String | None = None
    split_consistency_proven: bool = False
    omitted_split_shares: bool = False


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
        return self.get_share("s") is not None or len(self.shares) >= self.threshold

    @property
    def ready_for_export(self) -> bool:
        return self.recovered_secret_share() is not None

    @property
    def backup_metadata_warning_required(self) -> bool:
        return self._recovery_result().omitted_split_shares

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
        return self._recovery_result().secret

    def _recovery_result(self) -> Codex32RecoveryResult:
        if not self.ready:
            return Codex32RecoveryResult()

        try:
            entered_secret = self.get_share("s")
            if entered_secret is not None:
                canonical_secret = validate_codex32_s_share(
                    entered_secret.s,
                    expected_len=CODEX32_QR_CANONICAL_LENGTH,
                )
            else:
                canonical_secret = None

            split_shares = [share for share in self.shares if share.share_idx.lower() != "s"]
            if len(split_shares) >= self.threshold:
                for share_subset in combinations(split_shares, self.threshold):
                    recovered = validate_codex32_s_share(
                        recover_secret_share(list(share_subset)).s,
                        expected_len=CODEX32_QR_CANONICAL_LENGTH,
                    )
                    if canonical_secret is None:
                        canonical_secret = recovered
                    elif recovered.s.lower() != canonical_secret.s.lower():
                        if entered_secret is not None:
                            # Policy C keeps an independently valid entered S
                            # while omitting a complete but inconsistent split.
                            return Codex32RecoveryResult(
                                secret=canonical_secret,
                                omitted_split_shares=True,
                            )
                        raise Codex32InputError(
                            "Share set does not reconstruct the entered secret.",
                            ERROR_DATA,
                        )

                return Codex32RecoveryResult(
                    secret=canonical_secret,
                    split_consistency_proven=True,
                )

            return Codex32RecoveryResult(
                secret=canonical_secret,
                omitted_split_shares=bool(split_shares),
            )
        except Codex32InputError as e:
            logger.debug("Secret share recovery failed: %s", e)
            return Codex32RecoveryResult()

    def export_shares(self) -> tuple[dict[str, str], dict[str, str]]:
        recovery = self._recovery_result()
        secret_share = recovery.secret
        if secret_share is None:
            return {}, {}

        share_map: dict[str, str] = {}
        source_map: dict[str, str] = {}

        # Only a complete, consistent split set may cross this export boundary.
        verified_shares = self.shares if recovery.split_consistency_proven else []

        for share in verified_shares:
            share_idx = share.share_idx.lower()
            share_map[share_idx] = normalize_codex32_display(share.s)
            source_map[share_idx] = "entered"

        entered_secret = self.get_share("s")
        if entered_secret is not None:
            share_map["s"] = normalize_codex32_display(entered_secret.s)
            source_map["s"] = "entered"
        else:
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
        """Best-effort release of in-memory share collection state."""
        for share in self.shares:
            wipe_codex32_share(share)

        self.shares = []
        self.threshold = 0
        self.ident = ""
        self.case = "lower"


def validate_codex32_seed_metadata(
    seed_bytes: bytes,
    master_share: str | None = None,
    export_shares: dict[str, str] | None = None,
) -> None:
    """Validate that Codex32 backup metadata represents ``seed_bytes``.

    Metadata is optional, but when present it must contain one unambiguous,
    canonical ``S`` share. Split shares must match its header. When enough
    split shares are present, every threshold-sized subset must reconstruct the
    same ``S``. Below-threshold splits remain valid stored recovery context but
    must be omitted by export boundaries because consistency cannot be proven.
    """
    if master_share is None and not export_shares:
        return

    parsed_export_shares: dict[str, Codex32String] = {}
    s_candidates: list[Codex32String] = []

    if master_share is not None:
        s_candidates.append(validate_codex32_s_share(master_share))

    raw_export_shares = export_shares or {}
    if not isinstance(raw_export_shares, Mapping):
        raise Codex32InputError("Codex32 export metadata must be a mapping.", ERROR_DATA)

    normalized_keys: set[str] = set()
    raw_split_count = 0
    for share_idx_raw in raw_export_shares.keys():
        share_idx = str(share_idx_raw).lower()
        if share_idx in normalized_keys:
            raise Codex32InputError(
                f"Duplicate normalized export metadata key '{share_idx}'.",
                ERROR_HEADER,
            )
        normalized_keys.add(share_idx)
        if share_idx != "s":
            raw_split_count += 1

    if raw_split_count > CODEX32_MAX_SPLIT_SHARES:
        raise Codex32InputError(
            f"A maximum of {CODEX32_MAX_SPLIT_SHARES} split shares is supported.",
            ERROR_HEADER,
        )

    for share_idx_raw, share_value in raw_export_shares.items():
        share_idx = str(share_idx_raw).lower()
        parsed_share = parse_codex32_share(share_value)
        if parsed_share.share_idx.lower() != share_idx:
            raise Codex32InputError(
                f"Export metadata key '{share_idx_raw}' does not match share index "
                f"'{parsed_share.share_idx}'.",
                ERROR_HEADER,
            )
        parsed_export_shares[share_idx] = parsed_share
        if share_idx == "s":
            s_candidates.append(validate_codex32_s_share(share_value))

    if not s_candidates:
        raise Codex32InputError(
            "Codex32 backup metadata must include a canonical S share.",
            ERROR_DATA,
        )

    canonical_s = s_candidates[0]
    for candidate in s_candidates[1:]:
        if candidate.s.lower() != canonical_s.s.lower():
            raise Codex32InputError(
                "Conflicting canonical S shares in backup metadata.",
                ERROR_DATA,
            )

    if canonical_s.data != seed_bytes:
        raise Codex32InputError(
            "Codex32 backup metadata does not match the active seed.",
            ERROR_DATA,
        )

    split_shares = [
        share for share_idx, share in parsed_export_shares.items() if share_idx != "s"
    ]
    if not split_shares:
        return

    threshold = _parse_threshold(canonical_s.k)
    for share in split_shares:
        if share.k != canonical_s.k or share.ident != canonical_s.ident:
            raise Codex32InputError(
                "Export shares must match the canonical S threshold and identifier.",
                ERROR_HEADER,
            )

    if len(split_shares) >= threshold:
        for share_subset in combinations(split_shares, threshold):
            recovered = recover_secret_share(list(share_subset))
            if recovered.s.lower() != canonical_s.s.lower():
                raise Codex32InputError(
                    "Export shares do not reconstruct the canonical S share.",
                    ERROR_DATA,
                )


@dataclass
class Codex32BackupMetadata:
    """Canonical, export-safe Codex32 backup metadata."""

    share_map: dict[str, str] = field(default_factory=dict)
    source_map: dict[str, str] = field(default_factory=dict)
    show_warning: bool = False

    @property
    def available(self) -> bool:
        return "s" in self.share_map


def resolve_codex32_backup_metadata(
    seed_bytes: bytes,
    master_share: str | None = None,
    export_shares: Mapping[object, object] | None = None,
    share_sources: Mapping[object, object] | None = None,
) -> Codex32BackupMetadata:
    """Resolve malformed or legacy metadata into an export-safe Policy-C view.

    Canonical ``S`` failures and raw split overflow make backup unavailable.
    Invalid, incomplete, or inconsistent non-S metadata is omitted with a
    warning. Every normalization operation stays inside this exception boundary.
    """
    try:
        return _resolve_codex32_backup_metadata(
            seed_bytes=seed_bytes,
            master_share=master_share,
            export_shares=export_shares,
            share_sources=share_sources,
        )
    except (Codex32InputError, AttributeError, TypeError, ValueError):
        return Codex32BackupMetadata()


def _resolve_codex32_backup_metadata(
    seed_bytes: bytes,
    master_share: str | None,
    export_shares: Mapping[object, object] | None,
    share_sources: Mapping[object, object] | None,
) -> Codex32BackupMetadata:
    if export_shares is None:
        raw_share_items: list[tuple[object, object]] = []
    elif isinstance(export_shares, Mapping):
        raw_share_items = list(export_shares.items())
    else:
        raise Codex32InputError("Codex32 export metadata must be a mapping.", ERROR_DATA)

    normalized_entries: dict[str, tuple[object, object]] = {}
    collided_indices: set[str] = set()
    raw_split_count = 0
    for raw_key, raw_value in raw_share_items:
        share_idx = str(raw_key).lower()
        if share_idx != "s":
            raw_split_count += 1
        if share_idx in normalized_entries:
            collided_indices.add(share_idx)
        else:
            normalized_entries[share_idx] = (raw_key, raw_value)

    # Policy C treats raw overflow as a total metadata failure. Count entries
    # before collision collapse or invalid-entry filtering.
    if raw_split_count > CODEX32_MAX_SPLIT_SHARES:
        raise Codex32InputError(
            f"A maximum of {CODEX32_MAX_SPLIT_SHARES} split shares is supported.",
            ERROR_HEADER,
        )
    if "s" in collided_indices:
        raise Codex32InputError("Conflicting normalized S metadata keys.", ERROR_HEADER)

    normalized_sources: dict[str, object] = {}
    source_collisions: set[str] = set()
    if share_sources is not None:
        if not isinstance(share_sources, Mapping):
            share_sources = {}
        for raw_key, raw_value in share_sources.items():
            source_idx = str(raw_key).lower()
            if source_idx in normalized_sources:
                source_collisions.add(source_idx)
            else:
                normalized_sources[source_idx] = raw_value

    canonical_candidates: list[Codex32String] = []
    if master_share is not None:
        # Validate original case first. Canonical display conversion occurs only
        # after strict parsing succeeds.
        canonical_candidates.append(validate_codex32_s_share(master_share))

    raw_s_entry = normalized_entries.get("s")
    if raw_s_entry is not None:
        _, raw_s_value = raw_s_entry
        canonical_candidates.append(validate_codex32_s_share(raw_s_value))

    if not canonical_candidates:
        raise Codex32InputError(
            "Codex32 backup metadata must include a canonical S share.",
            ERROR_DATA,
        )

    canonical_s = canonical_candidates[0]
    for candidate in canonical_candidates[1:]:
        if candidate.s.lower() != canonical_s.s.lower():
            raise Codex32InputError(
                "Conflicting canonical S shares in backup metadata.",
                ERROR_DATA,
            )
    if canonical_s.data != seed_bytes:
        raise Codex32InputError(
            "Codex32 backup metadata does not match the active seed.",
            ERROR_DATA,
        )

    canonical_display = canonical_s.s.upper()
    share_map = {"s": canonical_display}
    source_map = {"s": "unknown"}
    dropped_non_s_entries = bool(collided_indices - {"s"})
    parsed_split_shares: dict[str, Codex32String] = {}

    for share_idx, (_, raw_value) in normalized_entries.items():
        if share_idx == "s" or share_idx in collided_indices:
            continue
        try:
            parsed = parse_codex32_share(raw_value)
        except Codex32InputError:
            dropped_non_s_entries = True
            continue
        if parsed.share_idx.lower() != share_idx:
            dropped_non_s_entries = True
            continue
        if parsed.k != canonical_s.k or parsed.ident != canonical_s.ident:
            dropped_non_s_entries = True
            continue
        parsed_split_shares[share_idx] = parsed
        share_map[share_idx] = parsed.s.upper()
        # Non-S shares in this product are collection inputs, never derived.
        source_map[share_idx] = "entered"

    split_consistency_proven = False
    if parsed_split_shares:
        try:
            threshold = _parse_threshold(canonical_s.k)
        except Codex32InputError:
            dropped_non_s_entries = True
            threshold = CODEX32_MAX_SPLIT_SHARES + 1

        if len(parsed_split_shares) >= threshold:
            try:
                validate_codex32_seed_metadata(
                    seed_bytes,
                    master_share=canonical_display,
                    export_shares=share_map,
                )
                split_consistency_proven = True
            except Codex32InputError:
                dropped_non_s_entries = True

    raw_s_source = normalized_sources.get("s") if "s" not in source_collisions else None
    if raw_s_source == "entered":
        source_map["s"] = "entered"
    elif raw_s_source == "derived" and split_consistency_proven:
        source_map["s"] = "derived"

    if parsed_split_shares and not split_consistency_proven:
        dropped_non_s_entries = True

    if dropped_non_s_entries:
        return Codex32BackupMetadata(
            share_map={"s": canonical_display},
            source_map={"s": source_map["s"]},
            show_warning=True,
        )

    return Codex32BackupMetadata(
        share_map=share_map,
        source_map=source_map,
        show_warning=False,
    )
