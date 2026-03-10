# Codex32_Implementation Branch Review

Branch: FractalEncrypt/FractalEncrypt_seedsigner @ Codex32_Implementation
Reviewed: 2026-03-10
30 commits, 49 files changed

## Raw vs Real Diff

The diff shows +17,250/-12,450 lines, but with whitespace changes ignored
the real changes are only +4,965/-165. Over 70% of the diff is
whitespace/line-ending reformatting noise. This is the #1 blocker for
upstream acceptance.

## Prioritized Changes

### HIGH - Must fix before upstream PR

1. **Whitespace reformatting pollutes the diff** - Files like screen.py
   (2,654 line diff, 2 real changes), psbt_parser.py (991 vs 49),
   psbt_views.py (1,271 vs 93), controller.py (997 vs 27) have massive
   whitespace-only changes mixed with real code. Upstream reviewers will
   reject this immediately. Fix: rebase and separate whitespace commits
   from feature commits, or strip whitespace changes entirely.

2. **CRLF line endings mixed in** - 168 lines with carriage returns
   detected. SeedSigner upstream uses Unix (LF) line endings. Fix:
   normalize all line endings to LF and add .gitattributes if needed.

3. **codex32_min.py has no external dependencies (good) but duplicates
   _is_single_case** - The function exists in both codex32.py and
   codex32_min.py. codex32.py should import it from codex32_min.

4. **Memory wiping is best-effort only** - wipe_codex32_share() and
   Codex32Seed.wipe() note that Python strings are immutable. This is
   honest and correct, but the PR should document this limitation
   explicitly for upstream reviewers who will ask about it.

5. **128-bit seeds only** - codex32.py hardcodes 16-byte (128-bit) seed
   support and 48-char shares. BIP-93 supports 128 to 512 bits. The
   spec doc acknowledges this constraint, but the code should validate
   gracefully if longer shares are scanned (currently raises a generic
   length error).

### MED - Should fix for quality

6. **codex32_to_seed_bytes only handles S-shares** - If a non-S share
   is passed, the error message could be clearer about the recovery flow.

7. **Codex32ShareCollection.recovered_secret_share silently returns None
   on error** - Line 228 catches Codex32InputError and returns None. This
   swallows validation errors during recovery. Consider logging or
   surfacing the error type.

8. **sanitize_codex32_input strips hyphens** - But the Codex32QR spec
   (section 3.2) says "Hyphens MUST NOT be silently stripped" and
   "Payloads that contain hyphens MUST be rejected." The sanitize
   function strips hyphens, which contradicts the spec. Either the spec
   or the code needs to change.

9. **PSBT parser changes are unrelated to Codex32** - The psbt_parser.py
   and psbt_views.py real changes (49 and 93 lines) include bug fixes
   (missing-utxo guard, signed metadata preservation) that should be
   separate PRs to upstream. Mixing feature + bugfix makes review harder.

10. **Test coverage gaps** - No negative/adversarial tests for:
    - Malformed codex32 strings with valid-looking prefixes
    - Threshold edge cases (threshold = 0, threshold > 9)
    - Share index collision during recovery
    - Extremely long input strings

11. **TODOs in seed_views.py** - 6 TODO comments remain in the codebase
    (lines 1663, 2009, 2106, 2639, 2740, 2924). These should be resolved
    or converted to GitHub issues before upstream PR.

### LOW - Nice to have

12. **Documentation typo** - File is named "Seedigner_" (missing 'S' in
    SeedSigner) in the Implementation Overview doc path.

13. **Codex32QR spec could reference BIP-93 directly** - The spec is
    well-written but doesn't link to the actual BIP-93 document.

14. **Screenshot generator changes** - 294 lines of changes to the
    screenshot generator. These are test tooling changes and could be
    a separate PR.

15. **qr_type.py shows full-file diff** - Only 1 real line added
    (SEED__CODEX32) but the entire file shows as changed due to
    whitespace normalization.

## Architecture Assessment

The Codex32 implementation itself is clean and well-structured:
- codex32_min.py: Pure BIP-93 math, no dependencies, portable
- codex32.py: Higher-level validation/conversion, uses embit for BIP39
- Codex32Seed extends Seed cleanly
- Share collection flow with threshold-based recovery
- Memory wiping (best-effort, honestly documented)
- 14 new view classes for complete UX flow
- Solid test coverage (16 unit + 8 flow tests)
- Good documentation with test vectors

The main blocker is not the code quality - it is the diff hygiene.
