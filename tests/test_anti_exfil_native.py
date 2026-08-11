import ctypes
import os
from pathlib import Path

import pytest

from seedsigner.helpers.anti_exfil import (
    AntiExfilInputError,
    AntiExfilNativeBackend,
    AntiExfilNativeError,
    AntiExfilUnavailableError,
)


NATIVE_LIBRARY_ENV = "SEEDSIGNER_ANTI_EXFIL_LIBRARY"
NATIVE_LIBRARY = os.environ.get(NATIVE_LIBRARY_ENV)

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


def test_missing_library_fails_closed(tmp_path):
    with pytest.raises(AntiExfilUnavailableError, match="required anti-exfil library"):
        AntiExfilNativeBackend(tmp_path / "missing.so")


def test_relative_library_path_is_rejected():
    with pytest.raises(AntiExfilUnavailableError, match="must be absolute"):
        AntiExfilNativeBackend(Path("libsecp256k1.so"))


def test_missing_required_symbol_fails_closed(tmp_path, monkeypatch):
    library = tmp_path / "wrong-library.so"
    library.touch()
    monkeypatch.setattr(ctypes, "CDLL", lambda path: object())
    with pytest.raises(AntiExfilUnavailableError, match="symbol is unavailable"):
        AntiExfilNativeBackend(library)


def test_bad_native_abi_fails_closed(tmp_path, monkeypatch):
    library = tmp_path / "wrong-abi.so"
    library.touch()

    def reject_abi(path):
        raise OSError("wrong ELF class")

    monkeypatch.setattr(ctypes, "CDLL", reject_abi)
    with pytest.raises(AntiExfilUnavailableError, match="wrong ELF class"):
        AntiExfilNativeBackend(library)


@pytest.mark.skipif(
    not NATIVE_LIBRARY or not Path(NATIVE_LIBRARY).is_file(),
    reason=f"set {NATIVE_LIBRARY_ENV} to the pinned native library",
)
def test_pinned_native_vectors_and_fail_closed_inputs():
    with AntiExfilNativeBackend(Path(NATIVE_LIBRARY)) as backend:
        assert backend.host_commit(HOST_RANDOMNESS) == HOST_COMMITMENT
        assert backend.signer_commit(SECRET, MESSAGE, HOST_COMMITMENT) == EXPECTED_OPENING
        assert backend.sign(SECRET, MESSAGE, HOST_RANDOMNESS) == EXPECTED_SIGNATURE

        with pytest.raises(AntiExfilInputError, match="secret key must be 32 bytes"):
            backend.sign(SECRET[:-1], MESSAGE, HOST_RANDOMNESS)
        with pytest.raises(AntiExfilInputError, match="message hash must be bytes"):
            backend.sign(SECRET, bytearray(MESSAGE), HOST_RANDOMNESS)
        with pytest.raises(AntiExfilNativeError, match="native anti-exfil signing failed"):
            backend.sign(bytes(32), MESSAGE, HOST_RANDOMNESS)

    with pytest.raises(AntiExfilUnavailableError, match="backend is closed"):
        backend.sign(SECRET, MESSAGE, HOST_RANDOMNESS)
