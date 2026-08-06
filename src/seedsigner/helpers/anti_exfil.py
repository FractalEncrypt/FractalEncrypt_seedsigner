"""Fail-closed binding for SeedSigner's native ECDSA anti-exfil primitive.

The native library is built by SeedSigner OS from the pinned secp256k1-zkp
revision. This module intentionally has no Python or ordinary-ECDSA fallback.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path


DEFAULT_LIBRARY_PATH = Path("/usr/lib/seedsigner/libsecp256k1.so.0")
CONTEXT_SIGN_VERIFY = 0x301
OPAQUE_STRUCT_SIZE = 64

_Byte = ctypes.c_ubyte
_BytePointer = ctypes.POINTER(_Byte)


class AntiExfilNativeError(RuntimeError):
    """Base error for the required native anti-exfil backend."""


class AntiExfilUnavailableError(AntiExfilNativeError):
    """The required library, ABI, or symbol set is unavailable."""


class AntiExfilInputError(AntiExfilNativeError):
    """A caller supplied a malformed fixed-width cryptographic value."""


def _input_buffer(value: bytes, expected_length: int, name: str):
    if not isinstance(value, bytes):
        raise AntiExfilInputError(f"{name} must be bytes")
    if len(value) != expected_length:
        raise AntiExfilInputError(f"{name} must be {expected_length} bytes")
    return (_Byte * expected_length).from_buffer_copy(value)


def _clear(buffer) -> None:
    ctypes.memset(buffer, 0, ctypes.sizeof(buffer))


class AntiExfilNativeBackend:
    """Own a randomized secp256k1 context and expose signer-only operations."""

    def __init__(self, library_path: Path | str = DEFAULT_LIBRARY_PATH):
        path = Path(library_path)
        if not path.is_absolute():
            raise AntiExfilUnavailableError("anti-exfil library path must be absolute")
        self.library_path = path.resolve()
        self._library = None
        self._context = None

        if not self.library_path.is_file():
            raise AntiExfilUnavailableError(
                f"required anti-exfil library is missing: {self.library_path}"
            )

        try:
            self._library = ctypes.CDLL(os.fspath(self.library_path))
            self._bind_required_symbols()
            self._context = self._library.secp256k1_context_create(CONTEXT_SIGN_VERIFY)
        except (OSError, AttributeError) as exc:
            self.close()
            raise AntiExfilUnavailableError(
                f"required anti-exfil library or symbol is unavailable: {exc}"
            ) from exc

        if not self._context:
            raise AntiExfilUnavailableError("anti-exfil context creation failed")

        randomization = (_Byte * 32).from_buffer_copy(os.urandom(32))
        try:
            if self._library.secp256k1_context_randomize(
                self._context, randomization
            ) != 1:
                self.close()
                raise AntiExfilUnavailableError(
                    "anti-exfil context randomization failed"
                )
        finally:
            _clear(randomization)

    def _bind_required_symbols(self) -> None:
        library = self._library

        library.secp256k1_context_create.argtypes = [ctypes.c_uint]
        library.secp256k1_context_create.restype = ctypes.c_void_p
        library.secp256k1_context_destroy.argtypes = [ctypes.c_void_p]
        library.secp256k1_context_destroy.restype = None
        library.secp256k1_context_randomize.argtypes = [
            ctypes.c_void_p,
            _BytePointer,
        ]
        library.secp256k1_context_randomize.restype = ctypes.c_int

        library.secp256k1_ecdsa_anti_exfil_host_commit.argtypes = [
            ctypes.c_void_p,
            _BytePointer,
            _BytePointer,
        ]
        library.secp256k1_ecdsa_anti_exfil_host_commit.restype = ctypes.c_int

        library.secp256k1_ecdsa_anti_exfil_signer_commit.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            _BytePointer,
            _BytePointer,
            _BytePointer,
        ]
        library.secp256k1_ecdsa_anti_exfil_signer_commit.restype = ctypes.c_int
        library.secp256k1_ecdsa_s2c_opening_serialize.argtypes = [
            ctypes.c_void_p,
            _BytePointer,
            ctypes.c_void_p,
        ]
        library.secp256k1_ecdsa_s2c_opening_serialize.restype = ctypes.c_int
        library.secp256k1_anti_exfil_sign.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            _BytePointer,
            _BytePointer,
            _BytePointer,
        ]
        library.secp256k1_anti_exfil_sign.restype = ctypes.c_int
        library.secp256k1_ecdsa_signature_serialize_compact.argtypes = [
            ctypes.c_void_p,
            _BytePointer,
            ctypes.c_void_p,
        ]
        library.secp256k1_ecdsa_signature_serialize_compact.restype = ctypes.c_int

    def close(self) -> None:
        if self._context and self._library:
            self._library.secp256k1_context_destroy(self._context)
        self._context = None

    def __enter__(self) -> "AntiExfilNativeBackend":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _require_context(self) -> None:
        if not self._context or not self._library:
            raise AntiExfilUnavailableError("anti-exfil backend is closed")

    def host_commit(self, host_randomness: bytes) -> bytes:
        """Return the 32-byte tagged commitment to the host's nonce contribution."""

        self._require_context()
        randomness = _input_buffer(host_randomness, 32, "host randomness")
        commitment = (_Byte * 32)()
        if self._library.secp256k1_ecdsa_anti_exfil_host_commit(
            self._context, commitment, randomness
        ) != 1:
            raise AntiExfilNativeError("native host commitment failed")
        return bytes(commitment)

    def signer_commit(
        self, secret_key: bytes, message_hash: bytes, host_commitment: bytes
    ) -> bytes:
        """Return the 33-byte serialized signer opening for protocol message 2."""

        self._require_context()
        secret = _input_buffer(secret_key, 32, "secret key")
        message = _input_buffer(message_hash, 32, "message hash")
        commitment = _input_buffer(host_commitment, 32, "host commitment")
        opening = (_Byte * OPAQUE_STRUCT_SIZE)()
        serialized = (_Byte * 33)()
        try:
            if self._library.secp256k1_ecdsa_anti_exfil_signer_commit(
                self._context,
                opening,
                message,
                secret,
                commitment,
            ) != 1:
                raise AntiExfilNativeError("native signer commitment failed")
            if self._library.secp256k1_ecdsa_s2c_opening_serialize(
                self._context, serialized, opening
            ) != 1:
                raise AntiExfilNativeError("native opening serialization failed")
            return bytes(serialized)
        finally:
            _clear(secret)
            _clear(opening)

    def sign(
        self, secret_key: bytes, message_hash: bytes, host_randomness: bytes
    ) -> bytes:
        """Return a 64-byte compact anti-exfil signature for protocol message 4."""

        self._require_context()
        secret = _input_buffer(secret_key, 32, "secret key")
        message = _input_buffer(message_hash, 32, "message hash")
        randomness = _input_buffer(host_randomness, 32, "host randomness")
        signature = (_Byte * OPAQUE_STRUCT_SIZE)()
        serialized = (_Byte * 64)()
        try:
            if self._library.secp256k1_anti_exfil_sign(
                self._context,
                signature,
                message,
                secret,
                randomness,
            ) != 1:
                raise AntiExfilNativeError("native anti-exfil signing failed")
            if self._library.secp256k1_ecdsa_signature_serialize_compact(
                self._context, serialized, signature
            ) != 1:
                raise AntiExfilNativeError("native signature serialization failed")
            return bytes(serialized)
        finally:
            _clear(secret)
            _clear(signature)
