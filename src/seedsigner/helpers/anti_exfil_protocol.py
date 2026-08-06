"""Terminal-first SeedSigner ECDSA anti-exfil signer controller.

This is an experimental, single-input native-P2WPKH protocol boundary. It uses
the AEXB v1 terminal envelope while the eventual QR/PSBT wire format is still
under review. It deliberately contains no camera, QR, screen, settings, or
ordinary-signing fallback behavior.
"""

from __future__ import annotations

import argparse
import hmac
import json
import struct
import sys
from dataclasses import dataclass
from enum import Enum, IntEnum
from pathlib import Path

from embit import ec, script
from embit.psbt import PSBT, PSBTError
from embit.transaction import SIGHASH

from seedsigner.helpers.anti_exfil import (
    DEFAULT_LIBRARY_PATH,
    AntiExfilNativeBackend,
    AntiExfilNativeError,
)
from seedsigner.models.psbt_parser import PSBTParser
from seedsigner.models.seed import InvalidSeedException, Seed
from seedsigner.models.settings import SettingsConstants


MAGIC = b"AEXB"
FORMAT_VERSION = 1
HEADER = struct.Struct(">4sBBH")
COMMON_LENGTH = 32 + 32 + 33
GROUP_N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


class AntiExfilProtocolCode(str, Enum):
    INVALID_MESSAGE = "AE_INVALID_MESSAGE"
    WRONG_STAGE = "AE_WRONG_STAGE"
    TRANSACTION_MISMATCH = "AE_TRANSACTION_MISMATCH"
    SIGNATURE_SLOT_MISMATCH = "AE_SIGNATURE_SLOT_MISMATCH"
    SIGNING_MODE_MISMATCH = "AE_SIGNING_MODE_MISMATCH"
    COMMITMENT_MISMATCH = "AE_COMMITMENT_MISMATCH"
    OPENING_MISMATCH = "AE_OPENING_MISMATCH"
    NATIVE_BACKEND = "AE_NATIVE_BACKEND"
    OUTPUT_EXISTS = "AE_OUTPUT_EXISTS"


class AntiExfilProtocolError(RuntimeError):
    def __init__(self, code: AntiExfilProtocolCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class Stage(IntEnum):
    HOST_COMMIT = 1
    SIGNER_OPENINGS = 2
    HOST_REVEAL = 3
    SIGNER_SIGNATURES = 4


_STAGE_EXTRA_LENGTHS = {
    Stage.HOST_COMMIT: 32,
    Stage.SIGNER_OPENINGS: 32 + 33,
    Stage.HOST_REVEAL: 32 + 33 + 32,
    Stage.SIGNER_SIGNATURES: 32 + 33 + 32 + 64,
}


@dataclass(frozen=True, slots=True)
class AntiExfilMessage:
    stage: Stage
    session_id: bytes
    message_hash: bytes
    signer_pubkey: bytes
    commitment: bytes
    opening: bytes | None = None
    host_randomness: bytes | None = None
    signature: bytes | None = None

    def encode(self) -> bytes:
        _validate_message(self)
        payload = self.session_id + self.message_hash + self.signer_pubkey + self.commitment
        if self.opening is not None:
            payload += self.opening
        if self.host_randomness is not None:
            payload += self.host_randomness
        if self.signature is not None:
            payload += self.signature
        return HEADER.pack(MAGIC, FORMAT_VERSION, int(self.stage), len(payload)) + payload

    def diagnostic(self) -> dict[str, object]:
        result: dict[str, object] = {
            "format": "AEXB",
            "format_version": FORMAT_VERSION,
            "stage": self.stage.name,
            "stage_number": int(self.stage),
            "session_id": self.session_id.hex(),
            "message_hash": self.message_hash.hex(),
            "signer_pubkey": self.signer_pubkey.hex(),
            "host_commitment": self.commitment.hex(),
        }
        if self.opening is not None:
            result["signer_opening"] = self.opening.hex()
        if self.host_randomness is not None:
            result["host_randomness"] = self.host_randomness.hex()
        if self.signature is not None:
            result["signature_compact"] = self.signature.hex()
        return result


def decode_message(encoded: bytes) -> AntiExfilMessage:
    if not isinstance(encoded, bytes) or len(encoded) < HEADER.size:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            "message is shorter than the AEXB header",
        )
    magic, version, stage_number, payload_length = HEADER.unpack(encoded[: HEADER.size])
    if magic != MAGIC:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, "message has the wrong AEXB magic"
        )
    if version != FORMAT_VERSION:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            f"unsupported AEXB format version {version}",
        )
    try:
        stage = Stage(stage_number)
    except ValueError as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.WRONG_STAGE,
            f"unknown AEXB stage {stage_number}",
        ) from exc

    payload = encoded[HEADER.size :]
    expected_length = COMMON_LENGTH + _STAGE_EXTRA_LENGTHS[stage]
    if payload_length != len(payload) or payload_length != expected_length:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            f"stage {stage.name} payload length is not canonical",
        )

    offset = 0

    def take(length: int) -> bytes:
        nonlocal offset
        value = payload[offset : offset + length]
        offset += length
        return value

    message = AntiExfilMessage(
        stage=stage,
        session_id=take(32),
        message_hash=take(32),
        signer_pubkey=take(33),
        commitment=take(32),
        opening=take(33) if stage >= Stage.SIGNER_OPENINGS else None,
        host_randomness=take(32) if stage >= Stage.HOST_REVEAL else None,
        signature=take(64) if stage >= Stage.SIGNER_SIGNATURES else None,
    )
    _validate_message(message)
    return message


def _validate_public_key(value: bytes, name: str) -> None:
    if not isinstance(value, bytes) or len(value) != 33:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"{name} must be exactly 33 bytes"
        )
    try:
        ec.PublicKey.parse(value)
    except Exception as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"invalid {name}"
        ) from exc


def _validate_message(message: AntiExfilMessage) -> None:
    if not isinstance(message.stage, Stage):
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.WRONG_STAGE, "message stage is invalid"
        )
    for name, value in (
        ("session ID", message.session_id),
        ("message hash", message.message_hash),
        ("host commitment", message.commitment),
    ):
        if not isinstance(value, bytes) or len(value) != 32:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                f"{name} must be exactly 32 bytes",
            )
    _validate_public_key(message.signer_pubkey, "signer public key")

    needs_opening = message.stage >= Stage.SIGNER_OPENINGS
    needs_randomness = message.stage >= Stage.HOST_REVEAL
    needs_signature = message.stage >= Stage.SIGNER_SIGNATURES
    if (message.opening is not None) != needs_opening:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            "opening presence conflicts with stage",
        )
    if (message.host_randomness is not None) != needs_randomness:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            "host randomness presence conflicts with stage",
        )
    if (message.signature is not None) != needs_signature:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            "signature presence conflicts with stage",
        )
    if message.opening is not None:
        _validate_public_key(message.opening, "signer opening")
    if message.host_randomness is not None:
        if (
            not isinstance(message.host_randomness, bytes)
            or len(message.host_randomness) != 32
        ):
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                "host randomness must be exactly 32 bytes",
            )
    if message.signature is not None:
        if not isinstance(message.signature, bytes) or len(message.signature) != 64:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                "compact signature must be exactly 64 bytes",
            )
        r = int.from_bytes(message.signature[:32], "big")
        s = int.from_bytes(message.signature[32:], "big")
        if not (1 <= r < GROUP_N and 1 <= s <= GROUP_N // 2):
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                "signature scalars are invalid or non-low-S",
            )


@dataclass(frozen=True, slots=True)
class SigningContext:
    input_index: int
    signer_pubkey: bytes
    message_hash: bytes
    secret_key: bytes
    fingerprint: str
    derivation: str
    input_amount: int
    spend_amount: int
    fee_amount: int


@dataclass(frozen=True, slots=True)
class ControllerResult:
    response: AntiExfilMessage
    context: SigningContext


def _parse_psbt(psbt_bytes: bytes) -> PSBT:
    if not isinstance(psbt_bytes, bytes):
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, "PSBT must be bytes"
        )
    try:
        psbt = PSBT.parse(psbt_bytes)
    except (PSBTError, ValueError, IndexError) as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"invalid PSBT: {exc}"
        ) from exc
    if psbt.serialize() != psbt_bytes:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            "PSBT is not in canonical embit representation",
        )
    return psbt


def _format_derivation(derivation: list[int]) -> str:
    return "m/" + "/".join(
        f"{index & 0x7fffffff}{'h' if index & 0x80000000 else ''}"
        for index in derivation
    )


def derive_signing_context(
    psbt_bytes: bytes, seed: Seed, network: str
) -> tuple[PSBT, SigningContext]:
    if network not in {
        SettingsConstants.MAINNET,
        SettingsConstants.TESTNET,
        SettingsConstants.REGTEST,
    }:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"unsupported network {network!r}"
        )

    psbt = _parse_psbt(psbt_bytes)
    try:
        parser = PSBTParser(psbt, seed, network)
    except Exception as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE,
            f"SeedSigner rejected the PSBT or seed: {exc}",
        ) from exc
    if parser.root is None or parser.policy is None:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, "SeedSigner did not parse the PSBT"
        )

    fingerprint = parser.root.my_fingerprint
    candidates: list[SigningContext] = []
    for input_index, input_scope in enumerate(psbt.inputs):
        if input_scope.is_taproot:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH,
                "anti-exfil v1 supports ECDSA only; Taproot input rejected",
            )
        for pubkey, origin in input_scope.bip32_derivations.items():
            if origin.fingerprint != fingerprint:
                continue
            derived = parser.root.derive(origin.derivation)
            if derived.key.get_public_key().sec() != pubkey.sec():
                raise AntiExfilProtocolError(
                    AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH,
                    "SeedSigner derivation does not reproduce the PSBT public key",
                )
            if pubkey in input_scope.partial_sigs:
                raise AntiExfilProtocolError(
                    AntiExfilProtocolCode.SIGNING_MODE_MISMATCH,
                    "anti-exfil path rejects a PSBT already signed by this SeedSigner key",
                )
            try:
                utxo = psbt.utxo(input_index)
            except Exception as exc:
                raise AntiExfilProtocolError(
                    AntiExfilProtocolCode.INVALID_MESSAGE,
                    f"input {input_index} is missing usable UTXO data",
                ) from exc
            if utxo.script_pubkey != script.p2wpkh(pubkey):
                raise AntiExfilProtocolError(
                    AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH,
                    "anti-exfil terminal v1 requires a native P2WPKH signing slot",
                )
            sighash_type = input_scope.sighash_type
            if sighash_type is None:
                sighash_type = SIGHASH.ALL
            if sighash_type != SIGHASH.ALL:
                raise AntiExfilProtocolError(
                    AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH,
                    f"input {input_index} requests unsupported sighash type {sighash_type}",
                )
            candidates.append(
                SigningContext(
                    input_index=input_index,
                    signer_pubkey=pubkey.sec(),
                    message_hash=psbt.sighash(input_index, sighash=sighash_type),
                    secret_key=derived.key.secret,
                    fingerprint=fingerprint.hex(),
                    derivation=_format_derivation(origin.derivation),
                    input_amount=parser.input_amount,
                    spend_amount=parser.spend_amount,
                    fee_amount=parser.fee_amount,
                )
            )

    if len(candidates) != 1:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH,
            f"anti-exfil terminal v1 requires exactly one SeedSigner ECDSA slot; found {len(candidates)}",
        )
    return psbt, candidates[0]


class AntiExfilSignerController:
    """Process signer-side AEXB stages against an authoritative SeedSigner PSBT."""

    def __init__(self, seed: Seed, network: str, backend: AntiExfilNativeBackend):
        self.seed = seed
        self.network = network
        self.backend = backend

    def process(self, request_bytes: bytes, psbt_bytes: bytes) -> ControllerResult:
        request = decode_message(request_bytes)
        if request.stage not in {Stage.HOST_COMMIT, Stage.HOST_REVEAL}:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.WRONG_STAGE,
                "SeedSigner accepts only HOST_COMMIT (message 1) or HOST_REVEAL (message 3)",
            )

        _, context = derive_signing_context(psbt_bytes, self.seed, self.network)
        if not hmac.compare_digest(context.signer_pubkey, request.signer_pubkey):
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH,
                "SeedSigner-derived public key does not match the anti-exfil message",
            )
        if not hmac.compare_digest(context.message_hash, request.message_hash):
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.TRANSACTION_MISMATCH,
                "SeedSigner-derived sighash does not match the anti-exfil message",
            )

        try:
            if request.stage == Stage.HOST_COMMIT:
                opening = self.backend.signer_commit(
                    context.secret_key, request.message_hash, request.commitment
                )
                response = AntiExfilMessage(
                    stage=Stage.SIGNER_OPENINGS,
                    session_id=request.session_id,
                    message_hash=request.message_hash,
                    signer_pubkey=request.signer_pubkey,
                    commitment=request.commitment,
                    opening=opening,
                )
            else:
                if request.host_randomness is None or request.opening is None:
                    raise AntiExfilProtocolError(
                        AntiExfilProtocolCode.INVALID_MESSAGE,
                        "HOST_REVEAL is incomplete",
                    )
                commitment = self.backend.host_commit(request.host_randomness)
                if not hmac.compare_digest(commitment, request.commitment):
                    raise AntiExfilProtocolError(
                        AntiExfilProtocolCode.COMMITMENT_MISMATCH,
                        "host randomness does not match the committed value",
                    )
                expected_opening = self.backend.signer_commit(
                    context.secret_key, request.message_hash, request.commitment
                )
                if not hmac.compare_digest(expected_opening, request.opening):
                    raise AntiExfilProtocolError(
                        AntiExfilProtocolCode.OPENING_MISMATCH,
                        "HOST_REVEAL does not contain this signer's deterministic opening",
                    )
                signature = self.backend.sign(
                    context.secret_key,
                    request.message_hash,
                    request.host_randomness,
                )
                response = AntiExfilMessage(
                    stage=Stage.SIGNER_SIGNATURES,
                    session_id=request.session_id,
                    message_hash=request.message_hash,
                    signer_pubkey=request.signer_pubkey,
                    commitment=request.commitment,
                    opening=request.opening,
                    host_randomness=request.host_randomness,
                    signature=signature,
                )
        except AntiExfilNativeError as exc:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.NATIVE_BACKEND, str(exc)
            ) from exc

        return ControllerResult(response=response, context=context)


def _read_text_secret(path: Path, label: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"cannot read {label}: {exc}"
        ) from exc
    if not value:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"{label} is empty"
        )
    return value


def _write_new(path: Path, value: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output:
            output.write(value)
    except FileExistsError as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.OUTPUT_EXISTS,
            f"refusing to replace existing output: {path}",
        ) from exc
    except OSError as exc:
        raise AntiExfilProtocolError(
            AntiExfilProtocolCode.INVALID_MESSAGE, f"cannot write output: {exc}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Process one signer-side anti-exfil stage without QR or UI"
    )
    parser.add_argument("--psbt", type=Path, required=True)
    parser.add_argument("--message", type=Path, required=True)
    parser.add_argument("--mnemonic-file", type=Path, required=True)
    parser.add_argument("--passphrase-file", type=Path)
    parser.add_argument(
        "--network",
        choices=[
            SettingsConstants.MAINNET,
            SettingsConstants.TESTNET,
            SettingsConstants.REGTEST,
        ],
        default=SettingsConstants.MAINNET,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY_PATH)
    args = parser.parse_args(argv)

    try:
        mnemonic = _read_text_secret(args.mnemonic_file, "mnemonic file")
        passphrase = (
            _read_text_secret(args.passphrase_file, "passphrase file")
            if args.passphrase_file
            else ""
        )
        try:
            seed = Seed(mnemonic.split(), passphrase=passphrase)
        except (InvalidSeedException, ValueError, IndexError) as exc:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                f"SeedSigner rejected the mnemonic or passphrase: {exc}",
            ) from exc
        request_bytes = args.message.read_bytes()
        psbt_bytes = args.psbt.read_bytes()
        with AntiExfilNativeBackend(args.library) as backend:
            result = AntiExfilSignerController(seed, args.network, backend).process(
                request_bytes, psbt_bytes
            )
        encoded = result.response.encode()
        _write_new(args.output, encoded)
    except (AntiExfilProtocolError, AntiExfilNativeError, OSError) as exc:
        if isinstance(exc, AntiExfilProtocolError):
            code = exc.code.value
            message = exc.message
        elif isinstance(exc, AntiExfilNativeError):
            code = AntiExfilProtocolCode.NATIVE_BACKEND.value
            message = str(exc)
        else:
            code = AntiExfilProtocolCode.INVALID_MESSAGE.value
            message = str(exc)
        print(
            json.dumps(
                {
                    "status": "error",
                    "code": code,
                    "message": message,
                    "production_fallback": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "status": "ok",
                "backend": "native-secp256k1-zkp",
                "production_fallback": False,
                "output": str(args.output.resolve()),
                "response": result.response.diagnostic(),
                "input_index": result.context.input_index,
                "seed_fingerprint": result.context.fingerprint,
                "derivation": result.context.derivation,
                "input_amount": result.context.input_amount,
                "spend_amount": result.context.spend_amount,
                "fee_amount": result.context.fee_amount,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
