from typing import List
from seedsigner.models import codex32 as codex32_model
from seedsigner.models.seed import Seed, Codex32Seed, ElectrumSeed, InvalidSeedException
from seedsigner.models.settings_definition import SettingsConstants



class SeedStorage:
    def __init__(self) -> None:
        self.seeds: List[Seed] = []
        self.pending_seed: Seed = None
        self._pending_mnemonic: List[str] = []
        self._pending_is_electrum : bool = False


    def set_pending_seed(self, seed: Seed):
        self.pending_seed = seed


    def get_pending_seed(self) -> Seed:
        return self.pending_seed


    @staticmethod
    def _codex32_metadata_richness(seed: Codex32Seed) -> tuple[int, int, int, int, int, int]:
        """Rank usable Codex32 backup metadata without trusting field presence."""
        share_map = seed.codex32_export_shares or {}
        source_map = seed.codex32_share_sources or {}
        try:
            codex32_model.validate_codex32_seed_metadata(
                seed.seed_bytes,
                master_share=seed.codex32_master_share,
                export_shares=share_map,
            )
        except codex32_model.Codex32InputError:
            return (-1, -1, -1, -1, -1, -1)

        canonical_s_value = seed.codex32_master_share or share_map.get("s")
        if canonical_s_value is None:
            return (0, 0, 0, 0, 0, 0)

        canonical_s = codex32_model.validate_codex32_s_share(canonical_s_value)
        split_count = len([idx for idx in share_map if str(idx).lower() != "s"])
        verified_split_count = 0
        if canonical_s.k != "0" and split_count >= int(canonical_s.k):
            # validate_codex32_seed_metadata() above proved every threshold subset.
            verified_split_count = split_count

        recognized_sources = len([
            source for source in source_map.values() if source in ["entered", "derived"]
        ])
        return (
            1,
            int(seed.codex32_master_share is not None),
            verified_split_count,
            int("s" in {str(idx).lower() for idx in share_map}),
            recognized_sources,
            # A warning is safety-relevant metadata: on otherwise equal duplicates,
            # preserve the seed that still requires the user-facing warning.
            int(seed.codex32_backup_warning),
        )


    def finalize_pending_seed(self) -> Seed:
        # Store the pending seed and return the stored Seed object.
        seed = self.pending_seed
        if seed in self.seeds:
            index = self.seeds.index(seed)
            existing_seed = self.seeds[index]

            # Preserve the duplicate with richer *validated* Codex32 backup metadata.
            if (
                isinstance(existing_seed, Codex32Seed)
                and isinstance(seed, Codex32Seed)
                and self._codex32_metadata_richness(seed)
                > self._codex32_metadata_richness(existing_seed)
            ):
                self.seeds[index] = seed
                if existing_seed is not seed:
                    existing_seed.wipe()
            else:
                if seed is not existing_seed:
                    seed.wipe()
                seed = existing_seed
        else:
            self.seeds.append(seed)
        self.pending_seed = None
        return seed


    def clear_pending_seed(self):
        if self.pending_seed is not None:
            self.pending_seed.wipe()
        self.pending_seed = None


    def validate_mnemonic(self, mnemonic: List[str]) -> bool:
        try:
            Seed(mnemonic=mnemonic)
        except InvalidSeedException as e:
            return False
        
        return True


    def num_seeds(self):
        return len(self.seeds)
    

    @property
    def pending_mnemonic(self) -> List[str]:
        # Always return a copy so that the internal List can't be altered
        return list(self._pending_mnemonic)


    @property
    def pending_mnemonic_length(self) -> int:
        return len(self._pending_mnemonic)


    def init_pending_mnemonic(self, num_words:int = 12, is_electrum:bool = False):
        self._pending_mnemonic = [None] * num_words
        self._pending_is_electrum = is_electrum


    def update_pending_mnemonic(self, word: str, index: int):
        """
        Replaces the nth word in the pending mnemonic.

        * may specify a negative `index` (e.g. -1 is the last word).
        """
        if index >= len(self._pending_mnemonic):
            raise Exception(f"index {index} is too high")
        self._pending_mnemonic[index] = word
    

    def get_pending_mnemonic_word(self, index: int) -> str:
        if index < len(self._pending_mnemonic):
            return self._pending_mnemonic[index]
        return None
    

    def get_pending_mnemonic_fingerprint(self, network: str = SettingsConstants.MAINNET) -> str:
        try:
            if self._pending_is_electrum:
                seed = ElectrumSeed(self._pending_mnemonic)
            else:
                seed = Seed(self._pending_mnemonic)
            return seed.get_fingerprint(network)
        except InvalidSeedException:
            return None


    def convert_pending_mnemonic_to_pending_seed(self):
        if self._pending_is_electrum:
            self.pending_seed = ElectrumSeed(self._pending_mnemonic)
        else:
            self.pending_seed = Seed(self._pending_mnemonic)
        self.discard_pending_mnemonic()
    

    def discard_pending_mnemonic(self):
        self._pending_mnemonic = []
        self._pending_is_electrum = False
