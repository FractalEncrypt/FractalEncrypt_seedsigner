"""SeedSigner semantic PSBT-v0 validation and multi-slot signing controller."""

from __future__ import annotations
from dataclasses import dataclass
import hashlib
import hmac
from embit import bip32, ec, script
from embit.networks import NETWORKS
from embit.psbt import PSBT
from embit.transaction import SIGHASH
from seedsigner.helpers.anti_exfil import AntiExfilNativeError
from seedsigner.helpers.anti_exfil_protocol import AntiExfilProtocolCode, AntiExfilProtocolError
from seedsigner.helpers.anti_exfil_protocol_v1 import Network, ProtocolMessage, SigningSlot, Stage, decode_message
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants

@dataclass(frozen=True, slots=True)
class SigningContext:
    input_index: int
    signer_pubkey: bytes
    message_hash: bytes
    secret_key: bytes
    fingerprint: str
    derivation: str
    script_kind: str
    input_amount: int
    spend_amount: int
    fee_amount: int
    @property
    def identifier(self): return self.input_index, self.signer_pubkey

@dataclass(frozen=True, slots=True)
class ControllerResult:
    response: ProtocolMessage
    contexts: tuple[SigningContext, ...]
    @property
    def context(self):
        return self.contexts[0]

def protocol_network_for_setting(network: str) -> Network:
    mapping = {SettingsConstants.MAINNET: Network.MAINNET,
               SettingsConstants.TESTNET: Network.TESTNET3,
               SettingsConstants.SIGNET: Network.SIGNET,
               SettingsConstants.REGTEST: Network.REGTEST}
    mapping[SettingsConstants.TESTNET4] = Network.TESTNET4
    try: return mapping[network]
    except KeyError as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"unsupported network {network!r}") from exc

def protocol_network_matches_setting(setting: str, network: Network) -> bool:
    if setting == SettingsConstants.TESTNET:
        return network in (Network.TESTNET3, Network.TESTNET4, Network.SIGNET)
    return network == protocol_network_for_setting(setting)

def parse_psbt_v0(raw: bytes) -> PSBT:
    if not isinstance(raw, bytes) or not raw.startswith(b"psbt\xff"):
        _fail(AntiExfilProtocolCode.INVALID_MESSAGE, "invalid PSBT magic")
    try: psbt = PSBT.parse(raw)
    except Exception as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.INVALID_MESSAGE, f"invalid PSBT: {exc}") from exc
    if psbt.serialize() != raw: _fail(AntiExfilProtocolCode.INVALID_MESSAGE, "PSBT is not canonical")
    if psbt.version not in (None, 0): _fail(AntiExfilProtocolCode.INVALID_MESSAGE, "protocol v1 accepts PSBT v0 only")
    if psbt.tx is None or not psbt.inputs or not psbt.outputs: _fail(AntiExfilProtocolCode.INVALID_MESSAGE, "PSBT requires an unsigned transaction")
    return psbt

def derive_signing_contexts(psbt_bytes: bytes, seed: Seed, network: str):
    protocol_network_for_setting(network)
    psbt = parse_psbt_v0(psbt_bytes)
    root = bip32.HDKey.from_seed(
        seed.seed_bytes,
        version=NETWORKS[SettingsConstants.map_network_to_embit(network)]["xprv"],
    )
    input_amount = sum(_resolve_utxo(psbt, i).value for i in range(len(psbt.inputs)))
    spend_amount = sum(output.value for output in psbt.tx.vout)
    fee_amount = input_amount - spend_amount
    if fee_amount < 0:
        _fail(AntiExfilProtocolCode.INVALID_MESSAGE, "PSBT spends more than its inputs")
    contexts = []
    for index, scope in enumerate(psbt.inputs):
        utxo = _resolve_utxo(psbt, index)
        if _taproot(scope, utxo.script_pubkey):
            _slot_fail(index, "Taproot data is unsupported")
        kind, keys = _classify(index, scope, utxo.script_pubkey)
        sighash = SIGHASH.ALL if scope.sighash_type is None else scope.sighash_type
        if sighash != SIGHASH.ALL: _slot_fail(index, f"unsupported sighash {sighash}")
        _validate_derivations(index, scope, keys)
        digest = psbt.sighash(index, sighash=SIGHASH.ALL)
        for pub, origin in scope.bip32_derivations.items():
            encoded = pub.sec()
            if encoded not in keys or origin.fingerprint != root.my_fingerprint: continue
            derived = root.derive(origin.derivation)
            if derived.key.get_public_key().sec() != encoded: _slot_fail(index, "derivation does not reproduce public key")
            if pub in scope.partial_sigs: _fail(AntiExfilProtocolCode.SIGNING_MODE_MISMATCH, f"input {index} already has a controlled signature")
            if scope.final_scriptsig is not None or scope.final_scriptwitness is not None: continue
            contexts.append(SigningContext(index, encoded, digest, derived.key.secret,
                root.my_fingerprint.hex(), _format_derivation(origin.derivation), kind,
                input_amount, spend_amount, fee_amount))
    contexts.sort(key=lambda item: item.identifier)
    if not contexts: _slot_fail(0, "PSBT has no controlled signing slots")
    if len(contexts) > 128: _slot_fail(0, "PSBT exceeds global slot limit")
    counts = {}
    for context in contexts:
        counts[context.input_index] = counts.get(context.input_index, 0) + 1
        if counts[context.input_index] > 16: _slot_fail(context.input_index, "per-input slot limit exceeded")
    return psbt, tuple(contexts)

def derive_signing_context(psbt_bytes: bytes, seed: Seed, network: str):
    psbt, contexts = derive_signing_contexts(psbt_bytes, seed, network)
    if len(contexts) != 1: _slot_fail(0, f"expected one slot; found {len(contexts)}")
    return psbt, contexts[0]

class AntiExfilSignerController:
    def __init__(self, seed: Seed, network: str, backend):
        self.seed, self.network, self.backend = seed, network, backend
    def process(self, request_bytes: bytes, psbt_bytes: bytes) -> ControllerResult:
        request = decode_message(request_bytes)
        if request.stage not in (Stage.HOST_COMMIT, Stage.HOST_REVEAL): _fail(AntiExfilProtocolCode.WRONG_STAGE, "SeedSigner accepts only messages 1 and 3")
        if not protocol_network_matches_setting(self.network, request.network):
            _fail(AntiExfilProtocolCode.TRANSACTION_MISMATCH, "message network differs from active network family")
        if not hmac.compare_digest(request.psbt_digest, hashlib.sha256(psbt_bytes).digest()): _fail(AntiExfilProtocolCode.TRANSACTION_MISMATCH, "message PSBT digest differs from exact PSBT")
        _, contexts = derive_signing_contexts(psbt_bytes, self.seed, self.network)
        if tuple(context.identifier for context in contexts) != tuple(slot.identifier for slot in request.slots): _fail(AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH, "message slot set differs from SeedSigner enumeration")
        output = []
        try:
            for context, slot in zip(contexts, request.slots):
                if context.message_hash != slot.message_hash or slot.sighash_type != SIGHASH.ALL: _fail(AntiExfilProtocolCode.TRANSACTION_MISMATCH, "slot sighash context differs from PSBT")
                if request.stage == Stage.HOST_COMMIT:
                    opening = self.backend.signer_commit(context.secret_key, context.message_hash, slot.commitment)
                    output.append(SigningSlot(slot.input_index, slot.signer_pubkey, slot.message_hash, slot.sighash_type, slot.commitment, opening=opening))
                else:
                    if slot.rho is None or slot.opening is None: _fail(AntiExfilProtocolCode.INVALID_MESSAGE, "host reveal slot is incomplete")
                    if self.backend.host_commit(slot.rho) != slot.commitment: _fail(AntiExfilProtocolCode.COMMITMENT_MISMATCH, "host reveal does not match commitment")
                    opening = self.backend.signer_commit(context.secret_key, context.message_hash, slot.commitment)
                    if opening != slot.opening: _fail(AntiExfilProtocolCode.OPENING_MISMATCH, "accepted opening changed")
                    signature = self.backend.sign(context.secret_key, context.message_hash, slot.rho)
                    output.append(SigningSlot(slot.input_index, slot.signer_pubkey, slot.message_hash, slot.sighash_type, slot.commitment, opening=slot.opening, signature=signature))
        except AntiExfilNativeError as exc: raise AntiExfilProtocolError(AntiExfilProtocolCode.NATIVE_BACKEND, str(exc)) from exc
        stage = Stage.SIGNER_OPENINGS if request.stage == Stage.HOST_COMMIT else Stage.SIGNER_SIGNATURES
        response = ProtocolMessage(request.network, stage, request.session_id, request.psbt_digest, tuple(output))
        response.encode()
        return ControllerResult(response, contexts)

def _resolve_utxo(psbt, index):
    scope, witness, legacy = psbt.inputs[index], psbt.inputs[index].witness_utxo, psbt.inputs[index].non_witness_utxo
    if legacy is not None:
        txin = psbt.tx.vin[index]
        if legacy.txid() != txin.txid or txin.vout >= len(legacy.vout): _slot_fail(index, "non-witness UTXO does not match prevout")
        referenced = legacy.vout[txin.vout]
        if witness is not None and witness != referenced: _slot_fail(index, "witness and non-witness UTXO disagree")
        witness = referenced
    if witness is None: _slot_fail(index, "missing UTXO data")
    return witness

def _classify(index, scope, outer):
    typ = outer.script_type()
    if typ == "p2tr": _slot_fail(index, "Taproot input is unsupported")
    if typ == "p2wpkh" and scope.redeem_script is None and scope.witness_script is None: return "p2wpkh", (_p2wpkh_key(index, outer, scope),)
    if typ == "p2sh" and scope.redeem_script is not None and script.p2sh(scope.redeem_script) == outer:
        if scope.redeem_script.script_type() == "p2wpkh" and scope.witness_script is None: return "p2sh-p2wpkh", (_p2wpkh_key(index, scope.redeem_script, scope),)
        if scope.redeem_script.script_type() == "p2wsh" and scope.witness_script is not None:
            if script.p2wsh(scope.witness_script) != scope.redeem_script: _slot_fail(index, "nested witness script hash mismatch")
            return "p2sh-p2wsh-multisig", _parse_multisig(index, scope.witness_script)
    if typ == "p2wsh" and scope.redeem_script is None and scope.witness_script is not None:
        if script.p2wsh(scope.witness_script) != outer: _slot_fail(index, "witness script hash mismatch")
        return "p2wsh-multisig", _parse_multisig(index, scope.witness_script)
    _slot_fail(index, f"unsupported or inconsistent script type {typ}")

def _p2wpkh_key(index, program, scope):
    keys = [pub.sec() for pub in scope.bip32_derivations if script.p2wpkh(pub) == program]
    if len(keys) != 1: _slot_fail(index, "P2WPKH requires exactly one matching derivation")
    return keys[0]
def _parse_multisig(index, witness_script):
    raw = witness_script.data
    if len(raw) < 3 or raw[-1] != 0xae or not 0x51 <= raw[0] <= 0x60 or not 0x51 <= raw[-2] <= 0x60: _slot_fail(index, "witness script is not standard multisig")
    required, declared, cursor, keys = raw[0] - 0x50, raw[-2] - 0x50, 1, []
    while cursor < len(raw) - 2:
        if raw[cursor] != 33 or cursor + 34 > len(raw) - 2: _slot_fail(index, "multisig keys require canonical pushes")
        encoded = raw[cursor + 1:cursor + 34]
        try: ec.PublicKey.parse(encoded)
        except Exception: _slot_fail(index, "invalid multisig public key")
        keys.append(encoded); cursor += 34
    if cursor != len(raw) - 2 or declared != len(keys) or not 1 <= required <= declared <= 16 or len(set(keys)) != len(keys): _slot_fail(index, "invalid multisig threshold or keys")
    return tuple(keys)
def _validate_derivations(index, scope, keys):
    seen = set()
    for pub, origin in scope.bip32_derivations.items():
        encoded = pub.sec()
        if encoded in seen or encoded not in keys: _slot_fail(index, "derivation key is duplicate or absent from script")
        seen.add(encoded)
        if len(origin.fingerprint) != 4: _slot_fail(index, "invalid derivation fingerprint")
def _taproot(scope, script_pubkey):
    return bool(
        script_pubkey.script_type() == "p2tr"
        or scope.taproot_bip32_derivations
        or scope.taproot_internal_key
        or scope.taproot_merkle_root
        or scope.taproot_sigs
        or scope.taproot_scripts
    )
def _format_derivation(path): return "m/" + "/".join(f"{i & 0x7fffffff}{'h' if i & 0x80000000 else ''}" for i in path)
def _slot_fail(index, message): _fail(AntiExfilProtocolCode.SIGNATURE_SLOT_MISMATCH, f"input {index}: {message}")
def _fail(code, message): raise AntiExfilProtocolError(code, message)
