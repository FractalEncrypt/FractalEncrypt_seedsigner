# Codex32 User Flow Guide (SeedSigner V2)

## 1) Who this guide is for

This guide is for users who are working with Codex32 shares created by hand (worksheet + pencil), and want to safely import, verify, recover, and back up in SeedSigner.

This specifically covers your scenario:

- User has split shares (for example 2-of-N) from worksheets
- User may **not** have completed the extra checksum-validation worksheet yet
- User may not have an `S` share yet

SeedSigner is used to **verify** and recover from hand-calculated shares. Manual entry can offer bounded corrections, which require review and confirmation from the backup. Unreadable characters use a separate reconstruction path. It does not offer a share-creation or checksum-appending command.

---

## 2) Codex32 screens list (user-facing)

## Entry points

1. **Load a Seed** menu
   - `Enter Codex32 Seed`
   - `Scan Codex32 Share`

Compatibility note:

- The generic camera entry path (including `Scan SeedQR`) can ingest codex32 shares.
- When a codex32 payload is detected, SeedSigner routes into codex32 validation/collection flow instead of treating it as a BIP39 SeedQR payload.

## Core Codex32 entry/recovery flow

2. `Codex32EntryView` (manual character entry in numbered boxes)
3. `ScanCodex32ShareView` (camera scan for Codex32 share)
4. `Codex32ShareInvalidView` (invalid header/data/length/checksum, or share-set mismatch)
5. `Codex32ShareConflictConfirmView` (same index, different share)
6. `Codex32ShareSuccessView` (share accepted, continue flow)
7. `Codex32DiscardAllSharesConfirmView`
8. `Codex32ShareEntryMethodView` (choose enter vs scan after discard)
9. `Codex32MasterShareSuccessView` (threshold reached, `S` recovered or validated)
10. `Codex32MasterSecretWarningView`
11. `Codex32MasterSecretDisplayView` (Boxes 1-24, then 25-48)

Correction entry may additionally use `Codex32CorrectionReviewView`,
`Codex32CorrectionDetailsView`, `Codex32CorrectionCauseView`, `Codex32BackupRepairView`,
`Codex32CorrectionEntryView`, `Codex32CorrectionMismatchView`,
`Codex32CorrectionProofView`, `Codex32ReconstructionAcceptView`, and
`Codex32LargeRecoveryWarningView`. After recovery, `Codex32RecoveryReviewView`
lets the user revisit entered shares while comparing the recovered fingerprint.
The recovered-seed screen offers **Check Fingerprint**, **Load Seed**, and
**More Options**. A fingerprint check supports optional eight-character entry,
visual comparison, or guidance without a previously recorded fingerprint.
**More Options** holds master-seed display and entered-share review. A match
is an accidental-error check; it does not remove correction history.

## Backup/export after seed is loaded

12. `SeedBackupView` (Codex32 options appear for Codex32Seed)
13. `Codex32BackupShareSelectView` (choose `S` or split share for QR export or manual display)
14. `Codex32BackupUnavailableView` (if export metadata is missing/invalid/inconsistent)
15. `Codex32BackupMetadataWarningView` (warns when inconsistent split-share metadata is omitted and flow continues with `S`-only)
16. `SeedTranscribeSeedQRWarningView` (Codex32QR warning path)
17. `SeedTranscribeSeedQRWholeQRView`
18. `SeedTranscribeSeedQRZoomedInView`
19. `SeedTranscribeSeedQRConfirmQRPromptView` (Confirm Codex32QR)
20. `SeedTranscribeSeedQRConfirmScanView`
21. `SeedTranscribeSeedQRConfirmWrongSeedView`
22. `SeedTranscribeSeedQRConfirmInvalidQRView`
23. `SeedTranscribeSeedQRConfirmSuccessView`

---

## 3) End-to-end flow: paper shares -> recovered secret -> loaded seed

## Phase A: Prepare from worksheets / printable cards

1. From your worksheet, copy each share exactly as written.
2. If needed, pre-stage each share on printable cards so manual entry is easier:
   - [`printable_templates/Seedsigner_Codex32_Printable_Page_SeedCards.pdf`](printable_templates/Seedsigner_Codex32_Printable_Page_SeedCards.pdf)
   - Box numbering matches worksheet/SeedSigner box numbering.
3. If you have not done worksheet checksum verification yet, continue anyway: SeedSigner can verify by validating the full share string during entry.
   - If verification fails in the seedsigner of a share that you've not verified manually, then you'll need to go back to the worksheet and recompute the share.

## Phase B: Start import in SeedSigner

Choose either:

1. `Load a Seed -> Enter Codex32 Seed` (manual first share), or
2. `Load a Seed -> Scan Codex32 Share` (scanned first share).

Both routes converge to Codex32 share validation + collection.

## Phase C: Share validation behavior (important trust model)

When a share is submitted, SeedSigner validates:

- format/header (`MS1`, threshold/index structure)
- length
- data/checksum

If invalid -> `Codex32ShareInvalidView`

If the share header doesn’t match the current share set (threshold/identifier),
the error explicitly calls out the **share-set mismatch** (rather than just a
generic “invalid header”).

When a correction is available, user choices there are **View Correction**,
**Review & Edit**, and **Discard Invalid Share**. The correction is displayed
with numbered, highlighted boxes, followed by pages of `entered → proposed`
pairs. The user distinguishes a typing mistake from a backup needing repair;
readable changed characters must then be re-entered into cleared boxes from the
backup. Annotated repairs remain unverified until independently checked. See
[error correction and verification](Codex32_Error_Correction.md) for unreadable
characters, large-recovery warnings, and fingerprint comparison.

Otherwise, user choices there are:

1. **Review & edit** (fix the entered characters)
2. **Discard invalid share** (choose whether to **enter or scan** the next share)
3. **Discard all shares**

Suggestions are not accepted automatically. When a worksheet's own calculation
is uncertain, verify it using the worksheet process; a checksum-valid completion
does not prove the intended seed.

## Phase D: Build up to threshold `k`

After each valid share, `Codex32ShareSuccessView` offers:

1. **Enter next share** (manual)
2. **Scan next share**
3. **Discard**

So users can alternate manual + scan for each subsequent share.

The success screen **preselects** Enter vs Scan based on how the last share was
entered (smoothly continuing the user’s preferred entry method).

### Duplicate index conflict path

If a new share uses an already-entered index but different content:

- `Codex32ShareConflictConfirmView`
- User chooses either:
  1. **Replace existing share**, or
  2. **Keep existing share** and continue

## Phase E: Threshold reached

Once `k` valid compatible shares are present, SeedSigner recovers/validates `S` and routes to:

- `Codex32MasterShareSuccessView`

User can then:

1. **Show Codex32 Key** -> warning -> two-page master display (boxes 1-24 then 25-48)
2. **Load seed** -> continue to finalize and load into SeedSigner

---

## 4) Path for users who already have an `S` share

If user enters/scans a valid `S` share directly:

- Seed can be loaded without split-share collection
- User still gets the master-share success and display/load options

---

## 5) After loading: what user can do

After `Finalize`, user lands in `SeedOptionsView` and can use the seed like any other loaded seed:

1. Scan/sign PSBTs
2. Export xpub
3. Address explorer
4. Sign message
5. Backup seed

For Codex32 backups specifically:

- `Backup seed -> View Codex32 Secret` (display in numbered boxes)
  - If multiple shares are available, `Codex32BackupShareSelectView` lets the user choose
    which share to display (S share or split share).
- `Backup seed -> Export as Codex32QR`
  - If multiple shares available, `Codex32BackupShareSelectView` lets user choose which share QR to transcribe/export.
  - `SeedTranscribeSeedQR*` screens are shared UI components; in this path they carry codex32QR payloads (not numeric SeedQR payloads).

---

## 6) Printable cards workflow recommendations

Practical operator workflow:

1. Keep worksheet as source of truth.
2. Copy share to printable card (temporary transport layer).
3. Enter/scan into SeedSigner for validation.
4. If invalid, return to worksheet process and recompute/rewrite (do not trust ad-hoc edits).
5. After recovery, back up `S` and required split shares onto durable media (e.g., metal), using printable cards only as staging.

---

## 7) Quick flow map

1. Prepare handwritten share(s) -> optional printable card staging
2. Load Seed -> Enter or Scan Codex32
3. Invalid? -> fix/re-enter (or discard)
4. Valid -> success screen -> enter/scan next share
5. Repeat until `k` valid shares
6. Recovered seed -> optional recorded-fingerprint check -> load seed (More Options: display master seed or review entered shares)
7. Finalize seed
8. Use seed for normal SeedSigner operations
9. Backup via Codex32 secret display and/or Codex32QR export + confirmation scan
