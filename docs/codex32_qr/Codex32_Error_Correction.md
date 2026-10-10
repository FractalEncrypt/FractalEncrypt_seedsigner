# Codex32 error correction

SeedSigner offers correction suggestions for manual entry of 48-character
codex32 shares. The entry retains the numbered boxes used on the backup cards
and official worksheets. Compare those positions when checking a shifted entry.

The fixed decoder supports up to four substituted characters, eight unreadable
characters marked `?`, or mixtures satisfying `2 * substitutions + erasures <= 8`.
A swap of two different characters counts as two substitutions. It does not
search for inserted/deleted characters or misplaced four-character groups.
`MS1` stays locked; subsequent shares retain the confirmed threshold/identifier.

When a manual entry has no accepted proposal, **No Correction Found** shows a
large red X and explains: "Errors or damage may exceed device limits. Review
numbered backup boxes." **Review & Edit** preserves that entry for another check
against the numbered backup. Editing a box keeps the keyboard ready for the next
change; it does not automatically select OK after each character. The user can
explicitly select OK to retry validation, including with remaining unknowns.
Ordinary initial entry still treats `?` as occupied so it can request correction.
If no proposal can be accepted, the same warning appears; the share never enters
the collection.
The decoder cannot determine the true error count or declare the backup lost.
QR validation and share-set mismatches retain their specific error messages.
A checksum-valid threshold-0 input with an index other than S gets a specific
**Invalid Share Header** warning pointing to boxes 4 and 9. A threshold typo
with an invalid checksum still uses correction.

## Reviewing a transcription correction

An invalid entry with a supported repair offers **View Correction** alongside
**Review & Edit**. Viewing the correction shows all 48 characters in two pages;
asterisks and highlighting identify the proposed replacements.

**Review Each Change** then lists the numbered `entered → proposed` pairs,
up to four changes per page. All changed positions are shown before continuing;
each page asks the user to compare with their backup while the pairs remain
visible. The last page offers **Continue**. Back revisits the previous changes
page or the full numbered overview.

After review, **I Mistyped** uses the existing readable backup for confirmation.
**Backup Corrupted** reopens the correction pairs as repair pages, up to three
changes per page, with instructions to preserve the original and annotate the
repairs. **Backup Ready** appears on the last page, with the corrections still
visible, then opens the usual four-box entry screen. **Review Corrections** on
the cause screen returns to the comparison pages. This path remains unverified
after re-entry: copying a proposal onto paper
and typing it back is not an independent check. Verify against a trusted wallet
record after recovery before treating the annotation as a confirmed repair.

Check the numbered positions against the original backup. The changed boxes
are then cleared for re-entry. Read their values from the backup, rather than
copying the proposal from memory. All other boxes are locked. Completing an
affected four-box group selects the right arrow; pressing it advances directly
to the next affected group. The left arrow returns to the previous affected
group, including completed corrections, skipping unchanged groups. When all
affected boxes are filled, OK is selected.
Exact equality
with the proposal is required; proof input is never automatically corrected.
A mismatch does not accept the share. Back returns to the original entry.

This deliberate re-entry is a SeedSigner confirmation choice. BIP93 recommends
confirmation before proceeding with a corrected string, without prescribing
this specific interaction.

## Unreadable characters and large recovery

Enter `?` in the numbered box for an unreadable character. It occupies that box
but remains invalid for normal parsing. The first use shows an inline explanation.

If proposed characters can be read from the backup, re-enter them. If they truly
cannot be read, select **Characters Unreadable** and explicitly accept an
unverified reconstruction. Any additional substitutions still require re-entry.

Nine through thirteen consecutive erasures have a separate warning before the
proposal is displayed. This path assumes every other entered character is
correct. Thirteen erasures consume all checksum redundancy: another typo can
produce a different valid share and the wrong seed. Checksum validity and a
unique proposal do not prove which backup the user intended.

The ordinary correction bound is also conditional on the actual damage being
within that bound. The device cannot measure the true distance from an unknown
original. It therefore always treats correction output as an untrusted proposal.

## Verifying recovery

Once an S share or the required `k` compatible shares are accepted, the recovery
screen displays the master fingerprint immediately, in lowercase. Its three
buttons are **Check Fingerprint**, **Load Seed**, and **More Options**.
**Check Fingerprint** asks whether there is a trusted record from before this
recovery, with **Enter Fingerprint**, **Compare Visually**, and
**No Fingerprint Record** paths. Entry uses eight hexadecimal characters and
compares case-insensitively. Backspace edits before the eighth character; the
eighth submits. **Try Again** returns to the check choices if the record differs.
A mismatch displays both values and offers **Review Entered Shares**.

**Recovered Seed** describes obtaining S from a valid S input or compatible
shares. It does not imply that character correction occurred. The header stays
the same for all recoveries. A separate line says "Share entry corrected." for a
confirmed transcription correction, or "Share repairs unverified." for repaired
or unreadable characters. That line remains visible alongside any fingerprint
check result; a match never replaces the repair caveat.

"Compare saved fingerprint" means compare all eight displayed characters with a
fingerprint saved on the backup or wallet setup notes before this recovery.
A typed match is labeled "Saved fingerprint matches." A visual confirmation
is labeled "Compared visually." Both leave correction provenance
intact; neither authenticates the wallet or verifies a repaired paper character.
The check is optional: **Load Seed** remains available, including without a record.
The no-record screen explains existing-wallet verification through a known
address and policy, and first-setup checks against the source worksheets.
Comparison markers are transient navigation state, are bound to the recovered
fingerprint, and reset when share editing creates a new recovery. Canceling the
check menu, keyboard or visual comparison preserves the previous marker; a new
mismatch or an explicit no-record choice clears it. They are never
saved to disk or included in exports.

After a typed or visual fingerprint match, **Record Matches** offers **Load Seed**
and **More Options**. **Load Seed** continues to the usual seed-finalization screen.
A match is a 32-bit error check; the wallet-policy and known-address reminder stays
visible. **More Options** preserves the comparison and correction provenance.

**More Options** holds **Show Master Seed**, **Review Entered Shares**, and
**Return to Fingerprint**. **Review Entered Shares** returns to the
original entry for a corrected share, or to the accepted text for a clean share.
Other retained entered shares are preserved for rechecking the recovery.
When the original corrected entry contains `?`, this recovery-review path treats
those boxes as pending input. It starts at the first unresolved box, keeps OK
disabled until every unknown is replaced, and uses the arrows to visit affected
four-box groups. Completing a group selects the next-page arrow when another
unresolved group remains; the next page starts at its first unresolved box.
The previous arrow permits revisiting earlier affected groups. Normal page
navigation resumes after the rebuild is complete. The final replacement repaints
OK immediately with the standard orange fill; removing a required character
disables it again. The `?` key is unavailable
in this clean rebuild; ordinary initial entry still permits unknown characters.
This path replaces a reconstruction with a fresh transcription from a readable
original backup; it does not require creating a new paper backup. A clean
replacement clears that share's correction record and starts a fresh fingerprint
comparison. A truly unreadable backup needs the explicit reconstruction flow
and independent wallet checks instead of this clean re-entry path.

Both master-seed display pages have a top Back control. Back from boxes 25-48
returns to boxes 1-24; Back again returns to the originating options screen
without finalizing the seed. Fingerprint entry accepts joystick press and all
three side buttons as key selection. Other generalized keyboards retain their
existing save-button behavior. Fingerprint results use the standard large green
success or red error icon; unverified repair guidance remains visible even with
a match.

The correction indicator and reviews cover retained shares. Below-threshold or
inconsistent split shares omitted by the existing export policy do not contribute
to the accepted S seed, and their correction records are omitted too; the separate
backup-metadata warning still reports those omissions.

Compare the full eight hexadecimal characters with a trusted fingerprint recorded
when the wallet was established. A mismatch means the recovered wallet differs
from the record: check the shares and the record before using the seed. A match
is a useful accidental-error check, not authentication; BIP32 fingerprints are
32-bit identifiers and can collide. They also do not verify header/padding bits
that do not change the decoded seed.

For a new manually generated backup there is no previously recorded fingerprint.
Start with the book's debiased dice and worksheet method, verify its checksums,
and perform a clean recovery without unverified reconstruction. Establish the
wallet, record its master fingerprint and wallet policy, then power down and
re-enter or scan the shares to compare a second recovery. Record a known receive
address or public descriptor for an additional wallet check. Repeating the same
wrong inputs can repeat the same wrong fingerprint, so check against the source
worksheets too.

Keep sufficient policy information to reconstruct the intended wallet, including
network, derivation/account information, script type, and, for multisig, threshold,
cosigner public keys and key ordering (prefer a public wallet descriptor). The
single/multisig and script-type checkboxes alone are not a complete multisig backup.
A watch-only coordinator can verify the expected addresses/policy without receiving
the seed. An empty balance alone does not establish that recovery is wrong.

Recording a fingerprint has a privacy/security tradeoff. It does not provide an
efficient way to invert a strong random seed, but it supplies a 32-bit filter for
candidate seeds and links backups to the same wallet. With a split share it adds
seed-dependent information beyond the share alone. An attacker with a candidate
space of uniformly random 128-bit seeds expects roughly `2^96` candidates to match
one 32-bit fingerprint, but finding a matching candidate does not recover the
wallet or make an exhaustive search cheap. Low-entropy seeds are more exposed to
candidate testing. Users can keep the verification record separately when metadata
privacy matters. The card field should say **Master fingerprint (recovered S)**,
so it is not confused with the share identifier or an individual share.

Appending checksums and creating shares are outside this feature. Backup
transcription confirmation continues to require an exact match without correction.
Invalid QR payloads remain fail-closed; QR-level recovery is a separate mechanism.

## Pi Zero 1.3 validation

Run the public-data benchmark on the actual Pi firmware/runtime:

```sh
python3 tools/benchmark_codex32_correction.py --iterations 1000
```

It measures module import, first-call and repeated fixed-decoder timings, including
failure cases. It accepts no seed input, makes no network requests, and prints only
timings/device metadata. A UVC camera connection alone does not expose a shell;
running this requires an existing shell/console or a test firmware session. No Pi
timing guarantee is inferred from desktop measurements.

From the repository root in Windows PowerShell, use the existing virtual
environment (activation and WSL are unnecessary):

```powershell
.\.venv\Scripts\python.exe tools/benchmark_codex32_correction.py --iterations 1000
```

An `embit` import error means the selected Python environment lacks the project's
dependency, not that the working directory is wrong. Desktop results measure the
desktop; the USB UVC camera connection does not execute this benchmark on the Pi.

## Vendoring and validation

The arithmetic in `models/codex32_correction.py` comes from
`benwestgate/python-codex32` revision
`f19d4627c5725a9f6cfa995a1f89fe62e1becb4c`, derived from correction PR #70.
Its license/copyright notice is retained in the module. Only the short-checksum
fixed decoder is included; structural search, other profiles, generation CRC
hints and wallet code are excluded. It runs with Python 3.10-compatible syntax.
All surviving proposals are reparsed by SeedSigner's strict existing parser.
Transient original/corrected text stays in memory; correction records are not
added to exported shares or QR payloads. Python strings cannot be reliably scrubbed.

Tests cover published/frozen vectors, all ordinary error/erasure distributions,
consecutive bursts, immutable headers, confirmation rejection, mixed unreadable
recovery, and fingerprint review. The vendored test corpus is the 48-character
subset of upstream's frozen PR #70 corpus.

References: [BIP93](https://github.com/bitcoin/bips/blob/master/bip-0093.mediawiki),
[BIP32](https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki).
