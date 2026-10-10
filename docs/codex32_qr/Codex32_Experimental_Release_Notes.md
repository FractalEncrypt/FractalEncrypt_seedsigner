# Codex32 EC Test 1 — experimental Pi Zero image

**EXPERIMENTAL INDEPENDENT FORK. For testing with public seeds and testnet/regtest
only. Do not enter real backups or mainnet seeds, and do not use this image to
secure funds. Mainnet is not disabled by this build. This is not an official
SeedSigner release. Report results with public test data only.**

**Draft superseded: not ready to publish.** These notes describe historical UX5.
Physical tests used a SeedSigner Plus at 240x320. Clipping found at 240x240 led to
reviewed layout and duplicate-share navigation changes. Runtime is now pinned at
`528031b63e4f8805e7f73fb3bb5355f630f53e86` (UX6). Build and physically check that
candidate, then replace the historical validation/asset sections below with its
actual results and hashes before publishing.

## What the feature adds

Manual 48-character Codex32 entry can propose up to four substitutions, eight
scattered erasures (`?`), or mixtures within `2S+E <= 8`. A separate warned path
supports a single consecutive erasure run of 9-13. Review the numbered changes
and entered-to-proposed pairs, then re-enter readable characters from the backup.
Unreadable reconstructions and annotated repairs keep an unverified warning.

Recovery displays a lowercase fingerprint as soon as enough compatible shares
are present. Optional entry of a previously recorded fingerprint and visual
comparison help catch transcription mistakes. After a match, Load Seed is
available immediately, with recovery tools under More Options. A 32-bit match
is an accidental-error check, not authentication; verify the wallet policy and
a known address. Thirteen consecutive unknowns use all checksum redundancy;
another typo outside that run can give a wrong but checksum-valid completion.

## Tested hardware and validation

- Historical device testing: Pi Zero 1.3, SeedSigner Plus at 240x320, pi0 target.
- Application `22ee79b2d9aff6ecf6b49572f42361c9363d598f`, including the separately
  reviewed upstream nested-SegWit change-verification merge.
- 586 normal tests, 86 optimized correction/flow/entry tests, 22 screenshot locales,
  and GitHub CI on Python 3.10 and 3.12 passed for this runtime revision.
- All seven focused device checks passed. The signed synthetic nested-SegWit PSBT
  was decoded from device video and its ECDSA signature verified; other PSBT data
  matched the unsigned fixture. No transaction was broadcast.
- A separate Raspberry Pi OS / Python 3.13.5 benchmark measured warm supported
  correction medians around 10-21 ms. It excludes firmware GUI work and is not an
  exact timing guarantee for the firmware.

## Known limitations

A pre-existing CompactSeedQR scanner problem rejects some binary payloads after
text-encoding conversion. It was reproduced using the Windows scanner library;
incidence on the Pi has not been established. It remains unfixed. Use the supplied
plain-text Codex32 share QRs for these tests; do not rely on CompactSeedQR recovery.

Only the pi0 target on the hardware above was device-tested. Other boards,
byte-identical independent rebuilds, stable-release readiness and real-funds use
are not established. Correction does not search for inserted/deleted characters
or misplaced box groups, and cannot determine the true number of mistakes.

## Historical asset preparation (superseded)

The following describes the earlier local package, not a published download.
Do not distribute it as the pending layout candidate.

1. The earlier package named `seedsigner_os.codex32-ec-test.1.pi0.img` and `SHA256SUMS`.
2. Verify its SHA256 before flashing. The image is 52,428,800 bytes; SHA256:
   `4c6104ee33aea1f2e68119fc2184077dcb45147c580af9ebd054f221724803f4`.
3. Flash to an SD card for the tested pi0 target using your usual image writer.
   About should identify `v0.8.7-Codex32-EC-UX5-test`, fork FractalEncrypt,
   and commit `22ee79b`.
4. Unzip `Codex32_EC_Test_1_Docs.zip`. Start with the experimental build/test guide
   for public BIP93 A/C and cash text/QR vectors and expected fingerprints, then
   follow the illustrated user-flow guide. The screen reference explains all
   Codex32-specific screens and related shared screens.
5. Follow the coordinator test-wallet instructions to export account xpubs to
   Sparrow, Nunchuk or compatible software, assemble single-sig/multisig policy,
   check a known address and test signing with public data only.

The public build receipt records immutable source inputs, version metadata,
builder image identity and staged-input hashes. It does not assert a reproducible
firmware build. The checksum file identifies these assets; without a separately
verifiable maintainer signature, it is not an independent authentication channel.
