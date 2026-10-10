# Codex32 user flow guide

Import worksheet shares, review entry corrections, recover the secret, and check
it before loading a seed. SeedSigner can validate and recover hand-calculated
shares; it does not offer a Codex32 share-creation or checksum-appending command.

**This is an experimental independent fork. Test with public seeds and
testnet/regtest only; do not enter real backups or secure funds with this build.**
Use the [build and test guide](Codex32_Experimental_Build_and_Test.md) for the
public BIP93 A/C and cash share QRs, expected fingerprints, and coordinator
single-sig/multisig walkthroughs.

The illustrations use the public BIP93 codex32 test vector "NAME", with fingerprint
`fab6868a`. The flow also applies to other compatible split codex32 shares.
The entry header identifies the share; the next line says **Boxes 17-20** (for
example), followed by the individual numbered boxes.

These are English software renders at 240x240, with hardware mocked, rather than
device photos. UX6 physical checks passed at 240x240. The later Keep Saved Share
navigation change needs a focused device check; see the build guide for source
pins and validation scope.
For every Codex32 screen and its meaning, including error and backup paths, see
the [screen reference](Codex32_Screen_Reference.md). Camera illustrations use a
placeholder, and some menus scroll beyond the first screenshot.

## 1. Prepare the shares and any existing wallet record

Use the original worksheets or numbered backup cards. Their numbering matches
the device's 48 boxes. Keep the worksheet as the source when checking a shifted
entry or uncertain hand calculation. SeedSigner checks the complete string's
checksum, but a checksum-valid reconstruction does not prove which wallet you
intended. Printable cards are available in the
[backup-card PDF](printable_templates/Seedsigner_Codex32_Printable_Page_SeedCards.pdf).

For an existing wallet, have its previously saved master fingerprint, network,
script type, account/derivation and a known address or public descriptor ready.
For multisig, keep the complete policy, including threshold, cosigners and key
ordering. A fingerprint and a few script-type checkboxes are not a full wallet
policy backup. If this is first setup, there is no prior fingerprint to compare
with; follow the first-setup guidance in step 4.

## 2. Enter or scan the first share

Choose **Load a Seed -> Enter codex32 Seed** for manual entry, or **Scan codex32
Share** for a QR. The general SeedQR camera path also recognizes Codex32 inputs.

| Manual entry | Share scan |
| --- | --- |
| ![Numbered first-share keyboard](img/screens/entry_first.png) | ![Codex32 scan camera placeholder](img/screens/scan_share.png) |

Manual entry advances through four numbered boxes at a time. `MS1` stays locked.
Use `?` for a character you cannot read; it occupies the box and requests
correction when you submit the complete entry. Joystick press and each of the
three vertical buttons select the highlighted keyboard character. Left/right
arrows let you revisit box groups.

When a share is valid and fewer than `k` compatible shares are present, **Share
Accepted** offers **Enter Next Share**, **Scan Next Share**, or **Discard**.
You can alternate typing and scanning. Subsequent manual shares lock the already
established threshold and identifier; the index remains editable. Use different
indices from one share set.

| Accepted first share | Next share with locked header |
| --- | --- |
| ![One of two shares accepted](img/screens/share_accepted.png) | ![Next-share numbered entry](img/screens/entry_next.png) |

A different threshold/identifier produces **Wrong Share Set**. Repeating an
identical share produces **Share Already Added**: use **Scan New Share**, or
**Discard This Entry** to return to entry-method choices. Your saved shares and
any repair history remain intact; repeating a share adds nothing toward `k`.

Different checksum-valid content under an already saved index produces
**Share Conflict**. Choose **Compare Shares** to see the differing numbered boxes
as `Saved -> New`, then check your original backup or another independent trusted
record. **Choose Share** returns to the choices; viewing the comparison does not
accept either copy. **Keep Saved Share** discards the new entry and asks whether
to enter or scan the next share;
**Use New Share** explicitly replaces the saved copy. The checksum cannot identify
which of two valid strings belongs to your backup. If you cannot establish which
is correct, keep the saved entry unchanged and investigate rather than guess.

| Identical repeat | Different content, same index | Numbered comparison |
| --- | --- | --- |
| ![Share Already Added](img/screens/duplicate_share.png) | ![Share Conflict choices](img/screens/share_conflict.png) | ![Saved-to-new differences](img/screens/conflict_compare_1.png) |

Discarding an invalid entry retains the valid collection; **Discard All Shares**
asks for confirmation.

## 3. Review an invalid entry before accepting a correction

Scanned QRs use strict validation. Manual entry can propose up to four
substitutions, eight scattered `?` erasures, or mixtures satisfying `2S + E <= 8`.
A transposition of two different characters counts as two substitutions. The
fixed decoder does not search for insertions, deletions or shifted box groups.
See [error-correction details](Codex32_Error_Correction.md) for the exact bounds.

| Supported proposal | No supported proposal |
| --- | --- |
| ![Invalid entry with View Correction](img/screens/correction_available.png) | ![No Correction Found with red failure icon](img/screens/no_correction.png) |

**View Correction** shows the proposed string in two numbered pages. Highlighted
boxes and `*` labels mark replacements. **Review Each Change** then shows the
box number and `entered -> proposed` pairs. Compare these with your backup while
they remain on screen, then choose **Continue**. No proposal is accepted simply
because you viewed it.

| Numbered proposed changes | Original and proposed characters |
| --- | --- |
| ![Highlighted correction boxes](img/screens/correction_boxes_1.png) | ![Entered-to-proposed pairs](img/screens/change_pairs.png) |

**No Correction Found** means there is no supported proposal. Errors or damage
may exceed the device's limits; the device cannot count all true errors or declare
your backup lost. **Review & Edit** keeps the original entry and lets you make
several changes without jumping to OK after every character. Check the numbered
worksheet boxes and retry, or discard the entry.

### Decide whether you mistyped or the backup needs repair

| Choose the source of the error | Repair instructions remain visible |
| --- | --- |
| ![Where is the error choices](img/screens/error_cause.png) | ![Numbered backup repair pairs](img/screens/repair_backup.png) |

Choose **I Mistyped** if the original backup is readable and agrees with the
proposal. The affected boxes are cleared for you to re-enter from that backup.
Left/right move between affected four-box groups; complete all required boxes
and submit. Re-entry must exactly match the proposal. **Backup Differs** means
the share has not been accepted: check the backup and retry or edit the original.

Choose **Backup Corrupted** when the paper needs repair. Keep the original and
mark the proposed repairs; review every repair page before **Backup Ready**.
Then re-enter the cleared boxes from your repaired backup. This confirms the new
transcription; it cannot independently prove the repair, so the recovered seed
retains **Share repairs unverified.**

| Re-enter from the backup | Cannot verify an unreadable character |
| --- | --- |
| ![Cleared starred re-entry boxes](img/screens/reentry.png) | ![Unverified Characters reconstruction warning](img/screens/unverified.png) |

For `?` characters, **Check Your Backup** asks whether the proposed characters
are readable. If so, re-enter them. If they remain unreadable, **Characters
Unreadable -> Accept Reconstruction** explicitly accepts an unverified
reconstruction. Readable substitutions in a mixed proposal still require
re-entry. Treat independently annotated repairs the same way when verifying the
wallet afterward.

### Large consecutive reconstruction needs extra care

![Thirteen-character Large Recovery warning](img/screens/large_thirteen.png)

A single consecutive run of 9-13 unknown characters has a separate warning.
Thirteen unknowns use all checksum redundancy. Another typo outside that run can
produce a wrong, checksum-valid completion. Check every readable box and use an
independent wallet record. A matching checksum alone cannot verify this case.

## 4. Recover the secret and check the fingerprint

Once `k` compatible shares are accepted, SeedSigner recovers S and shows
**Recovered Seed**. A valid S share can reach this screen directly. Recovery
means combining the shares; correction means repairing their entry. The status
line distinguishes a corrected transcription from unverified share repairs.

![Recovered Seed with the public BIP93 codex32 test vector NAME fingerprint](img/screens/recovered_clean.png)

Choose **Check Fingerprint** and compare with a fingerprint saved **before this
recovery**, on a backup or in your wallet setup records. **Enter Fingerprint**
accepts eight hexadecimal characters and submits the eighth. Each vertical
button or joystick press selects the highlighted character. **Compare Visually**
is available if you prefer to inspect the saved record yourself.

| Choose a comparison method | Optional recorded-fingerprint entry |
| --- | --- |
| ![Check Fingerprint methods](img/screens/check_fingerprint.png) | ![Hexadecimal fingerprint keyboard](img/screens/fingerprint_entry.png) |

| Recorded fingerprint matches | Recorded fingerprint differs |
| --- | --- |
| ![Record Matches with Load Seed](img/screens/record_matches.png) | ![Record Mismatch with recovery review](img/screens/record_mismatch.png) |

A match is a **32-bit accidental-error check**, not wallet authentication.
Check the wallet policy and a known address too. **Record Matches -> Load Seed**
continues loading; **More Options** opens recovery tools. A mismatch offers
**Try Again**, **Review Entered Shares**, or **Return to Fingerprint**; it does
not offer Load Seed on that result screen. Recheck both the entry and your record.

![Matching record with unverified share repairs still visible](img/screens/record_matches_unverified.png)

A match never removes **Share repairs unverified.** Returning to the fingerprint
retains both the repair caveat and the typed/visual comparison status. Copying the
newly calculated fingerprint into the entry field is not verification.

Without a prior record, choose **No Fingerprint Record**. For an existing wallet,
use its coordinator's saved policy and a known address. For first setup, check
the source worksheets and perform a clean recovery; establish the wallet and
record the master fingerprint, policy and a known address. Then power down,
re-enter or scan the shares, and compare a second recovery. Repeating the same
wrong transcription can repeat the same wrong fingerprint, so compare with the
original worksheets as well. A new record cannot independently verify the first
reconstruction.

## 5. Review shares or display S before loading

![Recovery Options menu](img/screens/recovery_options.png)

**More Options** offers **Show Master Seed**, **Review Entered Shares**, and
**Return to Fingerprint**. Top Back also returns to the fingerprint. The
comparison marker applies only to the current recovered seed.

**Review Entered Shares** opens an original transcription, including its original
errors if it had a correction. Editing rebuilds recovery and resets the old
fingerprint check. In this rebuild path, remaining `?` boxes are pending input:
the arrows move between affected groups and OK stays disabled until every `?`
is replaced. Read from an already readable original backup; this path does not
require creating a new paper backup. A truly unreadable backup needs the explicit
reconstruction path and independent wallet checks instead.

**Show Master Seed** warns before displaying the complete S string in two
numbered pages. Top Back from the second page returns to the first, then to the
originating options. It does not force you to finalize. Never photograph a real
secret or scan it into an internet-connected device.

## 6. Load the seed and use your coordinator

Choose **Load Seed**, or **Finalize Seed** after displaying S. At the standard
**Finalize Seed** screen, choose **Done**. The loaded seed offers normal
SeedSigner operations.

![Loaded seed options using the public BIP93 codex32 test vector NAME](img/screens/seed_options.png)

For a watch-only coordinator, export the correct account xpub and verify its
fingerprint, full origin path, network and script type. For multisig, assemble
the complete policy with the other cosigner xpubs and verify a known address.
A Codex32 share QR is seed input for SeedSigner, not an xpub for the coordinator.
See the [single-sig and multisig test walkthroughs](Codex32_Experimental_Build_and_Test.md#export-public-keys-and-create-coordinator-test-wallets)
for Sparrow, Nunchuk and other compatible software. Coordinator funds discovery
alone is not a substitute for checking the intended policy and address.

## 7. Back up the selected string and confirm the copy

![Codex32 backup choices](img/screens/backup_menu.png)

**Backup seed -> View codex32 Secret** displays numbered text.
**Export as codex32 QR** displays a QR for transcription. If retained split
shares are available, **Select Share** lets you choose S or one entered
share. Check that selection: S is the complete secret, while a split share has
its own threshold and index. These options export existing retained metadata;
they do not create a fresh share set.

After text display, **Confirm Backup -> Re-enter Backup** offers exact manual
re-entry. After QR transcription, **Check QR? -> Scan Copied QR** offers a
confirmation scan. Success means
the copied string matched the selected original. It does not establish the
wallet's policy or independently verify an earlier reconstruction.

| Selected string | Confirm the copied QR |
| --- | --- |
| ![Select secret S or entered shares](img/screens/backup_select.png) | ![Confirm Codex32QR prompt](img/screens/qr_confirm_prompt.png) |

Missing or inconsistent metadata can stop export with **Backup unavailable**.
If only split-share metadata is unverifiable, **Backup Warning** explains
that it was omitted and only S will be exported. Keep the original worksheets,
share labels and wallet records; see the [screen reference](Codex32_Screen_Reference.md#codex32-backup-and-qr-export)
for these warning and confirmation variants.
