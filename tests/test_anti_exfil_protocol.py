import hashlib
import os
from pathlib import Path

import pytest
from embit import bip32, bip39, ec, script
from embit.networks import NETWORKS
from embit.psbt import DerivationPath, PSBT
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput

from seedsigner.helpers.anti_exfil import AntiExfilNativeBackend
from seedsigner.helpers.anti_exfil_protocol import (
    AntiExfilMessage,
    AntiExfilProtocolCode,
    AntiExfilProtocolError,
    AntiExfilSignerController,
    Stage,
    decode_message,
    derive_signing_context,
    main,
)
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants


MNEMONIC = "model ensure search plunge galaxy firm exclude brain satoshi meadow cable roast"
DERIVATION = "m/84h/1h/0h/0/0"
SESSION_ID = bytes.fromhex("c3" * 32)
HOST_RANDOMNESS = bytes.fromhex("a5" * 32)
GENERATOR = bytes.fromhex(
    "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
)
VALID_SIGNATURE = (1).to_bytes(32, "big") + (1).to_bytes(32, "big")
NATIVE_LIBRARY = os.environ.get("SEEDSIGNER_ANTI_EXFIL_LIBRARY")


def tagged_host_commitment(host_randomness):
    tag_hash = hashlib.sha256(b"s2c/ecdsa/data").digest()
    return hashlib.sha256(tag_hash + tag_hash + host_randomness).digest()


def build_fixture():
    root = bip32.HDKey.from_seed(
        bip39.mnemonic_to_seed(MNEMONIC), version=NETWORKS["regtest"]["xprv"]
    )
    derivation = bip32.parse_path(DERIVATION)
    signer = root.derive(derivation).key.get_public_key()
    destination = ec.PrivateKey(bytes.fromhex("44" * 32)).get_public_key()
    transaction = Transaction(
        version=2,
        vin=[
            TransactionInput(
                txid=bytes.fromhex("22" * 32),
                vout=0,
                sequence=0xFFFFFFFD,
            )
        ],
        vout=[TransactionOutput(90_000, script.p2wpkh(destination))],
        locktime=0,
    )
    psbt = PSBT(transaction)
    psbt.inputs[0].witness_utxo = TransactionOutput(100_000, script.p2wpkh(signer))
    psbt.inputs[0].sighash_type = SIGHASH.ALL
    psbt.inputs[0].bip32_derivations[signer] = DerivationPath(
        root.my_fingerprint, derivation
    )
    return psbt


class FakeNativeBackend:
    def host_commit(self, host_randomness):
        return tagged_host_commitment(host_randomness)

    def signer_commit(self, secret_key, message_hash, commitment):
        return GENERATOR

    def sign(self, secret_key, message_hash, host_randomness):
        return VALID_SIGNATURE


@pytest.fixture
def fixture_context():
    psbt = build_fixture()
    psbt_bytes = psbt.serialize()
    seed = Seed(MNEMONIC.split())
    _, context = derive_signing_context(psbt_bytes, seed, SettingsConstants.REGTEST)
    controller = AntiExfilSignerController(
        seed, SettingsConstants.REGTEST, FakeNativeBackend()
    )
    commitment = tagged_host_commitment(HOST_RANDOMNESS)
    message_one = AntiExfilMessage(
        stage=Stage.HOST_COMMIT,
        session_id=SESSION_ID,
        message_hash=context.message_hash,
        signer_pubkey=context.signer_pubkey,
        commitment=commitment,
    )
    return psbt, psbt_bytes, context, controller, message_one


def test_message_is_canonical_and_trailing_data_is_rejected(fixture_context):
    _, _, _, _, message_one = fixture_context
    encoded = message_one.encode()
    assert decode_message(encoded) == message_one
    with pytest.raises(AntiExfilProtocolError) as raised:
        decode_message(encoded + b"\x00")
    assert raised.value.code == AntiExfilProtocolCode.INVALID_MESSAGE

    malformed = AntiExfilMessage(
        stage=Stage.HOST_REVEAL,
        session_id=message_one.session_id,
        message_hash=message_one.message_hash,
        signer_pubkey=message_one.signer_pubkey,
        commitment=message_one.commitment,
        opening=GENERATOR,
        host_randomness=bytearray(HOST_RANDOMNESS),
    )
    with pytest.raises(AntiExfilProtocolError) as raised:
        malformed.encode()
    assert raised.value.code == AntiExfilProtocolCode.INVALID_MESSAGE


def test_controller_completes_both_signer_stages_deterministically(fixture_context):
    _, psbt_bytes, _, controller, message_one = fixture_context
    first_opening = controller.process(message_one.encode(), psbt_bytes).response
    retry_opening = controller.process(message_one.encode(), psbt_bytes).response
    assert first_opening == retry_opening
    assert first_opening.stage == Stage.SIGNER_OPENINGS

    reveal = AntiExfilMessage(
        stage=Stage.HOST_REVEAL,
        session_id=message_one.session_id,
        message_hash=message_one.message_hash,
        signer_pubkey=message_one.signer_pubkey,
        commitment=message_one.commitment,
        opening=first_opening.opening,
        host_randomness=HOST_RANDOMNESS,
    )
    first_signature = controller.process(reveal.encode(), psbt_bytes).response
    retry_signature = controller.process(reveal.encode(), psbt_bytes).response
    assert first_signature == retry_signature
    assert first_signature.stage == Stage.SIGNER_SIGNATURES
    assert first_signature.signature == VALID_SIGNATURE


def test_response_stage_is_rejected_by_signer(fixture_context):
    _, psbt_bytes, _, controller, message_one = fixture_context
    response = controller.process(message_one.encode(), psbt_bytes).response
    with pytest.raises(AntiExfilProtocolError) as raised:
        controller.process(response.encode(), psbt_bytes)
    assert raised.value.code == AntiExfilProtocolCode.WRONG_STAGE


def test_changed_transaction_is_rejected(fixture_context):
    psbt, _, _, controller, message_one = fixture_context
    # PSBT.tx is a reconstructed view; OutputScope is the serialized authority.
    psbt.outputs[0].value -= 1
    with pytest.raises(AntiExfilProtocolError) as raised:
        controller.process(message_one.encode(), psbt.serialize())
    assert raised.value.code == AntiExfilProtocolCode.TRANSACTION_MISMATCH


def test_changed_signer_key_is_rejected(fixture_context):
    _, psbt_bytes, _, controller, message_one = fixture_context
    changed = AntiExfilMessage(
        stage=message_one.stage,
        session_id=message_one.session_id,
        message_hash=message_one.message_hash,
        signer_pubkey=GENERATOR,
        commitment=message_one.commitment,
    )
    with pytest.raises(AntiExfilProtocolError) as raised:
        controller.process(changed.encode(), psbt_bytes)
    assert raised.value.code == AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH


def test_changed_host_reveal_is_rejected(fixture_context):
    _, psbt_bytes, _, controller, message_one = fixture_context
    opening = controller.process(message_one.encode(), psbt_bytes).response.opening
    reveal = AntiExfilMessage(
        stage=Stage.HOST_REVEAL,
        session_id=message_one.session_id,
        message_hash=message_one.message_hash,
        signer_pubkey=message_one.signer_pubkey,
        commitment=message_one.commitment,
        opening=opening,
        host_randomness=HOST_RANDOMNESS[:-1] + bytes([HOST_RANDOMNESS[-1] ^ 1]),
    )
    with pytest.raises(AntiExfilProtocolError) as raised:
        controller.process(reveal.encode(), psbt_bytes)
    assert raised.value.code == AntiExfilProtocolCode.COMMITMENT_MISMATCH


def test_changed_opening_is_rejected(fixture_context):
    _, psbt_bytes, _, controller, message_one = fixture_context
    reveal = AntiExfilMessage(
        stage=Stage.HOST_REVEAL,
        session_id=message_one.session_id,
        message_hash=message_one.message_hash,
        signer_pubkey=message_one.signer_pubkey,
        commitment=message_one.commitment,
        opening=message_one.signer_pubkey,
        host_randomness=HOST_RANDOMNESS,
    )
    with pytest.raises(AntiExfilProtocolError) as raised:
        controller.process(reveal.encode(), psbt_bytes)
    assert raised.value.code == AntiExfilProtocolCode.OPENING_MISMATCH


def test_regular_signing_crossover_is_rejected(fixture_context):
    psbt, _, context, controller, message_one = fixture_context
    signer = ec.PublicKey.parse(context.signer_pubkey)
    psbt.inputs[0].partial_sigs[signer] = b"already-signed"
    with pytest.raises(AntiExfilProtocolError) as raised:
        controller.process(message_one.encode(), psbt.serialize())
    assert raised.value.code == AntiExfilProtocolCode.SIGNING_MODE_MISMATCH
    assert "already signed" in raised.value.message


def test_invalid_mnemonic_returns_structured_error(tmp_path, capsys, fixture_context):
    _, psbt_bytes, _, _, message_one = fixture_context
    psbt_path = tmp_path / "request.psbt"
    message_path = tmp_path / "message-1.aex"
    mnemonic_path = tmp_path / "mnemonic.txt"
    psbt_path.write_bytes(psbt_bytes)
    message_path.write_bytes(message_one.encode())
    mnemonic_path.write_text("not a valid bip39 mnemonic", encoding="utf-8")
    assert main(
        [
            "--psbt",
            str(psbt_path),
            "--message",
            str(message_path),
            "--mnemonic-file",
            str(mnemonic_path),
            "--output",
            str(tmp_path / "must-not-exist.aex"),
        ]
    ) == 1
    error = capsys.readouterr().err
    assert '"status": "error"' in error
    assert AntiExfilProtocolCode.INVALID_MESSAGE.value in error
    assert '"production_fallback": false' in error


@pytest.mark.skipif(
    not NATIVE_LIBRARY or not Path(NATIVE_LIBRARY).is_file(),
    reason="set SEEDSIGNER_ANTI_EXFIL_LIBRARY to the pinned native library",
)
def test_real_native_backend_and_terminal_entrypoint(tmp_path, fixture_context):
    _, psbt_bytes, context, _, message_one = fixture_context
    seed = Seed(MNEMONIC.split())
    with AntiExfilNativeBackend(Path(NATIVE_LIBRARY)) as backend:
        controller = AntiExfilSignerController(
            seed, SettingsConstants.REGTEST, backend
        )
        opening_response = controller.process(message_one.encode(), psbt_bytes).response
        reveal = AntiExfilMessage(
            stage=Stage.HOST_REVEAL,
            session_id=message_one.session_id,
            message_hash=context.message_hash,
            signer_pubkey=context.signer_pubkey,
            commitment=message_one.commitment,
            opening=opening_response.opening,
            host_randomness=HOST_RANDOMNESS,
        )
        signature_response = controller.process(reveal.encode(), psbt_bytes).response
        assert signature_response.stage == Stage.SIGNER_SIGNATURES

    psbt_path = tmp_path / "request.psbt"
    message_path = tmp_path / "message-1.aex"
    mnemonic_path = tmp_path / "mnemonic.txt"
    output_path = tmp_path / "message-2.aex"
    psbt_path.write_bytes(psbt_bytes)
    message_path.write_bytes(message_one.encode())
    mnemonic_path.write_text(MNEMONIC, encoding="utf-8")
    assert main(
        [
            "--psbt",
            str(psbt_path),
            "--message",
            str(message_path),
            "--mnemonic-file",
            str(mnemonic_path),
            "--network",
            SettingsConstants.REGTEST,
            "--output",
            str(output_path),
            "--library",
            NATIVE_LIBRARY,
        ]
    ) == 0
    assert decode_message(output_path.read_bytes()).stage == Stage.SIGNER_OPENINGS
    assert main(
        [
            "--psbt",
            str(psbt_path),
            "--message",
            str(message_path),
            "--mnemonic-file",
            str(mnemonic_path),
            "--network",
            SettingsConstants.REGTEST,
            "--output",
            str(output_path),
            "--library",
            NATIVE_LIBRARY,
        ]
    ) == 1
