"""Render the Codex32 documentation from real Views using public BIP93 data.

Run from the repository: python tools/render_codex32_screen_reference.py
Requires the repository's development/test dependencies. Hardware, camera and
release lookup are mocked; no seed input or private device evidence is accepted.
"""
import argparse
import os
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))
# Isolate settings before GUI imports: never read or write an operator's settings.
from seedsigner.models.settings import Settings
_settings_workspace = tempfile.TemporaryDirectory(prefix="codex32-reference-")
Settings.SETTINGS_FILENAME = str(Path(_settings_workspace.name) / "settings.json")

# Reuse the maintained screenshot generator's hardware stubs and capture renderer.
# Its unrelated release-splash lookup is disabled for this offline renderer.
from seedsigner.helpers.version import VersionUtils
with patch.object(VersionUtils, "_fetch_latest_seedsigner_release_tag", return_value=(None, None)):
    from screenshot_generator import generator as _generator
from screenshot_generator.utils import ScreenshotComplete, ScreenshotRenderer
from seedsigner.views import codex32_views as ec, seed_views as sv, scan_views
from seedsigner.models import codex32 as model
from seedsigner.models.codex32_correction import suggest_correction
from seedsigner.models.seed import Codex32Seed
from seedsigner.models.seed_storage import SeedStorage
from seedsigner.models.settings import Settings
from seedsigner.models.settings_definition import SettingsConstants as SC
from seedsigner.gui.renderer import Renderer
from seedsigner.controller import Controller
from seedsigner.views.view import View
from seedsigner.gui.components import TextArea, Fonts, GUIConstants
from seedsigner.models.qr_type import QRType
from PIL import ImageFont

A = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"
C = "MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN"
S = "MS12NAMES6XQGUZTTXKEQNJSJZV4JV3NZ5K3KWGSPHUH6EVW"
SHARES = {"s": S, "a": A, "c": C}
SOURCES = {"s": "derived", "a": "entered", "c": "entered"}
SEED = Codex32Seed(model.codex32_to_seed_bytes(S), codex32_master_share=S,
                   codex32_export_shares=SHARES, codex32_share_sources=SOURCES)
if SEED.get_fingerprint(SC.TESTNET).lower() != "fab6868a":
    raise RuntimeError("Unexpected public NAME fingerprint")

def flow(indices, erasures=False):
    damaged = list(A)
    for index in indices:
        damaged[index] = "?" if erasures else ("Q" if damaged[index] != "Q" else "P")
    proposal = suggest_correction("".join(damaged))
    if proposal is None or proposal.corrected != A:
        raise RuntimeError("Public correction fixture failed")
    return ec.CorrectionFlow(proposal)

TYPOS = flow((12, 17, 24, 40))
UNKNOWN = flow((17,), True)
EIGHT = flow((9, 12, 17, 21, 25, 31, 36, 43), True)
NINE = flow(range(12, 21), True)
THIRTEEN = flow(range(12, 25), True)
CORRECTED = {"a": (TYPOS.proposal, False)}
UNVERIFIED = {"a": (UNKNOWN.proposal, True)}
COLLECTION = model.Codex32ShareCollection.from_first_share(model.parse_codex32_share(A))
# A valid, deliberately different same-index share, not an identical-repeat fixture.
from seedsigner.models.codex32_min import ms32_encode
conflict_values = model.parse_codex32_share(A).data_part_values
conflict_values[6] = (conflict_values[6] + 1) % 32
CONFLICT = ms32_encode(conflict_values).upper()
CONFLICT_ARGS = dict(share_num=2, prefill="MS12NAME", share_data=CONFLICT, share_collection=COLLECTION)
CASES = []
def add(section, filename, title, text, cls, **args):
    CASES.append(dict(section=section, filename=filename, title=title, text=text,
                      cls=cls, args=args))

add("Import and share collection", "load_seed", "Load a Seed", "Choose Enter codex32 Seed for numbered entry, or Scan codex32 Share for the camera. Scroll to see lower menu items.", sv.LoadSeedView)
add("Import and share collection", "entry_first", "First share entry", "Enter exactly 48 characters in numbered four-box groups. MS1 is locked; ? marks an unreadable character. Any of the three side buttons selects a keyboard character.", sv.Codex32EntryView)
add("Import and share collection", "entry_unknown", "An unreadable box", "Use ? only when a backup character cannot be read. It fills the box for entry, but cannot pass normal validation. A supported completion still needs review.", sv.Codex32EntryView, share_data=UNKNOWN.proposal.original, start_page=4)
add("Import and share collection", "scan_share", "Scan a share", "Scan one Codex32 share QR. This illustration uses the generator's camera placeholder. Invalid scans use strict validation; correction proposals are a manual-entry feature.", scan_views.ScanCodex32ShareView, share_num=1)
add("Import and share collection", "share_accepted", "Share accepted", "One compatible NAME share has been accepted. Recovery needs two. Enter or scan the next share; Discard opens the discard confirmation.", sv.Codex32ShareSuccessView, entered_shares=1, total_shares=2, share_collection=COLLECTION, prefill="MS12NAME")
add("Import and share collection", "entry_next", "Next share entry", "MS1 plus the established threshold and identifier are locked for subsequent shares. The share index is the next editable position; enter a different index from the same set.", sv.Codex32EntryView, share_num=2, prefill="MS12NAME", share_collection=COLLECTION)
add("Import and share collection", "duplicate_share", "Share Already Added", "This exact share is already saved. It adds no share toward recovery. Scan New Share opens the camera; Discard This Entry keeps the saved shares and lets you choose how to enter a different share.", sv.Codex32ShareAlreadyAddedView, share_collection=COLLECTION, share_idx="a")
add("Import and share collection", "share_conflict", "Share Conflict", "Two checksum-valid strings use the same index but differ. Neither checksum identifies the correct backup. Compare Shares shows numbered differences. Check the original backup or an independent trusted record before choosing Keep Saved Share or Use New Share. If unsure, leave the saved share in place and investigate; do not guess.", sv.Codex32ShareConflictConfirmView, **CONFLICT_ARGS)
for page in range(4):
    add("Import and share collection", f"conflict_compare_{page+1}", f"Compare Shares: page {page+1}", "Saved → New lists differing box values. Next Differences advances; Back returns one page or to the choice screen. Choose Share returns to the choices without accepting either copy.", sv.Codex32ShareConflictReviewView, page_index=page, **CONFLICT_ARGS)
add("Import and share collection", "discard_all", "Discard all shares", "Continue discards the collected shares. Cancel keeps the collection. This confirmation also appears when backing out of an accepted-share screen.", sv.Codex32DiscardAllSharesConfirmView, share_collection=COLLECTION)
add("Import and share collection", "next_method", "Next share", "After discarding an invalid entry, choose manual entry or scanning while keeping any valid shares still in the collection.", sv.Codex32ShareEntryMethodView, share_num=2, prefill="MS12NAME", share_collection=COLLECTION)

add("Invalid entries", "correction_available", "Correction available", "A manual entry failed validation and a bounded proposal is available. View Correction starts review; Review & Edit keeps your original entry. The proposal has not been accepted.", sv.Codex32ShareInvalidView, share_data=TYPOS.proposal.original, correction_flow=TYPOS)
add("Invalid entries", "no_correction", "No Correction Found", "No supported proposal was found. Errors or damage may exceed this device's limits; the true error count is unknown. Review numbered backup boxes, discard this entry, or discard the collection.", sv.Codex32ShareInvalidView, correction_attempted=True, share_data=A[:12]+"?"*16+A[28:])
add("Invalid entries", "invalid_scan", "Invalid share", "A scanned share failed its checksum. Recheck the QR and backup. Manual correction availability is not implied by this scan error.", sv.Codex32ShareInvalidView, entry_method="scan")
add("Invalid entries", "header_mismatch", "Share set mismatch", "The scanned threshold or identifier differs from the current set. Use shares from one matching set; do not change a header merely to make it fit.", sv.Codex32ShareInvalidView, error_type=model.ERROR_HEADER, error_detail="Share header mismatch", share_collection=COLLECTION, entry_method="scan")
add("Invalid entries", "threshold_zero", "Invalid Share Header", "Threshold 0 requires the secret index S. Check boxes 4 and 9. This specific message is used for the valid-checksum structural error.", sv.Codex32ShareInvalidView, error_type=model.ERROR_HEADER, error_detail="Codex32 share index must be 's' when threshold is 0")

for page in (0, 1):
    add("Correction review and backup confirmation", f"correction_boxes_{page+1}", f"Review Correction: boxes {page*24+1}-{page*24+24}", "Proposed characters appear in numbered boxes. Yellow boxes and * labels identify changes. Compare them with the original backup before continuing; the next stage shows entered-to-proposed pairs.", ec.Codex32CorrectionReviewView, flow=TYPOS, page_index=page)
add("Correction review and backup confirmation", "change_pairs", "Review Changes", "Each line shows the box number and entered -> proposed character. Compare every pair with the backup before Continue. Up to four changes appear per page.", ec.Codex32CorrectionDetailsView, flow=TYPOS)
add("Correction review and backup confirmation", "change_pairs_next", "More changes", "For larger proposals, Next Changes advances through all affected boxes. Back returns to the previous group; Continue appears only on the last group.", ec.Codex32CorrectionDetailsView, flow=EIGHT, page_index=1)
add("Correction review and backup confirmation", "error_cause", "Where is the error?", "Choose I Mistyped when the original backup is readable and agrees with the proposal. Choose Backup Corrupted if the paper needs repair. Review Corrections returns to the comparison pairs.", ec.Codex32CorrectionCauseView, flow=TYPOS)
add("Correction review and backup confirmation", "repair_backup", "Repair Backup", "Keep the original backup and mark the proposed repairs. Next Repairs shows remaining pairs. Readable repaired characters must be re-entered; repaired paper still requires independent wallet verification.", ec.Codex32BackupRepairView, flow=TYPOS)
add("Correction review and backup confirmation", "repair_backup_last", "Backup Ready", "After all repair pairs have been reviewed, Backup Ready opens the cleared correction boxes. Re-enter from the repaired backup; accepting that transcription does not independently verify the repair.", ec.Codex32BackupRepairView, flow=TYPOS, page_index=1)
add("Correction review and backup confirmation", "repair_unreadable", "Characters Unreadable", "If proposed ? replacements cannot be checked on the original backup, Characters Unreadable opens the reconstruction warning. Do not describe an unreadable replacement as verified from paper.", ec.Codex32BackupRepairView, flow=UNKNOWN)
add("Correction review and backup confirmation", "check_backup", "Check Your Backup", "After an entry containing ?, decide whether the proposed characters are now readable. Re-enter from Backup proves that transcription; Characters Unreadable takes the explicit reconstruction path.", ec.Codex32CorrectionProofView, flow=UNKNOWN)
add("Correction review and backup confirmation", "reentry", "Re-enter changed boxes", "Only affected boxes are cleared. Read the * boxes from your backup. Left/right arrows navigate affected groups; OK is selected when all required characters are entered. A re-entry must match the proposal exactly.", ec.Codex32CorrectionEntryView, flow=TYPOS)
add("Correction review and backup confirmation", "backup_differs", "Backup Differs", "The re-entered characters do not match the proposal, so the share has not been accepted. Re-enter Again retries the proof; Review & Edit Original returns to your initial transcription.", ec.Codex32CorrectionMismatchView, flow=TYPOS)
add("Correction review and backup confirmation", "unverified", "Unverified Characters", "Accept Reconstruction explicitly accepts characters you cannot compare with the backup. Their unverified status remains visible during fingerprint checking. A trusted prior record and wallet checks are needed.", ec.Codex32ReconstructionAcceptView, flow=UNKNOWN)
add("Correction review and backup confirmation", "large_nine", "Large Recovery: 9 to 12 unknowns", "Supported consecutive unknowns beyond eight leave reduced checksum evidence. Another typo outside the burst can give a wrong but valid proposal. Check readable boxes and independently verify the wallet.", ec.Codex32LargeRecoveryWarningView, flow=NINE)
add("Correction review and backup confirmation", "large_thirteen", "Large Recovery: 13 unknowns", "Thirteen consecutive unknowns use all checksum redundancy. A valid completion does not verify the readable remainder. Review Reconstruction continues to the proposal; Review & Edit returns to the original entry.", ec.Codex32LargeRecoveryWarningView, flow=THIRTEEN)

add("Recovered seed and fingerprint checks", "recovered_clean", "Recovered Seed", "After k compatible shares, or a direct S share, the seed fingerprint is available. Recovery means combining shares; it does not mean an error was corrected. Check a previously saved fingerprint, Load Seed, or open More Options.", sv.Codex32MasterShareSuccessView)
add("Recovered seed and fingerprint checks", "recovered_corrected", "Share entry corrected", "Readable transcription errors were corrected and re-entered. The screen records that an entry was corrected; compare the fingerprint with a trusted prior record.", sv.Codex32MasterShareSuccessView, corrections=CORRECTED)
add("Recovered seed and fingerprint checks", "recovered_unverified", "Share repairs unverified", "One or more accepted repairs or unreadable characters lack independent verification. The yellow caveat remains separate from fingerprint-check status.", sv.Codex32MasterShareSuccessView, corrections=UNVERIFIED)
add("Recovered seed and fingerprint checks", "check_fingerprint", "Check Fingerprint", "Use a fingerprint saved before this recovery on a backup or wallet setup record. Enter Fingerprint checks eight hexadecimal characters; Compare Visually is optional; No Fingerprint Record explains next steps.", ec.Codex32FingerprintCheckView)
add("Recovered seed and fingerprint checks", "fingerprint_entry", "Enter Fingerprint", "Enter the eight characters from your existing record. All three side buttons select keys. The eighth character submits; Back cancels. Do not copy the new on-screen fingerprint and treat that as verification.", ec.Codex32FingerprintEntryView)
add("Recovered seed and fingerprint checks", "fingerprint_visual", "Compare visually", "Compare fab6868a with your existing record. Matches My Record or Does Not Match records your visual assessment. Optional typed entry avoids misreading similar characters.", ec.Codex32FingerprintVisualView)
add("Recovered seed and fingerprint checks", "record_matches", "Record Matches", "The saved fingerprint matches. Load Seed continues to normal finalization; More Options opens recovery tools. A 32-bit match checks accidental errors and must be followed by wallet-policy and known-address verification.", ec.Codex32FingerprintResultView, recorded_fingerprint="fab6868a")
add("Recovered seed and fingerprint checks", "record_matches_unverified", "A match with unverified repairs", "The green check means the recorded fingerprint matched. The yellow Share repairs unverified caveat remains: the match does not prove every repair or authenticate the wallet.", ec.Codex32FingerprintResultView, recorded_fingerprint="fab6868a", corrections=UNVERIFIED)
add("Recovered seed and fingerprint checks", "record_visual_match", "Visual match result", "A confirmed visual comparison uses the same match screen and loading choices. It is your comparison with a prior record, rather than a typed equality check.", ec.Codex32FingerprintResultView, visual_match=True)
add("Recovered seed and fingerprint checks", "record_mismatch", "Record Mismatch", "The entered record differs from this recovered seed. Try Again checks the record entry; Review Entered Shares reopens the originals. This result does not offer Load Seed.", ec.Codex32FingerprintResultView, recorded_fingerprint="00000000")
add("Recovered seed and fingerprint checks", "visual_mismatch", "Visual mismatch result", "Does Not Match leads to the same recovery-review choices, with a message to check your record and shares.", ec.Codex32FingerprintResultView, visual_match=False)
add("Recovered seed and fingerprint checks", "no_record", "Without a Record", "For an existing wallet, compare policy and a known address in the coordinator. For first setup, check worksheets, record the fingerprint, then restart and repeat recovery. A newly written record cannot verify this first reconstruction.", ec.Codex32FingerprintNoRecordView)
add("Recovered seed and fingerprint checks", "recovered_checked", "Return after a match", "After a typed match, Saved fingerprint matches appears alongside Share repairs unverified. Returning through More Options must preserve both independent facts.", sv.Codex32MasterShareSuccessView, corrections=UNVERIFIED, fingerprint_check=("entered", "fab6868a"))
add("Recovered seed and fingerprint checks", "recovered_visual_checked", "Return after visual comparison", "Compared visually records the visual path. The repair caveat remains when present; it is not replaced by comparison status.", sv.Codex32MasterShareSuccessView, corrections=UNVERIFIED, fingerprint_check=("visual", "fab6868a"))
add("Recovery options and seed loading", "recovery_options", "Recovery Options", "More Options holds Show Master Seed, Review Entered Shares, and Return to Fingerprint. Back also returns to the fingerprint without discarding the current comparison marker.", sv.Codex32MasterShareSuccessView, show_options=True, corrections=UNVERIFIED, fingerprint_check=("entered", "fab6868a"))
add("Recovery options and seed loading", "review_shares", "Review Entered Shares", "Choose an originally entered share, including its original damaged transcription if available. Editing rebuilds recovery and resets the previous fingerprint comparison; other compatible shares are retained where applicable.", ec.Codex32RecoveryReviewView, corrections=UNVERIFIED)
add("Recovery options and seed loading", "rebuild_unknowns", "Rebuild unreadable entry", "Reviewing a share with ? reopens numbered entry at the unresolved boxes. Left/right navigate remaining unknowns. Replace every ? before OK; these boxes are edits to the original entry, not proof that a backup repair was verified.", sv.Codex32EntryView, share_data=EIGHT.proposal.original, prefill="MS1", resolve_unknowns=True)
add("Recovery options and seed loading", "master_warning", "Master seed warning", "Show Master Seed exposes the complete secret S. Protect a real secret from cameras and connected devices. This guide displays public test data only.", sv.Codex32MasterSecretWarningView, share_data=S)
for page in (0, 1):
    add("Recovery options and seed loading", f"master_boxes_{page+1}", f"Secret S: boxes {page*24+1}-{page*24+24}", "The complete S string appears over two numbered pages. Top Back returns without forcing finalization. After the second page, Finalize Seed continues loading; a loaded-seed backup uses Confirm Backup instead.", sv.Codex32MasterSecretDisplayView, share_data=S, page_index=page)
add("Recovery options and seed loading", "finalize", "Finalize Seed", "Load Seed, or Finalize Seed after display, reaches SeedSigner's standard finalization screen. Confirm the seed to proceed to its normal operations.", sv.SeedFinalizeView)
add("Recovery options and seed loading", "seed_options", "Loaded seed", "The loaded public NAME seed offers normal SeedSigner operations: export xpubs, address checks, signing and backup. Coordinator setup is explained in the experimental build and test guide.", sv.SeedOptionsView, seed=SEED)

add("Codex32 backup and QR export", "backup_menu", "Backup Seed", "For a Codex32 seed, choose View Codex32 Secret or Export as Codex32QR. These export the retained S/share metadata; they do not create new split shares.", sv.SeedBackupView, seed=SEED)
add("Codex32 backup and QR export", "backup_select", "Select Share", "Choose the derived secret S or an entered split share. S reveals the complete seed; a split share is not interchangeable with it. This menu is shared by display and QR export.", sv.Codex32BackupShareSelectView, seed=SEED, share_map=SHARES, source_map=SOURCES)
add("Codex32 backup and QR export", "backup_unavailable", "Backup unavailable", "Missing, invalid or inconsistent secret metadata prevents backup export. Re-import the original Codex32 secret to restore metadata; do not infer a new backup string from this warning.", sv.Codex32BackupUnavailableView)
add("Codex32 backup and QR export", "metadata_warning", "Backup metadata warning", "Unverifiable split-share metadata has been omitted. Continuing exports only the valid secret S. This warning is about retained backup metadata, not proof that split shares were repaired.", sv.Codex32BackupMetadataWarningView, seed=SEED, share_data=S, next_mode=sv.Codex32BackupMetadataWarningView.MODE_DISPLAY)
add("Codex32 backup and QR export", "backup_display_last", "Confirm Backup after display", "For an already loaded seed, the second numbered page offers Confirm Backup instead of finalizing another seed.", sv.Codex32MasterSecretDisplayView, share_data=S, page_index=1, seed=SEED)
add("Codex32 backup and QR export", "backup_confirm_prompt", "Confirm codex32 backup", "Optionally re-enter the displayed string to verify the new transcription. Done leaves this confirmation flow. It checks the exact selected share or S string.", sv.Codex32BackupConfirmPromptView, seed=SEED, expected_share=S)
add("Codex32 backup and QR export", "backup_confirm_entry", "Backup re-entry", "Re-enter the selected string through the numbered keyboard. Backup confirmation requires exact equality and does not accept an automatic correction.", sv.Codex32BackupConfirmEntryView, seed=SEED, expected_share=S)
add("Codex32 backup and QR export", "backup_confirm_invalid", "Backup confirmation failed", "The transcription is invalid or differs from the selected original. Review & Edit reopens the entered boxes.", sv.Codex32BackupConfirmInvalidView, seed=SEED, expected_share=S, share_data=A)
add("Codex32 backup and QR export", "backup_confirm_success", "Backup confirmation succeeded", "The transcribed secret S matched the selected original. Confirming a split share reports that specific share instead; this is a transcription check.", sv.Codex32BackupConfirmSuccessView, seed=SEED)
qr = dict(seed=SEED, seedqr_format=QRType.SEED__CODEX32)
add("Codex32 backup and QR export", "qr_warning", "Codex32QR warning", "A QR containing S is the full secret; a share QR contains that selected split share. Keep real backup QRs offline. The examples here contain public data only.", sv.SeedTranscribeSeedQRWarningView, **qr, num_modules=model.CODEX32_QR_MODULE_TARGET, qr_data=S)
add("Codex32 backup and QR export", "qr_whole", "Whole Codex32QR", "View the selected string's full QR before transcription. The QR contains the plain Codex32 text, with no URI wrapper.", sv.SeedTranscribeSeedQRWholeQRView, **qr, num_modules=model.CODEX32_QR_MODULE_TARGET, qr_data=S)
add("Codex32 backup and QR export", "qr_zoom", "Zoomed QR transcription", "The enlarged QR section helps copy modules onto a paper grid. Navigate through the grid, then scan the completed copy for confirmation.", sv.SeedTranscribeSeedQRZoomedInView, **qr, qr_data=S)
add("Codex32 backup and QR export", "qr_confirm_prompt", "Confirm Codex32QR", "Scan the transcribed QR to compare its exact selected string. This checks your copied QR, not a wallet-policy or address record.", sv.SeedTranscribeSeedQRConfirmQRPromptView, **qr, expected_qr_data=S)
add("Codex32 backup and QR export", "qr_confirm_scan", "Scan the copied QR", "The confirmation camera compares the copied QR with the exact selected Codex32 text. Its preview is a placeholder in this reference.", sv.SeedTranscribeSeedQRConfirmScanView, **qr, expected_qr_data=S)
add("Codex32 backup and QR export", "split_warning", "Split-share display warning", "Selecting Share A changes the warning to identify that split share. Keep its index and threshold with the backup; it is not the complete secret S.", sv.Codex32MasterSecretWarningView, share_data=A, share_idx="a", seed=SEED)
add("Codex32 backup and QR export", "split_display", "Numbered split-share display", "The same numbered display shows the selected share with a Share A title. This first page contains that share's header and data, rather than the secret S string.", sv.Codex32MasterSecretDisplayView, share_data=A, share_idx="a", seed=SEED)
add("Codex32 backup and QR export", "split_confirm_success", "Split-share backup confirmed", "The success message names Share A when its exact transcription matched. It confirms that selected split-share copy, not the whole recovered wallet.", sv.Codex32BackupConfirmSuccessView, seed=SEED, share_idx="a")
add("Codex32 backup and QR export", "split_qr_warning", "Split-share QR warning", "Exporting Share A identifies that split share in the QR warning. A share QR and a secret S QR have different exposure consequences; verify the selection before copying.", sv.SeedTranscribeSeedQRWarningView, **qr, num_modules=model.CODEX32_QR_MODULE_TARGET, qr_data=A, codex32_share_idx="a")
add("Codex32 backup and QR export", "qr_wrong_share", "Wrong QR content", "A readable QR does not match the expected selected string. Recheck whether you copied S or the intended split share.", sv.SeedTranscribeSeedQRConfirmWrongSeedView, seedqr_format=QRType.SEED__CODEX32)
add("Codex32 backup and QR export", "qr_invalid", "Invalid confirmation QR", "The scanned QR is not a valid expected Codex32 backup. Review the grid and retry scanning.", sv.SeedTranscribeSeedQRConfirmInvalidQRView, seedqr_format=QRType.SEED__CODEX32)
add("Codex32 backup and QR export", "qr_success", "QR confirmation succeeded", "The scanned copy matched the expected backup. Keep it with the correct share label and fingerprint/policy records.", sv.SeedTranscribeSeedQRConfirmSuccessView, **qr)


def audit_screen(screen):
    issues = []
    top_nav = getattr(screen, "top_nav", None)
    if top_nav and getattr(top_nav.title, "needs_scroll", False):
        issues.append({"kind": "title_scroll", "text": top_nav.text})
    buttons = getattr(screen, "buttons", [])
    visible_buttons = [b for b in buttons if 0 <= b.screen_y < screen.canvas_height]
    boundary = min((b.screen_y for b in visible_buttons), default=screen.canvas_height)
    for component in screen.components:
        if not isinstance(component, TextArea):
            continue
        image_height = component.rendered_text_img.height
        y = component.screen_y + component.text_y - component.text_height_above_baseline
        if max(line["text_width"] for line in component.text_lines) > component.visible_width + 1:
            issues.append({"kind": "body_width", "text": component.text})
        if image_height > component.height or y + image_height > boundary:
            issues.append({"kind": "body_height", "text": component.text,
                           "bottom": y + image_height, "boundary": boundary})
    if getattr(screen, "instructions_text", None):
        font = Fonts.get_font(GUIConstants.get_body_font_name(), GUIConstants.get_button_font_size())
        if font.getlength(screen.instructions_text) > screen.canvas_width - 2*GUIConstants.EDGE_PADDING:
            issues.append({"kind": "scan_instruction_width", "text": screen.instructions_text})
    if getattr(screen, "warning_message_default", None):
        font = Fonts.get_font(GUIConstants.get_body_font_name(), 12)
        _, top, _, bottom = font.getbbox(screen.warning_message_default, anchor="ls")
        if screen.warning_y + bottom-top > screen.keyboard_top:
            issues.append({"kind": "entry_hint_overlap", "text": screen.warning_message_default})
    return issues


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--height", type=int, choices=(240, 320), default=240)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.height == 320 and args.output_dir is None:
        parser.error("240x320 QA requires --output-dir; public guide uses 240x240")
    os.environ["SEEDSIGNER_SCREENSHOT_SIZE"] = f"240x{args.height}"
    runtime_patch = subprocess.check_output(["git", "-C", str(ROOT), "diff", "22ee79b", "--", "src"])
    runtime_dirty = bool(subprocess.check_output(["git", "-C", str(ROOT), "diff", "HEAD", "--", "src"]))
    if not ImageFont.core.HAVE_RAQM:
        raise RuntimeError("libraqm is required for device-equivalent text layout")
    output = args.output_dir or ROOT / "docs/codex32_qr/img/screens"
    output.mkdir(parents=True, exist_ok=True)
    ScreenshotRenderer.configure_instance()
    renderer = ScreenshotRenderer.get_instance()
    if (renderer.canvas_width, renderer.canvas_height) != (240, args.height):
        raise RuntimeError("Unexpected screenshot dimensions")
    renderer.set_screenshot_path(str(output))
    records = []
    with patch.object(Renderer, "configure_instance", Mock()), patch.object(Renderer, "get_instance", Mock(return_value=renderer)), patch("seedsigner.controller.BackgroundImportThread.start"):
        # View imports are already loaded; background Pi/numpy imports are irrelevant.
        for case in CASES:
            Controller.reset_instance()
            controller = Controller.get_instance()
            controller._storage = SeedStorage()
            settings = Settings.get_instance()
            settings.set_value(SC.SETTING__LOCALE, SC.LOCALE__ENGLISH)
            settings.set_value(SC.SETTING__NETWORK, SC.TESTNET)
            controller.storage.pending_seed = SEED
            controller.storage.seeds.append(SEED)
            filename = case["filename"] + ".png"
            renderer.set_screenshot_filename(filename)
            view = case["cls"](**case["args"])
            try:
                view.run()
            except ScreenshotComplete:
                pass
            else:
                raise RuntimeError("No screenshot: " + filename)
            path = output / filename
            data = path.read_bytes()
            records.append(dict(filename=filename, view=case["cls"].__name__, title=case["title"],
                                section=case["section"], bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                                layout_issues=audit_screen(view.screen)))
    document = """# Codex32 screen reference

This reference shows the Codex32 import, correction, fingerprint, loading and
backup screens in the experimental fork. Use it to recognize what the device is
asking you to check. For a step-by-step recovery, see the
[user flow guide](Codex32_User_Flow_Guide.md); for wallet setup and public share
QRs, see the [build and test guide](Codex32_Experimental_Build_and_Test.md).

**Public test data only. Never fund these example wallets.** All screenshots use
public BIP93 NAME data (fingerprint `fab6868a`) or deliberately damaged versions
of it. They are native 240x240 renders of the reviewed layout/duplicate-share
candidate, with hardware mocked. Source hashes, checkout identity and the delta
from the historical `22ee79b` baseline identify the captured code in the image
manifest. See the build guide for the frozen runtime pin and device-test status.
These images are software renders, not photos of the previously tested UX5
firmware. The camera image is a placeholder.
Some menus scroll; screenshots show the initial viewport. Shared SeedSigner
screens are included where Codex32 changes their content. Button names can differ
in other languages. A fingerprint match is a 32-bit accidental-error check,
not authentication; verify the wallet policy and a known address as well.

"""
    section = None
    for case in CASES:
        if case["section"] != section:
            section = case["section"]
            document += f"## {section}\n\n| Screen | When it appears and what it means |\n| --- | --- |\n"
        document += f'| **{case["title"]}**<br>![{case["title"]}](img/screens/{case["filename"]}.png) | {case["text"]} |\n'
    document += """
## Image provenance and regeneration

The [image manifest](img/screens/manifest.json) records each screenshot's View,
SHA256, size and the runtime-source hashes used to render it. Recreate them with
repository development dependencies installed:

```bash
python tools/render_codex32_screen_reference.py
```

The renderer takes only the fixed public fixtures in its source and makes no
release lookup or camera capture. Do not replace these illustrations with photos
or screenshots containing real backup data. Images illustrate individual states;
they do not replace navigation or hardware testing.
"""
    if args.output_dir is None:
        (ROOT / "docs/codex32_qr/Codex32_Screen_Reference.md").write_text(document, encoding="utf-8", newline="\n")
    sources = [ROOT / "src/seedsigner/views/seed_views.py", ROOT / "src/seedsigner/views/codex32_views.py",
               ROOT / "src/seedsigner/views/scan_views.py", ROOT / "src/seedsigner/gui/screens/seed_screens.py",
               ROOT / "src/seedsigner/gui/screens/scan_screens.py", ROOT / "src/seedsigner/models/codex32_correction.py",
               ROOT / "src/seedsigner/gui/screens/screen.py", ROOT / "src/seedsigner/gui/components.py",
               ROOT / "src/seedsigner/gui/keyboard.py", ROOT / "src/seedsigner/gui/renderer.py",
               ROOT / "src/seedsigner/views/view.py", ROOT / "tests/screenshot_generator/generator.py",
               ROOT / "tests/screenshot_generator/utils.py",
               ROOT / "tools/render_codex32_screen_reference.py"]
    manifest = dict(base_runtime_commit="22ee79b2d9aff6ecf6b49572f42361c9363d598f",
                    checkout_commit=subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip(),
                    base_runtime_tree=subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "22ee79b:src"], text=True).strip(),
                    working_tree_runtime_changes=runtime_dirty, runtime_patch_sha256=hashlib.sha256(runtime_patch).hexdigest(),
                    language="en", dimensions=[240,args.height], test_data="Public BIP93 vector 2 NAME only",
                    hardware="mocked", sources={str(p.relative_to(ROOT)).replace("\\", "/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, images=records)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Rendered {len(records)} Codex32 screenshots to {output}")
    issues = {r["filename"]:r["layout_issues"] for r in records if r["layout_issues"]}
    print("Layout findings: " + json.dumps(issues))
    if issues:
        raise RuntimeError("Fix layout findings before using the screen reference")

if __name__ == "__main__":
    main()
