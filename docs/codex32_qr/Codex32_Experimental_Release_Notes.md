# SeedSigner Codex32 Alpha 0.1

**Experimental independent fork. Use public practice seeds and testnet/regtest
only. Do not enter real backups or mainnet seeds, or use this image to secure
funds. Mainnet is not disabled. This is not an official SeedSigner release.**

This first alpha release combines codex32 and SeedSigner to establish a
**Trust-minimized Analog-to-Digital Bridge**:

1. **Analog Generation:** Generate a codex32 master secret and split shares
   entirely offline using the book's debiased dice method and paper worksheets.
   Calculate the checksums yourself. No electronics are needed for key generation.
2. **Stateless Digital Signing:** When you need to receive or spend Bitcoin,
   temporarily bring your analog seed into the digital realm by entering or
   scanning it into SeedSigner. Interact with an internet-connected watch-only
   wallet over the air gap. With this workflow, the seed stays entirely cold and offline.
   SeedSigner keeps your seed and entered shares only in temporary memory,
   never saving them to the SD card. Powering off clears the loaded seed and
   shares from SeedSigner. They are no longer available when you turn it back
   on, so you must enter or scan your backup again before using the seed.

This lets you create your Bitcoin seed with paper and math, without relying on
an electronic key generator, while retaining the convenience of an electronic
signer when you need to use the wallet. Protect the paper from theft, damage and
transcription mistakes, and verify wallet details on the signer.

Codex32's error correction lets the device propose mathematical repairs to
entry mistakes and partially unreadable or corrupted backups, within limits.
This alpha imports existing 48-character codex32 backups. It does not create new
share sets or append checksums; generation is the offline book-and-worksheet step.
For this alpha, practice only with disposable or published test seeds.

## Guides and public practice backups

Start with the [recovery and test guide](Codex32_Experimental_Test_Guide.md).
Its first test scans NAME's two split shares, compares the recovered S secret,
and loads the signer. It also explains paper-backup practice, error-correction
trials and optional public-key export to Sparrow, Nunchuk or compatible wallet
software. Wallet software is not required to test share recovery.

The [illustrated user flow](Codex32_User_Flow_Guide.md) walks through the screens;
the [screen reference](Codex32_Screen_Reference.md) explains their messages.
[Print a backup card](printable_templates/Seedsigner_Codex32_Printable_SeedCards.pdf)
and use the guide's numbered four-character groups to copy NAME A or cash A.
All supplied BIP93 test seeds are public: never send funds to their wallets.

Use existing disposable codex32 test shares or make a test secret with the
[Codex32 book's debiased dice and worksheets](https://secretcodex32.com/docs/index.html).
Never enter secret data on that website or any other website. The guides live
on GitHub and can be updated; no documentation ZIP download is needed.
For compiling your own image, use the separate [source-build guide](Codex32_Experimental_Build_Guide.md).

## Image identity and validation

| Item | Value |
| --- | --- |
| Release image | `seedsigner_os.codex32-alpha-0.1.pi0.img` |
| Bytes | `52428800` |
| SHA256 | `5e7d16e84705211c59c0e8739722d7987fc93d490ec619b32c3db62e2e9df55a` |
| Application / proposed tag target | `87a4be4de12e24ce1c7f9e0bfcd6b78a535d3537` |
| Version shown on device | `v0.8.7-Codex32-EC-UX7-test` |
| OS | `d13859392660fe512a753bc14ecd0edc86c35510` |
| Buildroot | `bf2a2858aa675a14b60f1f9142c65b32652609c1` |
| Target / tested hardware | `--pi0`, Pi Zero 1.3, SeedSigner Plus at 240x240 and 320x240 |

The image has passed independent review and the maintainer's device checks.
The wider-screen checks were earlier in development; the final navigation check
used 240x240. Detailed evidence is in the
[build receipt](release/Alpha_0.1_Build_Receipt.json).
The development label above remains inside the tested image; the public release
name is **SeedSigner Codex32 Alpha 0.1**. No image bytes were changed for renaming.

## Download and try it

1. Download the Pi Zero image and `SHA256SUMS` from this release.
2. Verify the image before flashing. In the download folder, run
   `sha256sum -c SHA256SUMS` on Linux. In PowerShell, use
   `Get-FileHash .\seedsigner_os.codex32-alpha-0.1.pi0.img -Algorithm SHA256`
   and compare it with `SHA256SUMS`; on macOS use `shasum -a 256` on the image.
3. Flash with your usual SD image writer. Device testing covers Pi Zero 1.3.
   Check **Settings > Version** for the version string above and `87a4be4`.
4. Follow the linked recovery and test guide. No source build or wallet-software
   setup is required to practice entry and recovery.

Checksums let you compare the download's bytes; they are not a maintainer
signature. An independent identical firmware rebuild has not been established.

## Known limits and reporting

Ordinary correction supports up to four wrong characters, eight unreadable
characters, or mixtures within its bound. A separately warned path supports
one consecutive unreadable run of 9-13. Thirteen uses all checksum redundancy:
another typo elsewhere can produce a checksum-valid but wrong completion.
A saved fingerprint is a 32-bit accidental-error check, not proof of recovery.
Compare the paper and, for an existing wallet, its policy and a known address.

Correction does not repair inserted/deleted characters or move misplaced box
groups. The device cannot determine the true number of mistakes. Other board
images have not been device-tested for this alpha.

Codex32-only users should not encounter the reported **CompactSeedQR** issue:
it affects a separate binary QR backup format for BIP39 word seeds. If you also
use BIP39 seeds in this image, scanning some CompactSeedQR backups may fail.
This was observed in Windows scanner testing; Pi incidence is unknown. Having
both seed types loaded is not itself the trigger. Use manual BIP39 entry or
Standard SeedQR if available; see the [format-specific reporting guidance](Codex32_Experimental_Test_Guide.md#compactseedqr-when-also-using-bip39-seeds).

[Report issues in this fork](https://github.com/FractalEncrypt/FractalEncrypt_seedsigner/issues/new)
using public practice data only. Never attach a real seed, backup or private key.
