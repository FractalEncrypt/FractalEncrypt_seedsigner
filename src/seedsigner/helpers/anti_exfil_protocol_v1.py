"""Frozen canonical multi-slot AEXB protocol-v1 codec."""

from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
import struct
from embit import ec
from seedsigner.helpers.anti_exfil_protocol import AntiExfilProtocolCode, AntiExfilProtocolError

MAGIC = b"AEXB"
FORMAT_VERSION = 1
FLAGS = 0
SIGHASH_ALL = 1
MAX_SLOTS = 128
MAX_SLOTS_PER_INPUT = 16
MAX_MESSAGE_BYTES = 65_536
GROUP_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
HEADER = struct.Struct(">4sBBBBI32s32sH")
COMMON_RECORD = struct.Struct(">II33s32s32s")

class Network(IntEnum):
    MAINNET = 0
    TESTNET3 = 1
    REGTEST = 2
    SIGNET = 3
    TESTNET4 = 4

class Stage(IntEnum):
    HOST_COMMIT = 1
    SIGNER_OPENINGS = 2
    HOST_REVEAL = 3
    SIGNER_SIGNATURES = 4

_EXTRA_LENGTHS = {Stage.HOST_COMMIT: 0, Stage.SIGNER_OPENINGS: 33,
                  Stage.HOST_REVEAL: 65, Stage.SIGNER_SIGNATURES: 97}

@dataclass(frozen=True, slots=True)
class SigningSlot:
    input_index: int
    signer_pubkey: bytes
    message_hash: bytes
    sighash_type: int
    commitment: bytes
    opening: bytes | None = None
    rho: bytes | None = None
    signature: bytes | None = None

    @property
    def identifier(self):
        return self.input_index, self.signer_pubkey

@dataclass(frozen=True, slots=True)
class ProtocolMessage:
    network: Network
    stage: Stage
    session_id: bytes
    psbt_digest: bytes
    slots: tuple[SigningSlot, ...]

    def encode(self) -> bytes:
        _validate_message(self)
        records = b"".join(_encode_slot(self.stage, slot) for slot in self.slots)
        encoded = HEADER.pack(MAGIC, FORMAT_VERSION, int(self.network), int(self.stage),
                              FLAGS, len(records), self.session_id, self.psbt_digest,
                              len(self.slots)) + records
        if len(encoded) > MAX_MESSAGE_BYTES:
            _invalid("AEXB message is oversized")
        return encoded

    def diagnostic(self):
        return {"format": "AEXB", "format_version": FORMAT_VERSION,
                "network": self.network.name, "stage": self.stage.name,
                "stage_number": int(self.stage), "session_id": self.session_id.hex(),
                "psbt_digest": self.psbt_digest.hex(), "slot_count": len(self.slots),
                "slots": [_slot_diagnostic(slot) for slot in self.slots]}

def decode_message(encoded: bytes) -> ProtocolMessage:
    if not isinstance(encoded, bytes) or len(encoded) < HEADER.size:
        _invalid("message is shorter than the AEXB header")
    if len(encoded) > MAX_MESSAGE_BYTES:
        _invalid("AEXB message is oversized")
    magic, version, network_no, stage_no, flags, payload_len, session_id, digest, count = HEADER.unpack_from(encoded)
    if magic != MAGIC or version != FORMAT_VERSION or flags != FLAGS:
        _invalid("invalid AEXB header")
    try:
        network = Network(network_no)
    except ValueError as exc:
        raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"unknown AEXB network {network_no}") from exc
    try:
        stage = Stage(stage_no)
    except ValueError as exc:
        raise AntiExfilProtocolError(AntiExfilProtocolCode.WRONG_STAGE, f"unknown AEXB stage {stage_no}") from exc
    if not 1 <= count <= MAX_SLOTS:
        _invalid("AEXB slot count is outside v1 limits")
    record_len = COMMON_RECORD.size + _EXTRA_LENGTHS[stage]
    if payload_len != count * record_len or len(encoded) != HEADER.size + payload_len:
        _invalid("AEXB length is not canonical")
    slots = tuple(_decode_slot(stage, encoded[HEADER.size + i * record_len:HEADER.size + (i + 1) * record_len]) for i in range(count))
    message = ProtocolMessage(network, stage, session_id, digest, slots)
    _validate_message(message)
    return message

def validate_transition(previous: ProtocolMessage, current: ProtocolMessage) -> None:
    if int(current.stage) != int(previous.stage) + 1:
        raise AntiExfilProtocolError(AntiExfilProtocolCode.WRONG_STAGE, "messages are not adjacent stages")
    if previous.network != current.network or previous.psbt_digest != current.psbt_digest:
        raise AntiExfilProtocolError(AntiExfilProtocolCode.TRANSACTION_MISMATCH, "network or PSBT changed between stages")
    if previous.session_id != current.session_id:
        raise AntiExfilProtocolError(AntiExfilProtocolCode.SESSION_MISMATCH, "session changed between stages")
    if len(previous.slots) != len(current.slots):
        raise AntiExfilProtocolError(AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH, "slot count changed")
    for before, after in zip(previous.slots, current.slots):
        if before.identifier != after.identifier:
            raise AntiExfilProtocolError(AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH, "slot identifier changed")
        if (before.message_hash, before.sighash_type) != (after.message_hash, after.sighash_type):
            raise AntiExfilProtocolError(AntiExfilProtocolCode.TRANSACTION_MISMATCH, "slot context changed")
        if before.commitment != after.commitment:
            raise AntiExfilProtocolError(AntiExfilProtocolCode.COMMITMENT_MISMATCH, "slot commitment changed")
        if previous.stage >= Stage.SIGNER_OPENINGS and before.opening != after.opening:
            raise AntiExfilProtocolError(AntiExfilProtocolCode.OPENING_MISMATCH, "accepted opening changed")

def _encode_slot(stage, slot):
    result = COMMON_RECORD.pack(slot.input_index, slot.sighash_type, slot.signer_pubkey, slot.message_hash, slot.commitment)
    if stage >= Stage.SIGNER_OPENINGS: result += slot.opening or b""
    if stage == Stage.HOST_REVEAL: result += slot.rho or b""
    if stage == Stage.SIGNER_SIGNATURES: result += slot.signature or b""
    return result

def _decode_slot(stage, encoded):
    input_index, sighash, pubkey, message_hash, commitment = COMMON_RECORD.unpack_from(encoded)
    offset, opening, rho, signature = COMMON_RECORD.size, None, None, None
    if stage >= Stage.SIGNER_OPENINGS:
        opening, offset = encoded[offset:offset + 33], offset + 33
    if stage == Stage.HOST_REVEAL: rho = encoded[offset:offset + 32]
    if stage == Stage.SIGNER_SIGNATURES: signature = encoded[offset:offset + 64]
    return SigningSlot(input_index, pubkey, message_hash, sighash, commitment, opening, rho, signature)

def _validate_message(message):
    if not isinstance(message.network, Network) or not isinstance(message.stage, Stage):
        _invalid("network and stage must be canonical enums")
    _bytes("session ID", message.session_id, 32); _bytes("PSBT digest", message.psbt_digest, 32)
    if not isinstance(message.slots, tuple) or not 1 <= len(message.slots) <= MAX_SLOTS:
        _invalid("slot collection is outside v1 limits")
    previous, commitments, reveals, counts = None, set(), set(), {}
    for slot in message.slots:
        _validate_slot(message.stage, slot)
        if previous is not None and slot.identifier <= previous:
            raise AntiExfilProtocolError(AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH, "slots must be uniquely ordered")
        previous = slot.identifier
        if slot.commitment in commitments:
            raise AntiExfilProtocolError(AntiExfilProtocolCode.COMMITMENT_MISMATCH, "commitments must be unique")
        commitments.add(slot.commitment)
        if slot.rho is not None:
            if slot.rho in reveals:
                raise AntiExfilProtocolError(AntiExfilProtocolCode.COMMITMENT_MISMATCH, "reveals must be unique")
            reveals.add(slot.rho)
        counts[slot.input_index] = counts.get(slot.input_index, 0) + 1
        if counts[slot.input_index] > MAX_SLOTS_PER_INPUT:
            raise AntiExfilProtocolError(AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH, "per-input slot limit exceeded")

def _validate_slot(stage, slot):
    if not isinstance(slot.input_index, int) or not 0 <= slot.input_index <= 0xffffffff: _invalid("invalid input index")
    if slot.sighash_type != SIGHASH_ALL: _invalid("protocol v1 supports only SIGHASH_ALL")
    _point("signer public key", slot.signer_pubkey); _bytes("message hash", slot.message_hash, 32); _bytes("commitment", slot.commitment, 32)
    if (slot.opening is not None) != (stage >= Stage.SIGNER_OPENINGS): _invalid("opening presence conflicts with stage")
    if (slot.rho is not None) != (stage == Stage.HOST_REVEAL): _invalid("reveal presence conflicts with stage")
    if (slot.signature is not None) != (stage == Stage.SIGNER_SIGNATURES): _invalid("signature presence conflicts with stage")
    if slot.opening is not None: _point("signer opening", slot.opening)
    if slot.rho is not None: _bytes("host reveal", slot.rho, 32)
    if slot.signature is not None:
        _bytes("compact signature", slot.signature, 64)
        r, s = int.from_bytes(slot.signature[:32], "big"), int.from_bytes(slot.signature[32:], "big")
        if not (1 <= r < GROUP_N and 1 <= s <= GROUP_N // 2): _invalid("invalid signature scalars")

def _bytes(name, value, length):
    if not isinstance(value, bytes) or len(value) != length: _invalid(f"{name} must be {length} bytes")
def _point(name, value):
    _bytes(name, value, 33)
    try: ec.PublicKey.parse(value)
    except Exception as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"invalid {name}") from exc
def _invalid(message):
    raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, message)
def _slot_diagnostic(slot):
    result = {"input_index": slot.input_index, "sighash_type": slot.sighash_type,
              "signer_pubkey": slot.signer_pubkey.hex(), "message_hash": slot.message_hash.hex(),
              "host_commitment": slot.commitment.hex()}
    if slot.opening is not None: result["signer_opening"] = slot.opening.hex()
    if slot.rho is not None: result["host_randomness"] = slot.rho.hex()
    if slot.signature is not None: result["signature_compact"] = slot.signature.hex()
    return result
