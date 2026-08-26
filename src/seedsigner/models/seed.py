import logging
import unicodedata
import hashlib
import hmac

from binascii import hexlify
from embit import bip39, bip32, bip85
from embit.networks import NETWORKS
from typing import List

from seedsigner.models.settings import SettingsConstants

logger = logging.getLogger(__name__)


class InvalidSeedException(Exception):
    pass



class Seed:
    def __init__(self,
                 mnemonic: List[str] = None,
                 passphrase: str = "",
                 wordlist_language_code: str = SettingsConstants.WORDLIST_LANGUAGE__ENGLISH) -> None:
        self._wordlist_language_code = wordlist_language_code

        if not mnemonic:
            raise Exception("Must initialize a Seed with a mnemonic List[str]")
        self._mnemonic: List[str] = unicodedata.normalize("NFKD", " ".join(mnemonic).strip()).split()

        self._passphrase: str = ""
        self.set_passphrase(passphrase, regenerate_seed=False)

        self.seed_bytes: bytes = None
        self._generate_seed()


    @staticmethod
    def get_wordlist(wordlist_language_code: str = SettingsConstants.WORDLIST_LANGUAGE__ENGLISH) -> List[str]:
        # TODO: Support other BIP-39 wordlist languages!
        if wordlist_language_code == SettingsConstants.WORDLIST_LANGUAGE__ENGLISH:
            return bip39.WORDLIST
        else:
            raise Exception(f"Unrecognized wordlist_language_code {wordlist_language_code}")


    def _generate_seed(self):
        try:
            self.seed_bytes = bip39.mnemonic_to_seed(self.mnemonic_str, password=self._passphrase, wordlist=self.wordlist)
        except Exception as e:
            logger.info(repr(e), exc_info=True)
            raise InvalidSeedException(repr(e))


    @property
    def mnemonic_str(self) -> str:
        return " ".join(self._mnemonic)
    

    @property
    def mnemonic_list(self) -> List[str]:
        return self._mnemonic


    @property 
    def wordlist_language_code(self) -> str:
        return self._wordlist_language_code


    @property
    def mnemonic_display_str(self) -> str:
        return unicodedata.normalize("NFC", " ".join(self._mnemonic))
    

    @property
    def mnemonic_display_list(self) -> List[str]:
        return unicodedata.normalize("NFC", " ".join(self._mnemonic)).split()


    @property
    def has_passphrase(self):
        return self._passphrase != ""


    @property
    def passphrase(self):
        return self._passphrase
        

    @property
    def passphrase_display(self):
        return unicodedata.normalize("NFC", self._passphrase)


    @property
    def passphrase_supported(self) -> bool:
        return True


    def set_passphrase(self, passphrase: str, regenerate_seed: bool = True):
        if passphrase:
            self._passphrase = unicodedata.normalize("NFKD", passphrase)
        else:
            # Passphrase must always have a string value, even if it's just the empty
            # string.
            self._passphrase = ""

        if regenerate_seed:
            # Regenerate the internal seed since passphrase changes the result
            self._generate_seed()


    @property
    def wordlist(self) -> List[str]:
        return Seed.get_wordlist(self.wordlist_language_code)


    def set_wordlist_language_code(self, language_code: str):
        # TODO: Support other BIP-39 wordlist languages!
        raise Exception("Not yet implemented!")


    @property
    def script_override(self) -> str:
        return None


    def derivation_override(self, sig_type: str = SettingsConstants.SINGLE_SIG) -> str:
        return None


    def detect_version(self, derivation_path: str, network: str = SettingsConstants.MAINNET, sig_type: str = SettingsConstants.SINGLE_SIG) -> str:
        embit_network = NETWORKS[SettingsConstants.map_network_to_embit(network)]
        return bip32.detect_version(derivation_path, default="xpub", network=embit_network)


    @property
    def passphrase_label(self) -> str:
        return SettingsConstants.LABEL__BIP39_PASSPHRASE


    @property
    def seedqr_supported(self) -> bool:
        return True


    @property
    def bip85_supported(self) -> bool:
        return True


    def get_fingerprint(self, network: str = SettingsConstants.MAINNET) -> str:
        root = bip32.HDKey.from_seed(self.seed_bytes, version=NETWORKS[SettingsConstants.map_network_to_embit(network)]["xprv"])
        return hexlify(root.child(0).fingerprint).decode('utf-8')


    def get_xpub(self, wallet_path: str = '/', network: str = SettingsConstants.MAINNET):
        # Import here to avoid slow startup times; takes 1.35s to import the first time
        from seedsigner.helpers import embit_utils
        return embit_utils.get_xpub(seed_bytes=self.seed_bytes, derivation_path=wallet_path, embit_network=SettingsConstants.map_network_to_embit(network))


    def get_bip85_child_mnemonic(self, bip85_index: int, bip85_num_words: int, network: str = SettingsConstants.MAINNET):
        """Derives the seed's nth BIP-85 child mnemonic"""
        root = bip32.HDKey.from_seed(self.seed_bytes, version=NETWORKS[SettingsConstants.map_network_to_embit(network)]["xprv"])

        # TODO: Support other BIP-39 wordlist languages!
        return bip85.derive_mnemonic(root, bip85_num_words, bip85_index)


    def wipe(self) -> None:
        """
        Best-effort release of sensitive in-memory fields.

        Python's immutable strings/bytes cannot be scrubbed safely in place. Clear
        mutable containers and drop our references without implying secure erasure.
        """
        self.seed_bytes = None

        if self._mnemonic is not None:
            for i in range(len(self._mnemonic)):
                self._mnemonic[i] = ""
            self._mnemonic = []

        if self._passphrase:
            self._passphrase = "\x00" * len(self._passphrase)
        self._passphrase = ""
        

    ### override operators    
    def __eq__(self, other):
        if isinstance(other, Seed):
            return self.seed_bytes == other.seed_bytes
        return False



class Codex32Seed(Seed):
    def __init__(
        self,
        seed_bytes: bytes,
        codex32_master_share: str | None = None,
        codex32_export_shares: dict[str, str] | None = None,
        codex32_share_sources: dict[str, str] | None = None,
    ) -> None:
        if len(seed_bytes) != 16:
            raise InvalidSeedException(
                f"Expected 16 bytes for a Codex32 master seed, got {len(seed_bytes)}"
            )

        from seedsigner.models import codex32 as codex32_model

        try:
            codex32_model.validate_codex32_seed_metadata(
                seed_bytes,
                master_share=codex32_master_share,
                export_shares=codex32_export_shares,
            )
        except codex32_model.Codex32InputError as exc:
            raise InvalidSeedException(str(exc)) from exc

        # Take ownership of a distinct immutable buffer so later cleanup of a
        # caller-owned Codex32String cannot alias this seed's entropy.
        # _generate_seed(). Must be set first since _generate_seed() reads it.
        self._codex32_entropy = bytes(bytearray(seed_bytes))

        # Derive BIP39 mnemonic from raw entropy, then delegate to parent.
        mnemonic = unicodedata.normalize("NFKD", bip39.mnemonic_from_bytes(seed_bytes)).split()
        super().__init__(mnemonic=mnemonic, passphrase="")

        self._codex32_master_share = codex32_master_share
        self._codex32_export_shares = dict(codex32_export_shares) if codex32_export_shares else None
        self._codex32_share_sources = dict(codex32_share_sources) if codex32_share_sources else None


    def _generate_seed(self):
        # Codex32 stores the raw 16-byte entropy as seed_bytes, not the
        # 64-byte PBKDF2 output that BIP39 normally produces. This matches
        # the codex32 spec where the secret IS the master seed entropy.
        self.seed_bytes = self._codex32_entropy


    def set_passphrase(self, passphrase: str, regenerate_seed: bool = True):
        if passphrase:
            raise InvalidSeedException("Codex32 seeds do not support passphrases")
        self._passphrase = ""


    @property
    def passphrase_supported(self) -> bool:
        return False


    @property
    def codex32_master_share(self) -> str | None:
        return self._codex32_master_share


    @property
    def codex32_export_shares(self) -> dict[str, str] | None:
        if self._codex32_export_shares is None:
            return None
        return dict(self._codex32_export_shares)


    @property
    def codex32_share_sources(self) -> dict[str, str] | None:
        if self._codex32_share_sources is None:
            return None
        return dict(self._codex32_share_sources)


    def wipe(self) -> None:
        super().wipe()

        self._codex32_entropy = None

        if self._codex32_master_share:
            self._codex32_master_share = "\x00" * len(self._codex32_master_share)
        self._codex32_master_share = None

        if self._codex32_export_shares:
            for share_idx, share in list(self._codex32_export_shares.items()):
                if isinstance(share, str):
                    self._codex32_export_shares[share_idx] = "\x00" * len(share)
            self._codex32_export_shares.clear()
        self._codex32_export_shares = None

        if self._codex32_share_sources:
            for share_idx, source in list(self._codex32_share_sources.items()):
                if isinstance(source, str):
                    self._codex32_share_sources[share_idx] = "\x00" * len(source)
            self._codex32_share_sources.clear()
        self._codex32_share_sources = None



class ElectrumSeed(Seed):

    def _generate_seed(self):
        if len(self._mnemonic) != 12:
            raise InvalidSeedException(f"Unsupported Electrum seed length: {len(self._mnemonic)}")

        s = hmac.digest(b"Seed version", self.mnemonic_str.encode('utf8'), hashlib.sha512).hex()
        prefix = s[0:3]

        # only support Electrum Segwit version for now
        if SettingsConstants.ELECTRUM_SEED_SEGWIT == prefix:
            self.seed_bytes=hashlib.pbkdf2_hmac('sha512', self.mnemonic_str.encode('utf-8'), b'electrum' + self._passphrase.encode('utf-8'), iterations = SettingsConstants.ELECTRUM_PBKDF2_ROUNDS)

        else:
            raise InvalidSeedException(f"Unsupported Electrum seed format: {prefix}")


    def set_passphrase(self, passphrase: str, regenerate_seed: bool = True):
        if passphrase:
            self._passphrase = ElectrumSeed.normalize_electrum_passphrase(passphrase)
        else:
            # Passphrase must always have a string value, even if it's just the empty
            # string.
            self._passphrase = ""

        if regenerate_seed:
            # Regenerate the internal seed since passphrase changes the result
            self._generate_seed()


    @staticmethod
    def normalize_electrum_passphrase(passphrase : str) -> str:
        passphrase = unicodedata.normalize('NFKD', passphrase)
        # lower
        passphrase = passphrase.lower()
        # normalize whitespaces
        passphrase = u' '.join(passphrase.split())
        return passphrase


    @property
    def script_override(self) -> str:
        return SettingsConstants.NATIVE_SEGWIT


    def derivation_override(self, sig_type: str = SettingsConstants.SINGLE_SIG) -> str:
        return "m/0h" if sig_type == SettingsConstants.SINGLE_SIG else "m/1h"


    def detect_version(self, derivation_path: str, network: str = SettingsConstants.MAINNET, sig_type: str = SettingsConstants.SINGLE_SIG) -> str:
        embit_network = NETWORKS[SettingsConstants.map_network_to_embit(network)]
        return embit_network["zpub"] if sig_type == SettingsConstants.SINGLE_SIG else embit_network["Zpub"]


    @property
    def passphrase_label(self) -> str:
        return SettingsConstants.LABEL__CUSTOM_EXTENSION


    @property
    def seedqr_supported(self) -> bool:
        return False


    @property
    def bip85_supported(self) -> bool:
        return False
