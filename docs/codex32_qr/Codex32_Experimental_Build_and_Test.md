# Experimental Codex32 EC: build and test

**Experimental fork: public test seeds and testnet/regtest only. Do not enter
real backups, mainnet seeds, or use this image to secure funds.** These are tester
instructions, not an upstream SeedSigner release endorsement. The software is
not restricted to testnet by code; this warning is a testing policy.

The upstream build guide explains Docker and hardware selection, but its default
application repository is upstream SeedSigner. A fresh checkout of our tested OS
revision also needs explicit version metadata. The numbered-entry/correction
feature is documented in [Codex32 Error Correction](Codex32_Error_Correction.md).

## Tested UX6 image and current branch

The maintainer built and tested UX6 on Pi Zero 1.3 with a SeedSigner Plus display
set to 240x240. All four focused physical checks passed on 2026-10-10, including
numbered entry/re-entry, identical repeats, conflicting-share comparison and
choices, repair-caveat retention, fingerprint entry and nested-SegWit signing.
Navigation results are operator-reported. The signed synthetic PSBT was decoded
from the device video; its ECDSA signature verifies and all unsigned transaction
and non-signature PSBT fields match the fixture. No transaction was broadcast.

| Tested build input | Revision |
| --- | --- |
| Runtime application commit | `528031b63e4f8805e7f73fb3bb5355f630f53e86` |
| Version label | `v0.8.7-Codex32-EC-UX6-test` |
| Pi Zero output label | `codex32-ec-ux6-test` |
| OS commit | `d13859392660fe512a753bc14ecd0edc86c35510` |
| Buildroot commit | `bf2a2858aa675a14b60f1f9142c65b32652609c1` |

The tested image is `seedsigner_os.codex32-ec-ux6-test.pi0.img`, 52,428,800 bytes,
SHA256 `48870161174ec734b3e37bdd2353b611377ef5254594c9ba38e0066a82d3ed3c`.
These identify the maintainer image; no downloadable GitHub release is published.
A fresh build need not match its binary hash: independent reproducibility is
not established. The commands below deliberately build the tested UX6 pin.

The reviewed UX7 navigation follow-up is committed at
`87a4be4de12e24ce1c7f9e0bfcd6b78a535d3537`. **Keep Saved Share** returns directly
to the existing scan-or-enter choice. Independent review passed with followups;
616 normal and 183 focused optimized tests passed. A fresh UX7 image and one
focused physical navigation check are pending. It is absent from the tested UX6
image above. Do not substitute branch HEAD for an image's exact source pin.
The clean-build commands below build this reviewed UX7 candidate.

UX6 validation passed 614 normal tests, 181 focused optimized tests and GitHub CI
on Python 3.10/3.12. Its reviewed layout covers all 76 English states at 240x240
and 240x320; 22 locale-generation runs passed on the review candidate. Historical
UX5 physical tests were at 240x320; they do not establish UX6's 240x240 coverage.

Use the [illustrated user flow](Codex32_User_Flow_Guide.md),
[screen reference](Codex32_Screen_Reference.md) and
[image validation notes](Codex32_Experimental_Release_Notes.md).
The [release checklist](Codex32_Experimental_Release_Checklist.md) is for maintainers.

## Known testing limits

- A pre-existing CompactSeedQR scanner issue rejects some binary payloads after
  text-encoding conversion on the Windows scanner library. Pi incidence is unknown;
  it remains unfixed. Use the supplied plain-text Codex32 share QRs for these tests.
- Separate Raspberry Pi OS / Python 3.13.5 correction benchmarks measured warm
  medians around 10-21 ms. These exclude the firmware GUI and do not establish an
  exact firmware timing guarantee.
- Physical tests cover Pi Zero 1.3 with SeedSigner Plus at 240x240 for UX6 and
  240x320 historically. Other board images, independent byte-identical rebuilds,
  stable-release readiness and real-funds use are not established.

## Current reviewed UX7 build on Linux / WSL2 / macOS

Install Git, Python 3, and Docker Engine or Docker Desktop with Compose support.
Use a fresh directory, not an existing SeedSigner OS build. On Windows, use WSL2
and clone inside its Linux filesystem (for example under `~/`), so Unix symlinks
and executable permissions are preserved. Allow the disk space/build time
specified in the [upstream guide](https://github.com/SeedSigner/seedsigner-os/blob/d13859392660fe512a753bc14ecd0edc86c35510/docs/building.md).

The commands below build Pi Zero / Zero W. They are intentionally pinned rather
than tracking the changing branch tip.

```bash
mkdir codex32-ec-test-build
cd codex32-ec-test-build

git clone --no-checkout https://github.com/SeedSigner/seedsigner-os.git
git -C seedsigner-os checkout --detach d13859392660fe512a753bc14ecd0edc86c35510
git -C seedsigner-os submodule update --init --recursive

cd seedsigner-os
git clone --no-checkout https://github.com/FractalEncrypt/FractalEncrypt_seedsigner.git opt/rootfs-overlay/opt
git -C opt/rootfs-overlay/opt checkout --detach 87a4be4de12e24ce1c7f9e0bfcd6b78a535d3537
git -C opt/rootfs-overlay/opt submodule update --init --recursive src/seedsigner/resources/seedsigner-translations
```

Generate required version metadata from the pinned commit. The startup screen
needs this file; cloning the application alone does not supply it.

```bash
python3 - <<'PY'
from pathlib import Path
import json, subprocess
from datetime import datetime, timezone
app = Path('opt/rootfs-overlay/opt')
def git(*args):
    return subprocess.check_output(['git', '-C', str(app), *args], text=True).strip()
commit = git('rev-parse', 'HEAD')
assert commit == '87a4be4de12e24ce1c7f9e0bfcd6b78a535d3537'
metadata = {
    'name': 'v0.8.7-Codex32-EC-UX7-test',
    'fork': 'FractalEncrypt',
    'short_commit_hash': commit[:7],
    'timestamp': datetime.fromisoformat(git('show', '-s', '--format=%cI', 'HEAD')).astimezone(timezone.utc).isoformat(),
}
(app / 'src/seedsigner/version.json').write_text(json.dumps(metadata, indent=4) + '\n', encoding='utf-8')
print(json.dumps(metadata, indent=2))
PY
```

Prepare translations/fonts with the pinned OS builder's existing function, then
retain only the runtime `src` tree in this fresh overlay. This preparation runs
in Docker and is not the firmware compilation. The function definitions are
loaded only up to the argument parser, so sourcing does not start a build.

```bash
export DOCKER_DEFAULT_PLATFORM=linux/amd64
docker compose build

docker compose run --rm --entrypoint bash build-images -lc '
set -euo pipefail
cd /opt
source <(awk "/^### Gather Arguments passed into build.sh script/{exit} {print}" build.sh)
rootfs_overlay=./rootfs-overlay
compile_translations_and_fonts
cd /opt/rootfs-overlay/opt
test -s src/seedsigner/version.json
test -f src/seedsigner/models/codex32_correction.py
find . -mindepth 1 -maxdepth 1 ! -name src -exec rm -rf -- {} +
'
```

Keep `--skip-repo`: fetching again would replace the prepared overlay and remove
its version file. Use a slash-free output label; the upstream script inserts this
label into the filename. Do not pass `codex/codex32-error-correction` as the output
label. Keep the usual clean build; do not add `--dev` or `--no-clean`.

```bash
export SS_ARGS='--pi0 --skip-repo --app-branch=codex32-ec-ux7-test'
docker compose up --force-recreate --build
```

Expected image: `images/seedsigner_os.codex32-ec-ux7-test.pi0.img`.
Confirm completion with exit code zero, then hash it before mounting/flashing:

```bash
sha256sum images/seedsigner_os.codex32-ec-ux7-test.pi0.img
```

On macOS, use `shasum -a 256` if `sha256sum` is unavailable. For another board,
use the upstream board table and replace `--pi0`; those targets are not validated
by the Pi Zero 1.3 tests. Flash using the existing upstream image-writing steps.
After boot, check `v0.8.7-Codex32-EC-UX7-test` and `87a4be4` in Settings > Version.

This procedure has been checked against the pinned builder and its shell syntax;
a complete fresh image build has not been run for this revision of the guide.
The generated metadata identifies the reviewed UX7 application. No UX7 image hash
or device success is claimed yet. Public receipts must also identify generated
build inputs; equal application commits do not imply equal firmware hashes.
An independent byte-identical rebuild has not been established.

## Public BIP93 recovery vectors: text and QR

**Public test data: never fund these wallets.** These QRs are seed/share inputs
for **SeedSigner**, not xpub exports for the coordinator. Each QR contains only
one uppercase 48-character Codex32 string, with no label or URI wrapper. Vector
3's lowercase text and uppercase QR encode the same share; mixed case is invalid.
Click an image to open/download its full 296x296 PNG. Keep the white border when
printing, and cover neighboring codes so the camera scans the intended share.

These include all split shares and principal recovered secrets from the BIP93
48-character vectors 1-3. Longer vectors 4-8 are outside this device guide's 48-box scope;
alternative padding examples are omitted to keep the listed share sets unambiguous; see [BIP93's full test vectors](https://github.com/bitcoin/bips/blob/master/bip-0093.mediawiki#test-vectors).
The [plain-text set](test_vectors/bip93_128bit_vectors.txt) and
[payload/hash manifest](test_vectors/bip93_128bit_vectors.json) are downloadable.
Fingerprints below are computed from the published seed bytes, not printed by BIP93.

For the complete device walkthrough, see the [Codex32 User Flow Guide](Codex32_User_Flow_Guide.md).

### Vector 2: k=2, identifier NAME

Recover with A + C; D is the published additional share. Any two of A/C/D recover the same seed.

```text
Share A: MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM
Share C: MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN
Share D: MS12NAMEDLL4F8JLH4E5VDVULDLFXU2JHDNLSM97XVENRXEG
```

| Share A | Share C | Share D |
| --- | --- | --- |
| <img src="test_vectors/bip93-v2-share-a.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 2, share A"> | <img src="test_vectors/bip93-v2-share-c.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 2, share C"> | <img src="test_vectors/bip93-v2-share-d.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 2, share D"> |

Expected recovered S-share:

```text
MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW
```

Seed hex: `d1808e096b35b209ca12132b264662a5`

Master fingerprint: **`fab6868a`**

<details>
<summary>Recovered S QR (direct-secret import; bypasses share recovery)</summary>

<img src="test_vectors/bip93-v2-secret.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 2, share S">

</details>

### Vector 3: k=3, identifier cash

Start with a + c + d. Any three distinct shares from a/c/d/e/f recover the same seed.

```text
Share a: ms13casha320zyxwvutsrqpnmlkjhgfedca2a8d0zehn8a0t
Share c: ms13cashcacdefghjklmnpqrstuvwxyz023949xq35my48dr
Share d: ms13cashd0wsedstcdcts64cd7wvy4m90lm28w4ffupqs7rm
Share e: ms13casheekgpemxzshcrmqhaydlp6yhms3ws7320xyxsar9
Share f: ms13cashf8jh6sdrkpyrsp5ut94pj8ktehhw2hfvyrj48704
```

| Share A | Share C | Share D |
| --- | --- | --- |
| <img src="test_vectors/bip93-v3-share-a.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 3, share A"> | <img src="test_vectors/bip93-v3-share-c.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 3, share C"> | <img src="test_vectors/bip93-v3-share-d.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 3, share D"> |

| Share E | Share F |
| --- | --- |
| <img src="test_vectors/bip93-v3-share-e.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 3, share E"> | <img src="test_vectors/bip93-v3-share-f.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 3, share F"> |

Expected recovered S-share:

```text
ms13cashsllhdmn9m42vcsamx24zrxgs3qqjzqud4m0d6nln
```

Seed hex: `ffeeddccbbaa99887766554433221100`

Master fingerprint: **`1e50c111`**

<details>
<summary>Recovered S QR (direct-secret import; bypasses share recovery)</summary>

<img src="test_vectors/bip93-v3-secret.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 3, share S">

</details>

### Vector 1: standalone secret, k=0, identifier test

Use this to test direct-secret loading, or as a third distinct signer for an
optional 2-of-3 test wallet. No share collection is needed.

```text
ms10testsxxxxxxxxxxxxxxxxxxxxxxxxxx4nzvca9cmczlw
```

<img src="test_vectors/bip93-v1-secret.png" width="222" alt="PUBLIC TEST ONLY: BIP93 vector 1, share S">

Seed hex: `318c6318c6318c6318c6318c6318c631`

Master fingerprint: **`3f3521a6`**

### Recover and load a signer

1. Start a fresh share collection: **Load a Seed -> Scan Codex32 Share** (or
   **Enter Codex32 Seed** for an EC trial). Scan/enter vector 2 A, then C; or
   vector 3 a, then c, then d. Do not mix NAME and cash. Start a new collection
   between vectors, rather than trying to append a different seed's shares.
2. At **Recovered Seed**, compare the fingerprint to the public expectation
   above. **Check Fingerprint -> Enter Fingerprint** exercises exact entry;
   visual comparison is also available. Keep any reconstruction caveat visible.
3. To check the expected S text, choose **More Options -> Show Master Seed**
   and review both numbered pages. Return to the recovered-seed screen.
4. Choose **Load Seed**, then **Finalize** if prompted. This loads one signing
   seed. Keep track of it by fingerprint: NAME `fab6868a`, cash `1e50c111`.
5. Repeat for the other vector when preparing multisig. You can reuse one physical
   SeedSigner: recover/export one signer at a time. Reload its shares when needed.

The hex above is the BIP32 seed itself, not BIP39 mnemonic entropy. Do not
convert it into BIP39 words or import a backup/share QR into the coordinator's
software-wallet seed importer; those paths either change the wallet or put the
secret into the coordinator. The intended flow exports public account keys only.

## Safe tester smoke checks

Use vector 2 A/C above. Manual entry exercises Codex32 correction; the clean QRs
exercise scanning and threshold recovery. Invalid QR payloads are rejected rather
than offered Codex32 character corrections.

- Recover clean A + C and compare the fingerprint.
- Enter A with one deliberate substitution. Review `entered -> proposed`, check
  the numbered boxes against A, choose the mistyped path, and re-enter the affected
  box from A. Verify the correction marker and then recover with C.
- Enter A with eight separated `?` characters. Exercise the readable/unreadable
  distinction and the fingerprint record entry or visual comparison.
- Enter A with thirteen consecutive `?` characters. Read the large-recovery
  warning, review the reconstruction, and recover with clean C. Check that the
  reconstruction guidance remains visible after fingerprint comparison.
- Enter A with fourteen `?` characters. Expect the red failure icon and no
  correction. Review & Edit must permit several edits without repeatedly moving
  focus to OK. Returning to enough known characters may make a proposal possible.
- Rebuild an unverified entered share from clean A. Forward/back navigation must
  reach unresolved boxes; OK becomes enabled and orange after the final box.

The ordinary bound is four substitutions, eight erasures, or mixed `2S+E <= 8`.
Only a single consecutive erasure run of 9-13 has the larger recovery path.
An extra typo outside that run can produce a wrong, checksum-valid completion.
A 32-bit fingerprint comparison catches accidental mistakes; it is not wallet
authentication. Verify policy and known addresses when testing wallet integration.

Report the application revision, board, display/language, test input positions,
expected/actual behavior, and photographs using public test data. Do not post
private shares, real fingerprints, xpubs, or wallet details with a bug report.


## Export public keys and create coordinator test wallets

Codex32's k-of-N threshold recovers **one seed**. It is independent of a wallet's
m-of-n signature policy. A and C from NAME are not two cosigners: they recover the
same signer. For the following 2-of-2 multisig, use NAME and cash as distinct
signers; optionally add vector 1's `3f3521a6` for a 2-of-3 variant.

### Shared setup and SeedSigner export

1. Set SeedSigner's **Settings -> Advanced -> Bitcoin network -> Testnet** (or Regtest when supported
   by your chosen coordinator/setup). Set the same network in the coordinator
   before creating the wallet. Testnet/regtest coin-type derivation is `1'`;
   addresses depend on the selected network. The references here use Testnet.
2. Load the recovered seed as described above. Enable the needed **Single Sig**
   and **Multisig** options in Settings if either menu is hidden. Select
   **Native Segwit** and account 0 for this test.
3. From the loaded seed, choose **Export Xpub -> Single Sig -> Native Segwit**
   for a single-sig wallet, or **Export Xpub -> Multisig -> Native Segwit** for
   a multisig cosigner. Export these separately: their account paths differ.
4. At **Xpub QR Format**, use **Animated (default)** for a compatible UR account
   scanner, such as Sparrow's SeedSigner importer. Current menus use format
   names, not Sparrow/Nunchuk buttons. If your coordinator expects the static
   public-key format, choose **Static** instead. Keep all animated frames visible
   until the coordinator completes its scan; lower QR density if needed.
5. Read the privacy warning, check the displayed fingerprint/path/key details,
   then choose **Export Xpub**. The coordinator scans this device-displayed QR,
   not the seed/share QRs above. An xpub export contains public key information.

| Wallet test | Script | Account path (Testnet) |
| --- | --- | --- |
| Single Sig, Native Segwit | P2WPKH | `m/84'/1'/0'` |
| Multisig, Native Segwit | P2WSH | `m/48'/1'/0'/2'` |

`h` and `'` both mean hardened derivation. Coordinators may show tpub/vpub/Vpub
encodings of account keys; the prefix alone does not determine the whole wallet
policy. Preserve the fingerprint, full origin path, account, script and network.
The [computed reference file](test_vectors/testnet_wallet_references.json)
includes normalized tpubs and exact first receive/change addresses. These wallet
references are computed locally, not additional published BIP93 vectors.

### Sparrow: single-sig

1. Start Sparrow on Testnet and confirm its network indicator. Create a new
   wallet named `Codex32 NAME single-sig TEST` (**File -> New Wallet**).
2. Choose **Single Signature**, **Native Segwit (P2WPKH)**. In its keystore,
   choose **Airgapped Hardware Wallet -> SeedSigner -> Scan**.
3. Scan NAME's **Single Sig** xpub export from SeedSigner. Check fingerprint
   `fab6868a` and path `m/84'/1'/0'`. Choose **Apply** and finish the wallet setup.
4. Compare receive address 0 and change address 0 to the references below and to
   SeedSigner's **Address Explorer**. Save/export the wallet configuration.
   The coordinator has a watch-only keystore; signing still happens on SeedSigner.

Repeat with cash (`1e50c111`) if you want a second single-sig test.
See the [official SeedSigner/Sparrow export walkthrough](https://github.com/SeedSigner/seedsigner/blob/dev/docs/dice_verification.md#create-new-wallet-from-seed-in-sparrow-wallet-to-see-xpubzpub-and-addresses)
and [Sparrow's keystore documentation](https://sparrowwallet.com/docs/quick-start.html).
Use the Codex32 recovery steps here in place of that walkthrough's seed creation.

### Sparrow: 2-of-2 multisig

1. Create a separate wallet named `Codex32 NAME+cash 2of2 TEST` and choose
   **Multi Signature**, **2 of 2**, **Native Segwit (P2WSH)**.
2. In keystore 1, choose **Airgapped Hardware Wallet -> SeedSigner -> Scan**.
   Scan NAME's **Multisig** xpub export; check `fab6868a` and `m/48'/1'/0'/2'`.
3. In keystore 2, scan cash's **Multisig** export; check `1e50c111` and the same
   path. Verify the two keys are distinct. Choose **Apply** to create the wallet.
4. Save the wallet file and export its descriptor/configuration. Retain both
   cosigner fingerprints, origin paths, xpubs, sorted key policy, threshold,
   script type and network. A fingerprint or the seeds alone does not specify
   the complete multisig wallet.
5. In Sparrow use **File -> Export Wallet -> Output Descriptor -> Show QR**
   (or the SeedSigner-compatible policy export offered by that version). Scan
   that public wallet-policy QR into SeedSigner when prompted by **Address
   Explorer** or address verification. Compare first receive/change addresses. Do not scan a
   PSBT where a wallet-policy QR is expected, or vice versa.

For the optional 2-of-3 variant, add vector 1's separate multisig export as a
third keystore, then select 2-of-3. Its addresses differ from the 2-of-2 references.

### Nunchuk (or another coordinator)

Nunchuk's desktop/mobile menu labels differ by release. Use the public-key /
air-gapped signer import, not a software-key seed import. Start by switching its
[network settings to Testnet](https://resources.nunchuk.io/getting-started/networksettings/).
If the installed version lacks the required test network or QR format, use a
compatible test build/coordinator; do not switch this exercise to mainnet.

1. Use **Add Key** and the air-gapped/public-key import workflow. Name the signer
   `Codex32 NAME TEST`, scan the appropriate SeedSigner xpub export, and review
   `fab6868a`, script, network and origin path. Use the QR format accepted by that Nunchuk version: animated export needs a
   compatible UR account scanner; try **Static** only where its import supports
   origin/path/account-key text. If QR import is unavailable but manual public
   signer import exists, enter the device-exported fingerprint, path and account
   key there, and record the QR interoperability limitation.
2. For [single-sig](https://resources.nunchuk.io/getting-started/createsinglesigwallet/),
   create a wallet with that one single-sig account key and one required signature.
   Review the wallet and create it. Save the wallet/BSMS configuration.
3. For [multisig](https://resources.nunchuk.io/getting-started/singledevicemultisig/),
   import two distinct **Multisig** account keys, NAME and cash, with the BIP48
   paths above. Create a wallet, assign both keys, require two signatures, review
   Native Segwit and the entire policy, then create and back up its BSMS/config.
4. Compare addresses against the same policy references below. For another
   coordinator, use its corresponding watch-only xpub/signer import and preserve
   all origin/policy fields. If it rejects a format, record the exact version and
   error instead of substituting secret imports or changing derivation blindly.

These coordinator instructions are based on application code and official docs.
The new guide has not been exercised end-to-end in every coordinator/version;
please report the version, QR format, network and any interoperability issue.

[Sparrow's descriptor exporter](https://github.com/sparrowwallet/sparrow/blob/master/src/main/java/com/sparrowwallet/sparrow/io/Descriptor.java)
provides a scannable public wallet-policy export.

### Address and repeat-recovery checks

| Testnet wallet | Receive address 0 | Change address 0 |
| --- | --- | --- |
| Vector 2 single-sig | `tb1qd8lkxcn54rt5jhdwlaawvfgc97zyun3as4p3lj` | `tb1qezqrac2z7hnhwgex5cqg527em89fypxpu2qhad` |
| Vector 3 single-sig | `tb1qcnfn2zgjjgavcl6svj0gt6undzd64n2q04p3pw` | `tb1q2zvanfeh0sw8uuqmz5qe2kmaektsrvtc2zw8c8` |
| NAME+cash 2-of-2 sortedmulti | `tb1q9p4mnuuct36kd5mzcyxyfrl9jlu6h40zllffnl3pjqnm97ql2wsswat9fd` | `tb1q8fx9axn6pas9hdjhk5v38zcxku5vgkunpsnqugtv0epxp4ad3vlsumh0em` |

Addresses are for account 0 and the exact policies above. An empty balance is
expected and is not a recovery-integrity test. Match the descriptor/account key
and known addresses, not merely an eight-character fingerprint or lack of funds.

After saving the coordinator wallet and policy, power down SeedSigner. Recover
from the same public share set again (for example use a corrected manual entry
on the second run), compare the fingerprint, re-export the same account, and
verify the same account key and addresses. This checks repeat recovery across a
power cycle. Policy export/re-import should also reproduce those addresses.

Signing is a separate optional test: in a coordinator on your disposable regtest
setup, create a PSBT, scan it with the appropriate recovered seed, review outputs
and change, sign, and scan the signed PSBT back into the coordinator. A 2-of-2
wallet needs both distinct signers; one public test seed can sign only its own
cosigner inputs. The funded/signing test is not required to confirm key export
or address agreement, and these published keys must never protect real funds.
