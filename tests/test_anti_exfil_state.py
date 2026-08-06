import hashlib

import pytest

from seedsigner.helpers.anti_exfil_protocol import (
    AntiExfilMessage,
    AntiExfilProtocolCode,
    AntiExfilProtocolError,
    Stage,
    decode_message,
    derive_signing_context,
)
from seedsigner.helpers.anti_exfil_transport import (
    AntiExfilTransportPackage,
    TransportNetwork,
)
from seedsigner.models.anti_exfil_state import AntiExfilFlowPhase, AntiExfilFlowState
from seedsigner.models.decode_qr import DecodeQR, DecodeQRStatus
from seedsigner.models.encode_qr import AntiExfilQrEncoder
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants

from test_anti_exfil_protocol import (
    GENERATOR,
    HOST_RANDOMNESS,
    MNEMONIC,
    SESSION_ID,
    FakeNativeBackend,
    build_fixture,
    tagged_host_commitment,
)


def make_round_one():
    psbt = build_fixture()
    psbt_bytes = psbt.serialize()
    seed = Seed(MNEMONIC.split())
    _, context = derive_signing_context(psbt_bytes, seed, SettingsConstants.REGTEST)
    message = AntiExfilMessage(
        stage=Stage.HOST_COMMIT,
        session_id=SESSION_ID,
        message_hash=context.message_hash,
        signer_pubkey=context.signer_pubkey,
        commitment=tagged_host_commitment(HOST_RANDOMNESS),
    )
    package = AntiExfilTransportPackage(
        message=message.encode(),
        network=TransportNetwork.REGTEST,
        psbt=psbt_bytes,
    )
    return seed, context, package


def make_round_two_request():
    seed, context, package = make_round_one()
    first_state = AntiExfilFlowState.from_package(package)
    first_state.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )
    opening_message = first_state.result.response
    reveal = AntiExfilMessage(
        stage=Stage.HOST_REVEAL,
        session_id=SESSION_ID,
        message_hash=context.message_hash,
        signer_pubkey=context.signer_pubkey,
        commitment=opening_message.commitment,
        opening=opening_message.opening,
        host_randomness=HOST_RANDOMNESS,
    )
    return seed, AntiExfilTransportPackage(
        message=reveal.encode(),
        network=TransportNetwork.REGTEST,
        psbt=package.psbt,
    )


def make_round_two_response():
    seed, request = make_round_two_request()
    resumed = AntiExfilFlowState.from_package(request)
    return resumed.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )


def test_round_one_state_emits_opening_only():
    seed, _, package = make_round_one()
    state = AntiExfilFlowState.from_package(package)
    assert state.phase == AntiExfilFlowPhase.REQUEST_LOADED
    assert state.round_number == 1
    assert state.session_fingerprint == SESSION_ID[:4].hex().upper()
    assert state.transaction_fingerprint == hashlib.sha256(package.psbt).digest()[:4].hex().upper()

    response = state.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )
    assert state.phase == AntiExfilFlowPhase.RESPONSE_READY
    assert response.psbt is None
    assert state.result.response.stage == Stage.SIGNER_OPENINGS
    assert state.result.response.opening == GENERATOR


def test_round_two_can_resume_from_package_after_power_cycle():
    seed, context, package = make_round_one()
    first_state = AntiExfilFlowState.from_package(package)
    opening = first_state.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    ).message
    opening_message = first_state.result.response

    reveal = AntiExfilMessage(
        stage=Stage.HOST_REVEAL,
        session_id=SESSION_ID,
        message_hash=context.message_hash,
        signer_pubkey=context.signer_pubkey,
        commitment=opening_message.commitment,
        opening=opening_message.opening,
        host_randomness=HOST_RANDOMNESS,
    )
    # A brand-new state object models a device process restart between rounds.
    resumed = AntiExfilFlowState.from_package(
        AntiExfilTransportPackage(
            message=reveal.encode(),
            network=TransportNetwork.REGTEST,
            psbt=package.psbt,
        )
    )
    response = resumed.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )
    assert opening
    assert resumed.round_number == 2
    assert resumed.result.response.stage == Stage.SIGNER_SIGNATURES
    assert response.psbt is None


def test_response_cannot_be_created_twice():
    seed, _, package = make_round_one()
    state = AntiExfilFlowState.from_package(package)
    state.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )
    with pytest.raises(AntiExfilProtocolError) as raised:
        state.create_response(
            seed=seed,
            network=SettingsConstants.REGTEST,
            backend=FakeNativeBackend(),
        )
    assert raised.value.code == AntiExfilProtocolCode.WRONG_STAGE


def test_response_stage_is_not_an_inbound_request():
    seed, _, package = make_round_one()
    state = AntiExfilFlowState.from_package(package)
    response = state.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )
    with pytest.raises(AntiExfilProtocolError) as raised:
        AntiExfilFlowState.from_package(response)
    assert raised.value.code == AntiExfilProtocolCode.WRONG_STAGE


def test_response_encoder_round_trips_as_anti_exfil_not_psbt():
    seed, _, package = make_round_one()
    state = AntiExfilFlowState.from_package(package)
    response = state.create_response(
        seed=seed,
        network=SettingsConstants.REGTEST,
        backend=FakeNativeBackend(),
    )
    encoder = AntiExfilQrEncoder(package=response)
    decoder = DecodeQR()
    for _ in range(encoder.seq_len() * 2):
        status = decoder.add_data(encoder.next_part())
        if status == DecodeQRStatus.COMPLETE:
            break
    assert decoder.is_complete
    assert decoder.is_anti_exfil
    assert not decoder.is_psbt
    decoded = decoder.get_anti_exfil_package(SettingsConstants.REGTEST)
    assert decoded.encode() == response.encode()


def test_signature_response_encoder_round_trips_all_source_fragments():
    response = make_round_two_response()
    assert decode_message(response.message).stage == Stage.SIGNER_SIGNATURES
    encoder = AntiExfilQrEncoder(package=response)
    decoder = DecodeQR()
    sequence_components = []
    for _ in range(encoder.seq_len()):
        part = encoder.next_part()
        sequence_components.append(part.split("/")[1])
        decoder.add_data(part)
    assert sequence_components == [
        f"{index}-{encoder.seq_len()}" for index in range(1, encoder.seq_len() + 1)
    ]
    assert decoder.is_complete
    decoded = decoder.get_anti_exfil_package(SettingsConstants.REGTEST)
    assert decoded.encode() == response.encode()
