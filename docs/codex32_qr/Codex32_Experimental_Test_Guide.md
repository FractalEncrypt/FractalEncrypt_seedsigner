# SeedSigner Codex32 Alpha 0.1: recovery and test guide

**Experimental independent fork: public practice seeds and testnet/regtest only.
Do not enter real backups or mainnet seeds, or use this alpha to secure funds.
Mainnet is not disabled. This is not an official SeedSigner release.**

## Recover a codex32 secret and load it into a signer

Use this guide after flashing the downloaded image or building from source.
The [illustrated user flow](Codex32_User_Flow_Guide.md) shows each step; the
[screen reference](Codex32_Screen_Reference.md) explains the device's messages.

Choose practice material before you start:

- An existing **public or disposable test** codex32 secret or compatible share
  set. This alpha's entry flow supports 48-character strings. Never use a real
  wallet backup for alpha testing.
- A new disposable test secret and shares made offline with the **debiased dice
  method and paper checksum/share worksheets** in the
  [Codex32 illustrated book](https://secretcodex32.com/docs/index.html).
  Follow the book's full randomness and checksum procedure, not an improvised
  dice-to-character mapping. SeedSigner does not create share sets or append
  checksums. Download/print the materials; never enter secret data on a website.
- The [public BIP93 practice vectors](#public-bip93-recovery-vectors-text-and-qr)
  below. They include the NAME and cash shares and the expected recovered secrets.
  Everyone knows these seeds; never fund these wallets.

### First test: scan NAME shares and compare the recovered secret

NAME needs **two distinct shares** (`k=2`). A and C are enough. No wallet software
is needed to perform this recovery test.

1. Start a fresh collection: **Load a Seed -> Scan codex32 Share**. Scan
   **NAME A** below. This first test uses two split shares, not the complete S
   secret QR.

   <img src="test_vectors/bip93-v2-share-a.png" width="296" alt="PUBLIC TEST ONLY: NAME split share A">

   Choose **Scan Next Share**, then scan **NAME C**:

   <img src="test_vectors/bip93-v2-share-c.png" width="296" alt="PUBLIC TEST ONLY: NAME split share C">

2. On **Recovered Seed**, expect fingerprint **`fab6868a`**. Choose
   **Check Fingerprint -> Enter Fingerprint** and enter that public expectation,
   or use the optional visual comparison.
3. Choose **More Options -> Show Master Seed**. Compare every numbered box with
   this expected **NAME S secret**, not just the fingerprint:

   ```text
   MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW
   ```

   | Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | Secret S | `MS12` | `NAME` | `S6XQ` | `GUZT` | `TXKE` | `QNJS` | `JZV4` | `JV3N` | `Z5K3` | `KWGS` | `PHUH` | `6EVW` |

   Return with the top Back button.
4. Choose **Load Seed**, then **Finalize** if prompted. The seed is ready for
   ordinary signer operations such as exporting public keys and deriving addresses.

For cash, start a fresh collection and scan **a + c + d** (`k=3`). Expect
fingerprint **`1e50c111`** and compare its expected S secret. Do not mix shares
from NAME and cash. A standalone S secret may also be typed or scanned directly.

The published seed hex is the BIP32 seed itself, not BIP39 mnemonic entropy.
Converting it to BIP39 words changes the wallet. Export public account keys to
wallet software; do not import the codex32 secret into a software wallet.

## Make a paper practice backup

Print the [codex32 backup cards](printable_templates/Seedsigner_Codex32_Printable_SeedCards.pdf)
at actual size and write down **NAME A** from the reference below. Mark the card
**PUBLIC TEST ONLY**. One card is enough for the entry trials. Use NAME throughout
these first tests so you do not accidentally mix boxes from different share sets.
If you want to practice cash instead, use its [separate reference below](#cash-share-a)
and recover with enough other cash shares.

**NAME A: copy each four-character group into the matching numbered boxes.**

```text
MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share A | `MS12` | `NAME` | `A320` | `ZYXW` | `VUTS` | `RQPN` | `MLKJ` | `HGFE` | `DCAX` | `RPP8` | `70HK` | `KQRM` |

Each column matches one four-box entry page on SeedSigner. For this public
practice card, record threshold **2**, ID **NAME**, share index **A**, and expected
fingerprint **`fab6868a`**. This provides practice for using numbered paper,
rather than repeatedly counting through a 48-character line.

Fingerprints for your own first-time secret must come from a clean recovery;
a newly written fingerprint cannot independently verify that first reconstruction.

All-uppercase and all-lowercase codex32 strings represent the same seed and
wallet. We suggest uppercase for paper legibility; choose either consistent case.
**Mixed-case strings are invalid.** The lowercase cash text is the published
BIP93 spelling; its uppercase QR and transcription groups carry the same data.

Check the completed card against this guide before testing. If you accidentally
write a few characters incorrectly, SeedSigner may propose a repair within its
limits. Compare the proposal with the public reference, repair the paper first,
then re-enter the requested boxes. Do not assume a checksum or fingerprint alone
proves a backup is right. Too many mistakes may prevent any proposal.

## Practice entry and error correction

Start a new collection for each trial. Type the practice share with **Enter
codex32 Seed**; scan the remaining clean shares afterward. Invalid QR payloads
are rejected strictly; character-correction proposals are a manual-entry feature.

Use NAME A as the reference. Make deliberate typing errors while leaving the
paper correct. For unreadable-character trials, enter `?` in the listed boxes;
you need not damage or erase the paper.

| Trial | Change while entering NAME A | Expected result |
| --- | --- | --- |
| One wrong character | Replace box 13 with a different alphabet character | A proposal, numbered review and readable-box re-entry |
| Four wrong characters | Replace boxes 13, 21, 29 and 37 | Four proposed changes to review and re-enter |
| Eight unreadable characters | Enter `?` in boxes 12, 16, 20, 24, 28, 32, 36 and 40 | Eight replacements to review; accept reconstruction only with its caveat |
| Mixed errors | Replace boxes 13 and 21; use `?` in 17, 25, 33 and 41 | A proposal for the two wrong and four unknown characters |
| Long missing run | Use `?` in boxes 13-25 (thirteen consecutive boxes) | A separate large-recovery warning before the proposal |
| Outside device limits | Use `?` in boxes 13-26 (fourteen boxes) | No correction found; review/edit remains available |

On correction review, compare **entered -> proposed** and the numbered boxes.
For readable transcription errors choose **I Mistyped** and re-enter from the
card. If the paper itself is wrong, choose **Backup Corrupted**, repair it against
the public reference while viewing the changes, then re-enter from the repaired
paper. If the original is truly unreadable, do not claim its recovered characters
match the paper: use the reconstruction path and retain its warning.

After reviewing and confirming the entered A share, choose **Scan Next Share**
and scan this clean **NAME C** to complete recovery:

<img src="test_vectors/bip93-v2-share-c.png" width="296" alt="PUBLIC TEST ONLY: NAME split share C after the entry trial">

Expect fingerprint **`fab6868a`**. On **More Options -> Show Master Seed**, compare
all boxes with this **NAME S secret**:

```text
MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Secret S | `MS12` | `NAME` | `S6XQ` | `GUZT` | `TXKE` | `QNJS` | `JZV4` | `JV3N` | `Z5K3` | `KWGS` | `PHUH` | `6EVW` |

Return to **Recovered Seed**, compare the fingerprint (or enter it with
**Check Fingerprint -> Enter Fingerprint**), then choose **Load Seed**.

Use the [user flow](Codex32_User_Flow_Guide.md) for rebuilding an unverified share,
reviewing repeat/conflicting shares and returning to the affected box groups.

The ordinary bound is four wrong characters, eight unknowns, or mixtures where
twice the wrong-character count plus the unknown count is at most eight.
Only one consecutive unknown run of 9-13 has the extended path. Thirteen uses all
checksum redundancy: an additional typo outside the run can yield a wrong,
checksum-valid completion. A 32-bit fingerprint match catches accidental errors;
check the recovered secret, wallet setup and a known address too.

## Optional: export public keys and create coordinator test wallets

### Load the public practice signers

If NAME is already loaded from the preceding tests, keep using it. To load either
practice signer directly, choose **Load a Seed -> Scan codex32 Share** and scan
its complete **S secret** below. This shortcut skips combining split shares;
it is useful when testing public-key exports and wallet setup.

**NAME S: expected fingerprint `fab6868a`**

<img src="test_vectors/bip93-v2-secret.png" width="296" alt="PUBLIC TEST ONLY: NAME complete secret S for wallet tests">

**cash S: expected fingerprint `1e50c111`**

<img src="test_vectors/bip93-v3-secret.png" width="296" alt="PUBLIC TEST ONLY: cash complete secret S for wallet tests">

For each import, compare the fingerprint and choose **Load Seed** (and **Finalize**
if prompted). Both of these seeds are public: never send funds to their wallets.
These seed QRs are for SeedSigner, not for importing secrets into Sparrow/Nunchuk.

If you prefer to recover from `k` split shares instead, use the
[vector QRs below](#public-bip93-recovery-vectors-text-and-qr): choose any two
distinct NAME shares, or any three distinct cash shares. Keep each recovery set
separate. These two sets produce two distinct seeds for the multisig exercise.



Codex32's k-of-N threshold recovers **one seed**. It is independent of a wallet's
m-of-n signature policy. A and C from NAME are not two cosigners: they recover the
same signer. For the following 2-of-2 multisig, use NAME and cash as distinct
signers; optionally add vector 1's `3f3521a6` for a 2-of-3 variant.

### Shared setup and SeedSigner export

1. Set SeedSigner's **Settings -> Advanced -> Bitcoin network -> Testnet** (or Regtest when supported
   by your chosen coordinator/setup). Set the same network in the coordinator
   before creating the wallet. Testnet/regtest coin-type derivation is `1'`;
   addresses depend on the selected network. The references here use Testnet.
2. Load the recovered seed as described above.
3. From the loaded seed, choose **Export Xpub -> Single Sig -> Native Segwit**
   for a single-sig wallet, or **Export Xpub -> Multisig -> Native Segwit** for
   a multisig cosigner. Export these separately: their account paths differ.
4. At **Xpub QR Format**, use **Animated (default)** for a compatible UR account
   scanner, such as Sparrow's SeedSigner importer. If your coordinator expects the static
   public-key format, choose **Static** instead. Keep all animated frames visible
   until the coordinator completes its scan; lower QR density if needed.
5. Read the privacy warning, check the displayed fingerprint/path/key details,
   then choose **Export Xpub**. The coordinator scans this device-displayed QR,
   not the seed/share QRs in the practice-vector section. An xpub export contains public key information.

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

1. In Sparrow go to Tools>Restart In> and choose either Testnet3 or Testnet4.
2. After restart, confirm Sparrow is in the correct testnet network and;
3. Create a new wallet named `Codex32 NAME single-sig TEST` (**File -> New Wallet**).
4. Choose **Single Signature**, **Native Segwit (P2WPKH)**. In its keystore,
   choose **Airgapped Hardware Wallet -> SeedSigner -> Scan**.
5. Scan NAME's **Single Sig** xpub export from SeedSigner. Check fingerprint
   `fab6868a` and path `m/84'/1'/0'`. Choose **Apply** and finish the wallet setup.
6. Compare receive address 0 and change address 0 to the references below and to
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
   Explorer** or address verification. Compare first receive/change addresses.

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

## Limits and reporting

The device cannot determine the true number of mistakes. Correction does not
repair inserted/deleted characters or move misplaced box groups. Review numbered
paper boxes when no correction is found. Other board images and independent
identical firmware rebuilds have not been validated for this alpha.

### CompactSeedQR when also using BIP39 seeds

Codex32 entry and Codex32QR scanning do not use the binary format involved in
this issue. You should not encounter this particular issue while using only the
codex32 features. Codex32 and BIP39 seeds can be loaded in the same session and
used for normal signer operations; having both loaded is not itself the trigger.

The issue concerns scanning **CompactSeedQR**, a separate binary backup format
for BIP39 word seeds. Some payloads were rejected after scanner-library text
conversion in Windows testing. Whether the same issue occurs on Pi hardware is
unknown. It does not apply to the supplied text-based Codex32QR practice shares.

If a BIP39 CompactSeedQR fails, use manual BIP39 word entry or a Standard SeedQR
backup, if available. [Open an issue in this fork](https://github.com/FractalEncrypt/FractalEncrypt_seedsigner/issues/new)
with the version, board, scan format and observed behavior. Reproduce with a
public practice seed before attaching any QR. Never post a real backup. If the
same problem is reproduced on an official upstream build, include that version
in an [upstream issue](https://github.com/SeedSigner/seedsigner/issues/new) and
link the reports; this fork's behavior alone does not establish an upstream bug.

### Report a practice test

[Open an issue here](https://github.com/FractalEncrypt/FractalEncrypt_seedsigner/issues/new)
with Settings > Version, board, display setting, language, practice-vector name,
changed box numbers and expected/actual results. Include public-data screenshots
where useful. Never attach a private seed, backup, fingerprint, xpub or wallet file.

## Public BIP93 recovery vectors: text and QR

**PUBLIC TEST ONLY: never fund these wallets.** The following QRs are inputs for
SeedSigner, not public-key exports for wallet software. Each QR contains one raw
uppercase 48-character string. The expected fingerprints are computed from the
published seed bytes; BIP93 does not publish these fingerprints.

QRs are displayed one per section with space between them. Open a QR for its full
296x296 image; keep its white quiet zone when printing. Cover other codes in the
camera's view. The raw strings and four-character groups contain identical data.

These are the complete split-share sets and principal S outputs for BIP93's
48-character vectors 1-3. Longer vectors 4-8 and alternate padding examples are
outside this guide. See [BIP93's complete vectors](https://github.com/bitcoin/bips/blob/master/bip-0093.mediawiki#test-vectors),
the [plain-text set](test_vectors/bip93_128bit_vectors.txt) and
[payload/hash manifest](test_vectors/bip93_128bit_vectors.json).

### Vector 2: k=2, identifier NAME

Any two distinct shares from A/C/D recover NAME. Begin with A + C.

#### NAME share A

```text
MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share A | `MS12` | `NAME` | `A320` | `ZYXW` | `VUTS` | `RQPN` | `MLKJ` | `HGFE` | `DCAX` | `RPP8` | `70HK` | `KQRM` |

<img src="test_vectors/bip93-v2-share-a.png" width="296" alt="PUBLIC TEST ONLY: NAME share A">

---

#### NAME share C

```text
MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share C | `MS12` | `NAME` | `CACD` | `EFGH` | `JKLM` | `NPQR` | `STUV` | `WXYZ` | `023F` | `TR2G` | `DZMP` | `Y6PN` |

<img src="test_vectors/bip93-v2-share-c.png" width="296" alt="PUBLIC TEST ONLY: NAME share C">

---

#### NAME share D

```text
MS12NAMEDLL4F8JLH4E5VDVULDLFXU2JHDNLSM97XVENRXEG
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share D | `MS12` | `NAME` | `DLL4` | `F8JL` | `H4E5` | `VDVU` | `LDLF` | `XU2J` | `HDNL` | `SM97` | `XVEN` | `RXEG` |

<img src="test_vectors/bip93-v2-share-d.png" width="296" alt="PUBLIC TEST ONLY: NAME share D">

---

#### NAME recovered secret S

Expected S secret (the complete seed backup):

```text
MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Secret S | `MS12` | `NAME` | `S6XQ` | `GUZT` | `TXKE` | `QNJS` | `JZV4` | `JV3N` | `Z5K3` | `KWGS` | `PHUH` | `6EVW` |

Seed hex: `d1808e096b35b209ca12132b264662a5`
Master fingerprint: **`fab6868a`**

<details>
<summary>Complete-secret QR: direct import, skips split-share recovery</summary>

<img src="test_vectors/bip93-v2-secret.png" width="296" alt="PUBLIC TEST ONLY: NAME complete secret S">

</details>

### Vector 3: k=3, identifier cash

Any three distinct shares from a/c/d/e/f recover cash. Begin with a + c + d.

#### CASH share A

```text
ms13casha320zyxwvutsrqpnmlkjhgfedca2a8d0zehn8a0t
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share A | `MS13` | `CASH` | `A320` | `ZYXW` | `VUTS` | `RQPN` | `MLKJ` | `HGFE` | `DCA2` | `A8D0` | `ZEHN` | `8A0T` |

<img src="test_vectors/bip93-v3-share-a.png" width="296" alt="PUBLIC TEST ONLY: cash share A">

---

#### CASH share C

```text
ms13cashcacdefghjklmnpqrstuvwxyz023949xq35my48dr
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share C | `MS13` | `CASH` | `CACD` | `EFGH` | `JKLM` | `NPQR` | `STUV` | `WXYZ` | `0239` | `49XQ` | `35MY` | `48DR` |

<img src="test_vectors/bip93-v3-share-c.png" width="296" alt="PUBLIC TEST ONLY: cash share C">

---

#### CASH share D

```text
ms13cashd0wsedstcdcts64cd7wvy4m90lm28w4ffupqs7rm
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share D | `MS13` | `CASH` | `D0WS` | `EDST` | `CDCT` | `S64C` | `D7WV` | `Y4M9` | `0LM2` | `8W4F` | `FUPQ` | `S7RM` |

<img src="test_vectors/bip93-v3-share-d.png" width="296" alt="PUBLIC TEST ONLY: cash share D">

---

#### CASH share E

```text
ms13casheekgpemxzshcrmqhaydlp6yhms3ws7320xyxsar9
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share E | `MS13` | `CASH` | `EEKG` | `PEMX` | `ZSHC` | `RMQH` | `AYDL` | `P6YH` | `MS3W` | `S732` | `0XYX` | `SAR9` |

<img src="test_vectors/bip93-v3-share-e.png" width="296" alt="PUBLIC TEST ONLY: cash share E">

---

#### CASH share F

```text
ms13cashf8jh6sdrkpyrsp5ut94pj8ktehhw2hfvyrj48704
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Share F | `MS13` | `CASH` | `F8JH` | `6SDR` | `KPYR` | `SP5U` | `T94P` | `J8KT` | `EHHW` | `2HFV` | `YRJ4` | `8704` |

<img src="test_vectors/bip93-v3-share-f.png" width="296" alt="PUBLIC TEST ONLY: cash share F">

---

#### CASH recovered secret S

Expected S secret (the complete seed backup):

```text
ms13cashsllhdmn9m42vcsamx24zrxgs3qqjzqud4m0d6nln
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Secret S | `MS13` | `CASH` | `SLLH` | `DMN9` | `M42V` | `CSAM` | `X24Z` | `RXGS` | `3QQJ` | `ZQUD` | `4M0D` | `6NLN` |

Seed hex: `ffeeddccbbaa99887766554433221100`
Master fingerprint: **`1e50c111`**

<details>
<summary>Complete-secret QR: direct import, skips split-share recovery</summary>

<img src="test_vectors/bip93-v3-secret.png" width="296" alt="PUBLIC TEST ONLY: cash complete secret S">

</details>

### Vector 1: k=0, identifier test

Standalone secret: no split-share combination is needed.

#### TEST recovered secret S

Expected S secret (the complete seed backup):

```text
ms10testsxxxxxxxxxxxxxxxxxxxxxxxxxx4nzvca9cmczlw
```

| Backup | 1-4 | 5-8 | 9-12 | 13-16 | 17-20 | 21-24 | 25-28 | 29-32 | 33-36 | 37-40 | 41-44 | 45-48 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Secret S | `MS10` | `TEST` | `SXXX` | `XXXX` | `XXXX` | `XXXX` | `XXXX` | `XXXX` | `XXX4` | `NZVC` | `A9CM` | `CZLW` |

Seed hex: `318c6318c6318c6318c6318c6318c631`
Master fingerprint: **`3f3521a6`**

<details>
<summary>Complete-secret QR: direct import, skips split-share recovery</summary>

<img src="test_vectors/bip93-v1-secret.png" width="296" alt="PUBLIC TEST ONLY: test complete secret S">

</details>

