"""In-memory state machine for one SeedSigner anti-exfil request/response."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib

from embit.psbt import PSBT

from seedsigner.helpers.anti_exfil import AntiExfilNativeBackend
from seedsigner.helpers.anti_exfil_protocol import AntiExfilProtocolCode, AntiExfilProtocolError
from seedsigner.helpers.anti_exfil_protocol_v1 import Stage, decode_message
from seedsigner.helpers.anti_exfil_signer_v1 import AntiExfilSignerController, ControllerResult
from seedsigner.helpers.anti_exfil_transport import AntiExfilTransportPackage
from seedsigner.models.seed import Seed


class AntiExfilFlowPhase(str, Enum):
    REQUEST_LOADED = "request_loaded"
    RESPONSE_READY = "response_ready"


@dataclass(slots=True)
class AntiExfilFlowState:
    """Hold only public request/response data; no secret session state is persisted."""

    request_package: AntiExfilTransportPackage
    request_psbt: PSBT
    phase: AntiExfilFlowPhase = AntiExfilFlowPhase.REQUEST_LOADED
    response_package: AntiExfilTransportPackage | None = None
    result: ControllerResult | None = None

    @classmethod
    def from_package(cls, package: AntiExfilTransportPackage) -> "AntiExfilFlowState":
        message = decode_message(package.message)
        if message.stage not in {Stage.HOST_COMMIT, Stage.HOST_REVEAL}:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.WRONG_STAGE,
                "SeedSigner accepts only coordinator messages 1 and 3",
            )
        if package.psbt is None:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                "anti-exfil coordinator request is missing its PSBT",
            )
        try:
            psbt = PSBT.parse(package.psbt)
        # embit can raise RuntimeError/EOF-style exceptions for truncated
        # untrusted streams in addition to its documented PSBTError family.
        # No parser exception may escape the controlled protocol-error path.
        except Exception as exc:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                f"invalid anti-exfil PSBT: {exc}",
            ) from exc
        if psbt.serialize() != package.psbt:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.INVALID_MESSAGE,
                "anti-exfil PSBT is not in canonical embit representation",
            )
        return cls(request_package=package, request_psbt=psbt)

    @property
    def request(self):
        return decode_message(self.request_package.message)

    @property
    def request_stage(self) -> Stage:
        return self.request.stage

    @property
    def round_number(self) -> int:
        return 1 if self.request_stage == Stage.HOST_COMMIT else 2

    @property
    def session_fingerprint(self) -> str:
        return self.request.session_id[:4].hex().upper()

    @property
    def transaction_fingerprint(self) -> str:
        return hashlib.sha256(self.request_package.psbt or b"").digest()[:4].hex().upper()

    def create_response(
        self,
        *,
        seed: Seed,
        network: str,
        backend=None,
    ) -> AntiExfilTransportPackage:
        if self.phase != AntiExfilFlowPhase.REQUEST_LOADED or self.response_package:
            raise AntiExfilProtocolError(
                AntiExfilProtocolCode.WRONG_STAGE,
                "anti-exfil response has already been created",
            )

        owns_backend = backend is None
        if backend is None:
            backend = AntiExfilNativeBackend()
        try:
            signer = AntiExfilSignerController(seed, network, backend)
            result = signer.process(
                self.request_package.message,
                self.request_package.psbt,
            )
        finally:
            if owns_backend:
                backend.close()

        response = AntiExfilTransportPackage(
            message=result.response.encode(),
            network=self.request_package.network,
            psbt=None,
        )
        # Force all response transport invariants before making the transition.
        response.encode()
        self.result = result
        self.response_package = response
        self.phase = AntiExfilFlowPhase.RESPONSE_READY
        return response

    def validate_for_review(self, *, seed: Seed, network: str):
        """Fail closed before the stock PSBT review parser sees the request."""

        signer = AntiExfilSignerController(seed, network, backend=None)
        return signer.validate_request(
            self.request_package.message,
            self.request_package.psbt,
        )
