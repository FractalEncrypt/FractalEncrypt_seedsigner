import hashlib
import pytest
from seedsigner.helpers.anti_exfil_protocol import AntiExfilProtocolCode, AntiExfilProtocolError
from seedsigner.helpers.anti_exfil_protocol_v1 import Network, ProtocolMessage, SigningSlot, Stage, decode_message
from seedsigner.helpers.anti_exfil_signer_v1 import derive_signing_contexts
from seedsigner.helpers.anti_exfil_transport import AntiExfilTransportPackage, TransportNetwork
from seedsigner.models.anti_exfil_state import AntiExfilFlowPhase, AntiExfilFlowState
from seedsigner.models.decode_qr import DecodeQR, DecodeQRStatus
from seedsigner.models.encode_qr import AntiExfilQrEncoder
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants
from test_anti_exfil_protocol import GENERATOR, HOST_RANDOMNESS, MNEMONIC, SESSION_ID, FakeNativeBackend, build_fixture, make_commit

def make_round_one():
    psbt = build_fixture(); raw = psbt.serialize(); seed = Seed(MNEMONIC.split())
    _, contexts = derive_signing_contexts(raw, seed, SettingsConstants.REGTEST)
    message = make_commit(raw, contexts)
    return seed, contexts, AntiExfilTransportPackage(message.encode(), TransportNetwork.REGTEST, raw)

def make_round_two_request():
    seed, contexts, package = make_round_one()
    first = AntiExfilFlowState.from_package(package)
    openings = first.create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend())
    opening_message = decode_message(openings.message)
    slots = tuple(SigningSlot(slot.input_index, slot.signer_pubkey, slot.message_hash, 1,
        slot.commitment, opening=opening.opening, rho=bytes([0xa0+i])*32)
        for i, (slot, opening) in enumerate(zip(decode_message(package.message).slots, opening_message.slots)))
    reveal = ProtocolMessage(Network.REGTEST, Stage.HOST_REVEAL, SESSION_ID,
                             hashlib.sha256(package.psbt).digest(), slots)
    return seed, AntiExfilTransportPackage(reveal.encode(), TransportNetwork.REGTEST, package.psbt)

def make_round_two_response():
    seed, request = make_round_two_request()
    return AntiExfilFlowState.from_package(request).create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend())

def test_round_one_state_emits_complete_opening_set():
    seed, contexts, package = make_round_one(); state = AntiExfilFlowState.from_package(package)
    assert state.phase == AntiExfilFlowPhase.REQUEST_LOADED and state.round_number == 1
    response = state.create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend())
    message = decode_message(response.message)
    assert response.psbt is None and len(message.slots) == len(contexts) == 5
    assert all(slot.opening == GENERATOR for slot in message.slots)

def test_round_two_resumes_statelessly_and_returns_no_psbt():
    seed, request = make_round_two_request(); resumed = AntiExfilFlowState.from_package(request)
    response = resumed.create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend())
    assert resumed.round_number == 2 and response.psbt is None
    assert decode_message(response.message).stage == Stage.SIGNER_SIGNATURES

def test_response_cannot_be_reused_as_request_or_created_twice():
    seed, _, package = make_round_one(); state = AntiExfilFlowState.from_package(package)
    response = state.create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend())
    with pytest.raises(AntiExfilProtocolError) as repeated:
        state.create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend())
    assert repeated.value.code == AntiExfilProtocolCode.WRONG_STAGE
    with pytest.raises(AntiExfilProtocolError): AntiExfilFlowState.from_package(response)

def test_truncated_psbt_is_a_controlled_protocol_error():
    _, _, package = make_round_one()
    truncated = AntiExfilTransportPackage(
        package.message,
        package.network,
        package.psbt[:-1],
    )
    with pytest.raises(AntiExfilProtocolError) as failure:
        AntiExfilFlowState.from_package(truncated)
    assert failure.value.code == AntiExfilProtocolCode.INVALID_MESSAGE

def test_both_response_stages_round_trip_as_anti_exfil_qr():
    seed, _, request = make_round_one()
    responses = [AntiExfilFlowState.from_package(request).create_response(seed=seed, network=SettingsConstants.REGTEST, backend=FakeNativeBackend()), make_round_two_response()]
    for response in responses:
        encoder, decoder = AntiExfilQrEncoder(package=response), DecodeQR()
        for _ in range(encoder.seq_len() * 2):
            if decoder.add_data(encoder.next_part()) == DecodeQRStatus.COMPLETE: break
        assert decoder.is_complete and decoder.is_anti_exfil and not decoder.is_psbt
        assert decoder.get_anti_exfil_package(SettingsConstants.REGTEST).encode() == response.encode()
