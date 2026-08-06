"""Shared protocol errors and terminal entry point for frozen anti-exfil v1."""

from __future__ import annotations
import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from seedsigner.helpers.anti_exfil import DEFAULT_LIBRARY_PATH, AntiExfilNativeBackend, AntiExfilNativeError
from seedsigner.models.seed import InvalidSeedException, Seed
from seedsigner.models.settings import SettingsConstants

class AntiExfilProtocolCode(str, Enum):
    INVALID_MESSAGE = "AE_INVALID_MESSAGE"
    WRONG_STAGE = "AE_WRONG_STAGE"
    SESSION_MISMATCH = "AE_SESSION_MISMATCH"
    TRANSACTION_MISMATCH = "AE_TRANSACTION_MISMATCH"
    SIGNATURE_SLOT_MISMATCH = "AE_SIGNATURE_SLOT_MISMATCH"
    SIGNING_MODE_MISMATCH = "AE_SIGNING_MODE_MISMATCH"
    COMMITMENT_MISMATCH = "AE_COMMITMENT_MISMATCH"
    OPENING_MISMATCH = "AE_OPENING_MISMATCH"
    SIGNATURE_INVALID = "AE_SIGNATURE_INVALID"
    RETRY_CONFLICT = "AE_RETRY_CONFLICT"
    NATIVE_BACKEND = "AE_NATIVE_BACKEND"
    OUTPUT_EXISTS = "AE_OUTPUT_EXISTS"

class AntiExfilProtocolError(RuntimeError):
    def __init__(self, code: AntiExfilProtocolCode, message: str):
        super().__init__(message); self.code, self.message = code, message

def _read(path: Path, text=False):
    try: value = path.read_text(encoding="utf-8").strip() if text else path.read_bytes()
    except OSError as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"cannot read {path}: {exc}") from exc
    if not value: raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"{path} is empty")
    return value

def _write_new(path: Path, value: bytes):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as output: output.write(value)
    except FileExistsError as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.OUTPUT_EXISTS, f"refusing to replace {path}") from exc

def main(argv=None):
    parser = argparse.ArgumentParser(description="Process one frozen multi-slot anti-exfil signer stage")
    parser.add_argument("--psbt", type=Path, required=True); parser.add_argument("--message", type=Path, required=True)
    parser.add_argument("--mnemonic-file", type=Path, required=True); parser.add_argument("--passphrase-file", type=Path)
    parser.add_argument("--network", choices=[SettingsConstants.MAINNET, SettingsConstants.TESTNET,
                        SettingsConstants.TESTNET4, SettingsConstants.SIGNET,
                        SettingsConstants.REGTEST], default=SettingsConstants.MAINNET)
    parser.add_argument("--output", type=Path, required=True); parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY_PATH)
    args = parser.parse_args(argv)
    try:
        try: seed = Seed(_read(args.mnemonic_file, True).split(), passphrase=_read(args.passphrase_file, True) if args.passphrase_file else "")
        except (InvalidSeedException, ValueError, IndexError) as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"invalid seed: {exc}") from exc
        from seedsigner.helpers.anti_exfil_signer_v1 import AntiExfilSignerController
        with AntiExfilNativeBackend(args.library) as backend:
            result = AntiExfilSignerController(seed, args.network, backend).process(_read(args.message), _read(args.psbt))
        encoded = result.response.encode(); _write_new(args.output, encoded)
    except (AntiExfilProtocolError, AntiExfilNativeError, OSError) as exc:
        code = exc.code.value if isinstance(exc, AntiExfilProtocolError) else AntiExfilProtocolCode.NATIVE_BACKEND.value
        print(json.dumps({"status":"error", "code":code, "message":str(exc), "production_fallback":False}), file=sys.stderr)
        return 1
    print(json.dumps({"status":"ok", "backend":"native-secp256k1-zkp", "production_fallback":False,
                      "output":str(args.output.resolve()), "response":result.response.diagnostic(),
                      "slots":[{"input_index":c.input_index,"seed_fingerprint":c.fingerprint,
                                "derivation":c.derivation,"script_kind":c.script_kind} for c in result.contexts]}, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
