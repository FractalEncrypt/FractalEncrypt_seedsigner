import hashlib
import os
from dataclasses import replace
from pathlib import Path
import pytest
from embit import bip32, bip39, ec, script
from embit.networks import NETWORKS
from embit.psbt import DerivationPath, PSBT
from embit.transaction import SIGHASH, Transaction, TransactionInput, TransactionOutput
from seedsigner.helpers.anti_exfil_protocol import AntiExfilProtocolCode, AntiExfilProtocolError
from seedsigner.helpers.anti_exfil_protocol_v1 import Network, ProtocolMessage, SigningSlot, Stage, decode_message
from seedsigner.helpers.anti_exfil_signer_v1 import AntiExfilSignerController, derive_signing_contexts
from seedsigner.helpers.anti_exfil_transport import AntiExfilTransportPackage, TransportNetwork
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants

MNEMONIC = "model ensure search plunge galaxy firm exclude brain satoshi meadow cable roast"
SESSION_ID = bytes.fromhex("c3" * 32)
HOST_RANDOMNESS = bytes.fromhex("a5" * 32)
GENERATOR = bytes.fromhex("0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798")
VALID_SIGNATURE = (1).to_bytes(32, "big") + (1).to_bytes(32, "big")
NATIVE_LIBRARY = os.environ.get("SEEDSIGNER_ANTI_EXFIL_LIBRARY")

def tagged_host_commitment(rho):
    tag = hashlib.sha256(b"s2c/ecdsa/data").digest()
    return hashlib.sha256(tag + tag + rho).digest()

def build_fixture():
    root = bip32.HDKey.from_seed(bip39.mnemonic_to_seed(MNEMONIC), version=NETWORKS["regtest"]["xprv"])
    paths = [bip32.parse_path(f"m/84h/1h/0h/0/{i}") for i in range(5)]
    own = [root.derive(path).key.get_public_key() for path in paths]
    external = [ec.PrivateKey(bytes([n]) * 32).get_public_key() for n in (0x31, 0x32, 0x33)]
    native_multi = script.multisig(2, [own[2], external[0], own[3]])
    nested_multi = script.multisig(2, [external[1], own[4], external[2]])
    redeem_key, redeem_multi = script.p2wpkh(own[1]), script.p2wsh(nested_multi)
    prevouts = (script.p2wpkh(own[0]), script.p2sh(redeem_key), script.p2wsh(native_multi), script.p2sh(redeem_multi))
    tx = Transaction(2, [TransactionInput(bytes([0x41 + i]) * 32, i, 0xfffffffd) for i in range(4)], [TransactionOutput(390000, script.p2wpkh(external[0]))], 0)
    psbt = PSBT(tx)
    for i, prevout in enumerate(prevouts):
        psbt.inputs[i].witness_utxo = TransactionOutput(100000 + i * 1000, prevout)
        psbt.inputs[i].sighash_type = SIGHASH.ALL
    psbt.inputs[1].redeem_script = redeem_key
    psbt.inputs[2].witness_script = native_multi
    psbt.inputs[3].redeem_script, psbt.inputs[3].witness_script = redeem_multi, nested_multi
    for input_index, key_index in ((0,0),(1,1),(2,2),(2,3),(3,4)):
        psbt.inputs[input_index].bip32_derivations[own[key_index]] = DerivationPath(root.my_fingerprint, paths[key_index])
    return psbt

class FakeNativeBackend:
    def host_commit(self, rho): return tagged_host_commitment(rho)
    def signer_commit(self, secret_key, message_hash, commitment): return GENERATOR
    def sign(self, secret_key, message_hash, rho): return VALID_SIGNATURE

def make_commit(psbt_bytes, contexts):
    slots = tuple(SigningSlot(c.input_index, c.signer_pubkey, c.message_hash, 1,
        tagged_host_commitment(bytes([0xa0 + i]) * 32)) for i, c in enumerate(contexts))
    return ProtocolMessage(Network.REGTEST, Stage.HOST_COMMIT, SESSION_ID, hashlib.sha256(psbt_bytes).digest(), slots)

@pytest.fixture
def fixture_context():
    psbt = build_fixture(); raw = psbt.serialize(); seed = Seed(MNEMONIC.split())
    _, contexts = derive_signing_contexts(raw, seed, SettingsConstants.REGTEST)
    return psbt, raw, contexts, AntiExfilSignerController(seed, SettingsConstants.REGTEST, FakeNativeBackend()), make_commit(raw, contexts)

def test_multislot_fixture_and_codec_are_canonical(fixture_context):
    _, raw, contexts, _, message = fixture_context
    assert hashlib.sha256(raw).hexdigest() == "fa4ef7e7bee778ec04017cd89c12da335d8e17fb3da749e3bfae070b0655d249"
    assert [c.input_index for c in contexts] == [0,1,2,2,3]
    assert [c.script_kind for c in contexts] == ["p2wpkh","p2sh-p2wpkh","p2wsh-multisig","p2wsh-multisig","p2sh-p2wsh-multisig"]
    assert decode_message(message.encode()) == message
    with pytest.raises(AntiExfilProtocolError): decode_message(message.encode() + b"x")

def test_frozen_reference_stage_one_vector_and_strict_slot_rules():
    psbt = b"psbt\xff" + b"protocol-v1-synthetic-wire-fixture"
    secrets = (bytes.fromhex("11"*32), bytes.fromhex("22"*32), bytes.fromhex("33"*32))
    rhos = (bytes.fromhex("a1"*32), bytes.fromhex("a2"*32), bytes.fromhex("a3"*32))
    hashes = (bytes.fromhex("81"*32), bytes.fromhex("82"*32), bytes.fromhex("83"*32))
    records = []
    for input_index, secret, rho, digest in ((0,secrets[0],rhos[0],hashes[0]),
                                              (1,secrets[1],rhos[1],hashes[1]),
                                              (1,secrets[2],rhos[2],hashes[2])):
        records.append(SigningSlot(input_index, ec.PrivateKey(secret).get_public_key().sec(),
                                   digest, 1, tagged_host_commitment(rho)))
    records.sort(key=lambda slot: slot.identifier)
    message = ProtocolMessage(Network.TESTNET4, Stage.HOST_COMMIT, SESSION_ID,
                              hashlib.sha256(psbt).digest(), tuple(records))
    assert hashlib.sha256(message.encode()).hexdigest() == "d29305233977f12b415dbcda4539fc92d20f30f533b2f532f130a2d59eadc89c"
    package = AntiExfilTransportPackage(message.encode(), TransportNetwork.TESTNET4, psbt)
    assert hashlib.sha256(package.encode()).hexdigest() == "3042be634afc5d84fb1414ce826fc69044d769652d090d8bf56e8d1c361a5ab3"
    with pytest.raises(AntiExfilProtocolError): replace(message, slots=tuple(reversed(message.slots))).encode()
    with pytest.raises(AntiExfilProtocolError): replace(message, slots=(message.slots[0], message.slots[0])).encode()
    with pytest.raises(AntiExfilProtocolError): replace(message, slots=(replace(message.slots[0], sighash_type=0x81),)).encode()
    with pytest.raises(AntiExfilProtocolError): replace(message, slots=(replace(message.slots[0], commitment=message.slots[1].commitment), message.slots[1])).encode()

def test_testnet4_is_distinct_and_uses_testnet_key_material():
    psbt = build_fixture(); raw = psbt.serialize(); seed = Seed(MNEMONIC.split())
    _, contexts = derive_signing_contexts(raw, seed, SettingsConstants.TESTNET4)
    message = ProtocolMessage(Network.TESTNET4, Stage.HOST_COMMIT, SESSION_ID,
        hashlib.sha256(raw).digest(), make_commit(raw, contexts).slots)
    response = AntiExfilSignerController(seed, SettingsConstants.TESTNET4, FakeNativeBackend()).process(message.encode(), raw).response
    assert response.network == Network.TESTNET4
    with pytest.raises(AntiExfilProtocolError):
        AntiExfilSignerController(seed, SettingsConstants.TESTNET, FakeNativeBackend()).process(message.encode(), raw)

def test_controller_completes_all_slots_deterministically(fixture_context):
    _, raw, _, controller, commit = fixture_context
    openings = controller.process(commit.encode(), raw).response
    assert openings.stage == Stage.SIGNER_OPENINGS and len(openings.slots) == 5
    reveal_slots = tuple(SigningSlot(s.input_index, s.signer_pubkey, s.message_hash, 1, s.commitment,
        opening=o.opening, rho=bytes([0xa0 + i]) * 32) for i, (s,o) in enumerate(zip(commit.slots, openings.slots)))
    reveal = ProtocolMessage(Network.REGTEST, Stage.HOST_REVEAL, SESSION_ID, commit.psbt_digest, reveal_slots)
    signatures = controller.process(reveal.encode(), raw).response
    assert signatures.stage == Stage.SIGNER_SIGNATURES
    assert all(slot.signature == VALID_SIGNATURE and slot.rho is None for slot in signatures.slots)

def test_slot_psbt_network_and_reveal_mutations_fail(fixture_context):
    psbt, raw, _, controller, commit = fixture_context
    bad_network = ProtocolMessage(Network.TESTNET4, commit.stage, commit.session_id, commit.psbt_digest, commit.slots)
    with pytest.raises(AntiExfilProtocolError): controller.process(bad_network.encode(), raw)
    changed = bytearray(raw); changed[-1] ^= 1
    with pytest.raises(AntiExfilProtocolError): controller.process(commit.encode(), bytes(changed))
    with pytest.raises(AntiExfilProtocolError):
        controller.process(ProtocolMessage(commit.network, commit.stage, commit.session_id, commit.psbt_digest, commit.slots[:-1]).encode(), raw)
    psbt.inputs[0].sighash_type = SIGHASH.NONE
    mutated = psbt.serialize()
    bad_digest = ProtocolMessage(commit.network, commit.stage, commit.session_id, hashlib.sha256(mutated).digest(), commit.slots)
    with pytest.raises(AntiExfilProtocolError): controller.process(bad_digest.encode(), mutated)
    missing_utxo = PSBT.parse(raw); missing_utxo.inputs[0].witness_utxo = None
    missing_raw = missing_utxo.serialize()
    missing_message = ProtocolMessage(commit.network, commit.stage, commit.session_id,
        hashlib.sha256(missing_raw).digest(), commit.slots)
    with pytest.raises(AntiExfilProtocolError): controller.process(missing_message.encode(), missing_raw)

def test_taproot_and_mixed_legacy_fail_whole_request(fixture_context):
    psbt, _, _, _, _ = fixture_context
    for replacement in (script.p2tr(ec.PrivateKey(bytes.fromhex("11"*32)).get_public_key()), script.p2pkh(ec.PrivateKey(bytes.fromhex("11"*32)).get_public_key())):
        changed = PSBT.parse(psbt.serialize()); changed.inputs[3].witness_utxo = TransactionOutput(103000, replacement)
        raw = changed.serialize(); seed = Seed(MNEMONIC.split())
        with pytest.raises(AntiExfilProtocolError): derive_signing_contexts(raw, seed, SettingsConstants.REGTEST)

def test_preexisting_controlled_signature_fails(fixture_context):
    psbt, _, _, _, _ = fixture_context
    pub = next(iter(psbt.inputs[0].bip32_derivations)); psbt.inputs[0].partial_sigs[pub] = b"existing"
    with pytest.raises(AntiExfilProtocolError) as raised:
        derive_signing_contexts(psbt.serialize(), Seed(MNEMONIC.split()), SettingsConstants.REGTEST)
    assert raised.value.code == AntiExfilProtocolCode.SIGNING_MODE_MISMATCH

@pytest.mark.skipif(not NATIVE_LIBRARY or not Path(NATIVE_LIBRARY).is_file(), reason="native library unavailable")
def test_real_native_backend(fixture_context):
    from seedsigner.helpers.anti_exfil import AntiExfilNativeBackend
    _, raw, _, _, commit = fixture_context
    with AntiExfilNativeBackend(Path(NATIVE_LIBRARY)) as backend:
        response = AntiExfilSignerController(Seed(MNEMONIC.split()), SettingsConstants.REGTEST, backend).process(commit.encode(), raw).response
    assert len(response.slots) == 5
