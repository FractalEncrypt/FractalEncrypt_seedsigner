"""Strict AEXT v1 package used by the anti-exfil UR2 QR transport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import hashlib
import hmac
import struct

from seedsigner.helpers.anti_exfil_protocol import (
    AntiExfilProtocolCode,
    AntiExfilProtocolError,
    Stage,
    decode_message,
)
from seedsigner.models.settings import SettingsConstants


MAGIC = b"AEXT"
VERSION = 1
UR_TYPE = "x-btc-anti-exfil"
FLAG_PSBT = 1
HEADER = struct.Struct(">4sBBBBII32s")
MAX_MESSAGE_BYTES = 65_536
MAX_PSBT_BYTES = 2_000_000


class TransportNetwork(IntEnum):
    MAINNET = 0
    TESTNET = 1
    REGTEST = 2
    SIGNET = 3


_SETTINGS_NETWORKS = {
    SettingsConstants.MAINNET: TransportNetwork.MAINNET,
    SettingsConstants.TESTNET: TransportNetwork.TESTNET,
    SettingsConstants.REGTEST: TransportNetwork.REGTEST,
}


def _invalid(message: str, *, code=AntiExfilProtocolCode.INVALID_MESSAGE):
    return AntiExfilProtocolError(code, message)


def _cbor_bytes(data: bytes) -> bytes:
    length = len(data)
    if length < 24:
        return bytes([0x40 | length]) + data
    if length <= 0xFF:
        return b"\x58" + bytes([length]) + data
    if length <= 0xFFFF:
        return b"\x59" + length.to_bytes(2, "big") + data
    if length <= 0xFFFFFFFF:
        return b"\x5a" + length.to_bytes(4, "big") + data
    raise _invalid("AEXT CBOR byte string is too large")


def _decode_cbor_bytes(encoded: bytes) -> bytes:
    if not isinstance(encoded, bytes) or not encoded:
        raise _invalid("empty AEXT CBOR payload")
    initial = encoded[0]
    if initial >> 5 != 2:
        raise _invalid("anti-exfil UR payload is not a CBOR byte string")
    additional = initial & 0x1F
    if additional < 24:
        length, offset = additional, 1
    elif additional == 24:
        if len(encoded) < 2:
            raise _invalid("truncated AEXT CBOR length")
        length, offset = encoded[1], 2
        if length < 24:
            raise _invalid("non-canonical AEXT CBOR length")
    elif additional == 25:
        if len(encoded) < 3:
            raise _invalid("truncated AEXT CBOR length")
        length, offset = int.from_bytes(encoded[1:3], "big"), 3
        if length <= 0xFF:
            raise _invalid("non-canonical AEXT CBOR length")
    elif additional == 26:
        if len(encoded) < 5:
            raise _invalid("truncated AEXT CBOR length")
        length, offset = int.from_bytes(encoded[1:5], "big"), 5
        if length <= 0xFFFF:
            raise _invalid("non-canonical AEXT CBOR length")
    else:
        raise _invalid("unsupported AEXT CBOR byte-string length")
    if len(encoded) != offset + length:
        raise _invalid("AEXT CBOR length does not match payload")
    return encoded[offset:]


@dataclass(frozen=True, slots=True)
class AntiExfilTransportPackage:
    message: bytes
    network: TransportNetwork
    psbt: bytes | None = None

    def encode(self) -> bytes:
        parsed = decode_message(self.message)
        requires_psbt = parsed.stage in {Stage.HOST_COMMIT, Stage.HOST_REVEAL}
        if requires_psbt != (self.psbt is not None):
            requirement = "requires" if requires_psbt else "forbids"
            raise _invalid(
                f"transport stage {parsed.stage.name} {requirement} PSBT context"
            )
        try:
            network = TransportNetwork(self.network)
        except (TypeError, ValueError) as exc:
            raise _invalid("AEXT transport network is invalid") from exc
        psbt = self.psbt or b""
        if len(self.message) > MAX_MESSAGE_BYTES or len(psbt) > MAX_PSBT_BYTES:
            raise _invalid("AEXT transport package is oversized")
        if psbt and not psbt.startswith(b"psbt\xff"):
            raise _invalid("AEXT transport PSBT has invalid magic")
        flags = FLAG_PSBT if psbt else 0
        digest = hashlib.sha256(psbt).digest() if psbt else bytes(32)
        return HEADER.pack(
            MAGIC,
            VERSION,
            int(network),
            int(parsed.stage),
            flags,
            len(self.message),
            len(psbt),
            digest,
        ) + self.message + psbt

    def to_cbor(self) -> bytes:
        return _cbor_bytes(self.encode())

    @classmethod
    def decode(
        cls, payload: bytes, *, expected_network: str | None = None
    ) -> "AntiExfilTransportPackage":
        if not isinstance(payload, bytes) or len(payload) < HEADER.size:
            raise _invalid("truncated AEXT transport header")
        (
            magic,
            version,
            network_number,
            stage_number,
            flags,
            message_len,
            psbt_len,
            digest,
        ) = HEADER.unpack_from(payload)
        if magic != MAGIC or version != VERSION or flags & ~FLAG_PSBT:
            raise _invalid("invalid AEXT transport header")
        try:
            network = TransportNetwork(network_number)
        except ValueError as exc:
            raise _invalid(f"unknown AEXT network {network_number}") from exc
        try:
            outer_stage = Stage(stage_number)
        except ValueError as exc:
            raise _invalid(
                f"unknown AEXT stage {stage_number}",
                code=AntiExfilProtocolCode.WRONG_STAGE,
            ) from exc
        if expected_network is not None:
            expected = _SETTINGS_NETWORKS.get(expected_network)
            if expected is None:
                raise _invalid(f"unsupported active network {expected_network!r}")
            if network != expected:
                raise _invalid(
                    "anti-exfil QR network does not match SeedSigner's active network",
                    code=AntiExfilProtocolCode.TRANSACTION_MISMATCH,
                )
        if message_len > MAX_MESSAGE_BYTES or psbt_len > MAX_PSBT_BYTES:
            raise _invalid("AEXT transport package is oversized")
        if len(payload) != HEADER.size + message_len + psbt_len:
            raise _invalid("AEXT lengths do not match payload")
        message = payload[HEADER.size : HEADER.size + message_len]
        psbt_bytes = payload[HEADER.size + message_len :]
        has_psbt = bool(flags & FLAG_PSBT)
        if has_psbt != bool(psbt_len):
            raise _invalid("AEXT PSBT flag is inconsistent")
        expected_digest = hashlib.sha256(psbt_bytes).digest() if has_psbt else bytes(32)
        if not hmac.compare_digest(digest, expected_digest):
            raise _invalid(
                "AEXT PSBT digest mismatch",
                code=AntiExfilProtocolCode.TRANSACTION_MISMATCH,
            )
        parsed = decode_message(message)
        if parsed.stage != outer_stage:
            raise _invalid(
                "AEXT stage conflicts with the embedded protocol message",
                code=AntiExfilProtocolCode.WRONG_STAGE,
            )
        package = cls(
            message=message,
            network=network,
            psbt=psbt_bytes if has_psbt else None,
        )
        package.encode()
        return package

    @classmethod
    def from_cbor(
        cls, encoded: bytes, *, expected_network: str | None = None
    ) -> "AntiExfilTransportPackage":
        return cls.decode(
            _decode_cbor_bytes(encoded), expected_network=expected_network
        )
