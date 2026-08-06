import hashlib

import pytest

from seedsigner.helpers.anti_exfil_protocol_v1 import Network, ProtocolMessage, SigningSlot, Stage
from seedsigner.helpers.anti_exfil_transport import (
    AntiExfilTransportPackage,
    TransportNetwork,
    UR_TYPE,
)
from seedsigner.helpers.ur2.ur import UR
from seedsigner.helpers.ur2.ur_encoder import UREncoder
from seedsigner.models.decode_qr import DecodeQR, DecodeQRStatus
from seedsigner.models.qr_type import QRType
from seedsigner.models.settings_definition import SettingsConstants


SIGNER_PUBKEY = bytes.fromhex(
    "029ac20335eb38768d2052be1dbbc3c8f6178407458e51e6b4ad22f1d91758895b"
)


def host_commit_package():
    psbt = b"psbt\xff"
    message = ProtocolMessage(
        network=Network.TESTNET3, stage=Stage.HOST_COMMIT,
        session_id=bytes.fromhex("c3" * 32), psbt_digest=hashlib.sha256(psbt).digest(),
        slots=(SigningSlot(0, SIGNER_PUBKEY, bytes.fromhex("88" * 32), 1,
                           hashlib.sha256(bytes.fromhex("a5" * 32)).digest()),),
    ).encode()
    return AntiExfilTransportPackage(
        message=message,
        network=TransportNetwork.TESTNET,
        psbt=psbt,
    )


def qr_frames(package):
    encoder = UREncoder(
        UR(UR_TYPE, bytearray(package.to_cbor())),
        max_fragment_len=30,
    )
    count = 1 if encoder.is_single_part() else encoder.fountain_encoder.seq_len() * 2
    return [encoder.next_part().upper() for _ in range(count)]


def test_detect_and_decode_anti_exfil_qr_without_entering_psbt_path():
    package = host_commit_package()
    frames = qr_frames(package)
    decoder = DecodeQR()
    for frame in frames:
        status = decoder.add_data(frame)
        assert decoder.qr_type == QRType.ANTI_EXFIL__UR
        if status == DecodeQRStatus.COMPLETE:
            break

    assert decoder.is_complete
    assert decoder.is_anti_exfil
    assert not decoder.is_psbt
    assert decoder.get_psbt() is None
    recovered = decoder.get_anti_exfil_package(SettingsConstants.TESTNET)
    assert recovered == package


def test_anti_exfil_qr_network_mismatch_fails_closed():
    decoder = DecodeQR()
    for frame in qr_frames(host_commit_package()):
        if decoder.add_data(frame) == DecodeQRStatus.COMPLETE:
            break
    with pytest.raises(Exception, match="active network"):
        decoder.get_anti_exfil_package(SettingsConstants.MAINNET)


def test_transport_rejects_digest_change_and_response_psbt():
    encoded = bytearray(host_commit_package().encode())
    encoded[-1] ^= 1
    with pytest.raises(Exception, match="digest mismatch"):
        AntiExfilTransportPackage.decode(bytes(encoded))

    response = ProtocolMessage(
        Network.TESTNET3, Stage.SIGNER_OPENINGS, bytes.fromhex("c3" * 32),
        hashlib.sha256(b"psbt\xff").digest(),
        (SigningSlot(0, SIGNER_PUBKEY, bytes.fromhex("88" * 32), 1,
                     hashlib.sha256(bytes.fromhex("a5" * 32)).digest(), opening=SIGNER_PUBKEY),),
    ).encode()
    with pytest.raises(Exception, match="forbids PSBT"):
        AntiExfilTransportPackage(
            response,
            TransportNetwork.TESTNET,
            b"psbt\xff",
        ).encode()


def test_cbor_must_be_canonical_byte_string():
    package = host_commit_package()
    with pytest.raises(Exception, match="not a CBOR byte string"):
        AntiExfilTransportPackage.from_cbor(b"\x80")
    encoded = package.to_cbor()
    with pytest.raises(Exception, match="does not match payload"):
        AntiExfilTransportPackage.from_cbor(encoded + b"\x00")
