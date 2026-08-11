"""Terminal self-test for SeedSigner's required native anti-exfil backend."""

from __future__ import annotations

import argparse
import hmac
import json
import sys
from pathlib import Path

from seedsigner.helpers.anti_exfil import (
    DEFAULT_LIBRARY_PATH,
    AntiExfilNativeBackend,
    AntiExfilNativeError,
)


SECRET = bytes.fromhex("55" * 32)
MESSAGE = bytes.fromhex("88" * 32)
HOST_RANDOMNESS = bytes.fromhex("a5" * 32)
HOST_COMMITMENT = bytes.fromhex(
    "82c8c9669afb1cb40dd4b62e6c6130d57870608d01725932d3be71e20b8a4d4a"
)
EXPECTED_OPENING = bytes.fromhex(
    "02f52a1b7896219289fb3abc8431d57660d1ced351ca861e73e42db8ae9e42851f"
)
EXPECTED_SIGNATURE = bytes.fromhex(
    "3f49a74cec28d63a7a52e091a8173045ea49f34ab1c0aeb195e186e234e8b774"
    "73092b7b631933e9057421f3c883981347ab7fc822eb069ac53cb9865d2e8bb3"
)


def run_selftest(library_path: Path) -> dict[str, object]:
    with AntiExfilNativeBackend(library_path) as backend:
        opening = backend.signer_commit(SECRET, MESSAGE, HOST_COMMITMENT)
        signature = backend.sign(SECRET, MESSAGE, HOST_RANDOMNESS)

    opening_matches = hmac.compare_digest(opening, EXPECTED_OPENING)
    signature_matches = hmac.compare_digest(signature, EXPECTED_SIGNATURE)
    if not opening_matches or not signature_matches:
        raise AntiExfilNativeError("native anti-exfil pinned-vector mismatch")

    return {
        "status": "ok",
        "backend": "native-secp256k1-zkp",
        "library": str(library_path.resolve()),
        "opening_matches": opening_matches,
        "signature_matches": signature_matches,
        "production_fallback": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run SeedSigner's pinned native anti-exfil vectors"
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=DEFAULT_LIBRARY_PATH,
        help=f"absolute native library path (default: {DEFAULT_LIBRARY_PATH})",
    )
    args = parser.parse_args(argv)

    try:
        result = run_selftest(args.library)
    except AntiExfilNativeError as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "backend": "unavailable",
                    "error": str(exc),
                    "production_fallback": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
