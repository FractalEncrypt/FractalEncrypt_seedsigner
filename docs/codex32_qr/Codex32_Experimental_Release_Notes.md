# Codex32 experimental image: UX6 validation notes

**EXPERIMENTAL INDEPENDENT FORK. Test with public seeds and testnet/regtest only.
Do not enter real backups or mainnet seeds, or use this image to secure funds.
Mainnet is not disabled. This is not an official SeedSigner release.**

These notes identify the maintainer's tested UX6 image. No downloadable GitHub
release is published. For building and testing, use the
[build and test guide](Codex32_Experimental_Build_and_Test.md). Packaging steps
belong in the [maintainer publication checklist](Codex32_Experimental_Release_Checklist.md).

## Feature behavior

Manual 48-character codex32 entry can propose up to four substitutions, eight
scattered erasures (`?`), or mixtures within `2S+E <= 8`. A separately warned path
supports one consecutive erasure run of 9-13. Review numbered changes and
entered-to-proposed pairs, then re-enter readable characters from the backup.
Unreadable reconstructions retain an unverified repair warning.

The recovered seed's lowercase fingerprint is available once enough compatible
split codex32 shares are entered. Optional entry of a previously recorded
fingerprint and visual comparison help catch accidental mistakes. Load Seed is
available after a match, with recovery tools under More Options. A 32-bit match
is an accidental-error check, not authentication; verify the wallet policy and
a known address. Thirteen consecutive unknowns use all checksum redundancy:
another typo outside the run can yield a wrong checksum-valid completion.

## Tested image identity

| Item | Value |
| --- | --- |
| Image | `seedsigner_os.codex32-ec-ux6-test.pi0.img` |
| Bytes | `52428800` |
| SHA256 | `48870161174ec734b3e37bdd2353b611377ef5254594c9ba38e0066a82d3ed3c` |
| Application | `528031b63e4f8805e7f73fb3bb5355f630f53e86` |
| Version | `v0.8.7-Codex32-EC-UX6-test` |
| OS | `d13859392660fe512a753bc14ecd0edc86c35510` |
| Buildroot | `bf2a2858aa675a14b60f1f9142c65b32652609c1` |
| Target | Pi Zero 1.3, `--pi0` |
| Physical display | SeedSigner Plus set to 240x240 |

All four focused physical checks passed per operator on 2026-10-10. The device's
signed synthetic nested-SegWit PSBT was independently decoded from video; its
ECDSA signature verifies, with unsigned transaction and non-signature metadata
unchanged. No transaction was broadcast. The build exited zero and its image
size/hash were independently checked. Local tests passed 614 normal and 181
focused optimized cases; GitHub CI passed on Python 3.10 and 3.12.

The reviewed UX7 navigation change returns **Keep Saved Share** to the existing
scan-or-enter choice. It is committed at `87a4be4de12e24ce1c7f9e0bfcd6b78a535d3537`,
with 616 normal and 183 focused optimized tests passing. It is absent from the
UX6 image above; a fresh UX7 image and one focused device check remain pending.
Branch HEAD must not be substituted for an image's source pin. Historical UX5
hashes and packages are not assets for UX6 or UX7.

## Limits

A pre-existing CompactSeedQR scanner problem rejects some binary payloads after
text conversion in the Windows scanner library; Pi incidence is unknown. It is
unfixed. Use the supplied plain-text codex32 share QRs for these tests.

Other board images, independent byte-identical rebuilds, stable-release readiness
and real-funds use are not established. Correction does not search for inserted
or deleted characters or misplaced box groups, and cannot determine the true
number of mistakes. Separate Raspberry Pi OS / Python 3.13.5 warm correction
benchmarks measured about 10-21 ms; they do not establish firmware GUI timing.

Checksums identify bytes but are not an independent authentication channel without
a separately verifiable signature. No reproducible firmware build is claimed.
