# Experimental Codex32 EC: build and test

**Experimental fork: public test seeds and testnet/regtest only. Do not enter
real backups, mainnet seeds, or use this image to secure funds.** These are tester
instructions, not an upstream SeedSigner release endorsement. The software is
not restricted to testnet by code; this warning is a testing policy.

The upstream build guide explains Docker and hardware selection, but its default
application repository is upstream SeedSigner. A fresh checkout of our tested OS
revision also needs explicit version metadata. The numbered-entry/correction
feature is documented in [Codex32 Error Correction](Codex32_Error_Correction.md).

## Pinned test revision

| Input | Revision |
| --- | --- |
| Application repository | `https://github.com/FractalEncrypt/FractalEncrypt_seedsigner.git` |
| Application branch for development | `codex/codex32-error-correction` |
| Application commit for this test | `11270918b794f83be5e9051d391599ff607ff655` |
| OS repository | `https://github.com/SeedSigner/seedsigner-os.git` |
| OS commit | `d13859392660fe512a753bc14ecd0edc86c35510` (v0.8.7) |
| Buildroot commit, selected by OS submodule | `bf2a2858aa675a14b60f1f9142c65b32652609c1` |
| Primary device target | Pi Zero 1.3, `--pi0`, standard 240x240 Waveshare display |

The application review passed with nonblocking followups. Desktop tests pass
(580 normal / 84 optimized). Earlier device sessions and a Pi Zero benchmark
passed, but the final UX4 refinements still need the maintainer's physical check.
No public release image is implied by this guide.

## Clean build on Linux / WSL2 / macOS

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
git -C opt/rootfs-overlay/opt checkout --detach 11270918b794f83be5e9051d391599ff607ff655
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
assert commit == '11270918b794f83be5e9051d391599ff607ff655'
metadata = {
    'name': 'v0.8.7-Codex32-EC-UX4-test',
    'fork': 'FractalEncrypt',
    'short_commit_hash': commit[:7],
    'timestamp': datetime.fromisoformat(git('show', '-s', '--format=%cI', 'HEAD')).astimezone(timezone.utc).replace(tzinfo=None).isoformat(),
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
export SS_ARGS='--pi0 --skip-repo --app-branch=codex32-ec-ux4-test'
docker compose up --force-recreate --build
```

Expected image: `images/seedsigner_os.codex32-ec-ux4-test.pi0.img`.
Confirm completion with exit code zero, then hash it before mounting/flashing:

```bash
sha256sum images/seedsigner_os.codex32-ec-ux4-test.pi0.img
```

On macOS, use `shasum -a 256` if `sha256sum` is unavailable. For another board,
use the upstream board table and replace `--pi0`; those targets are not validated
by the Pi Zero 1.3 tests. Flash using the existing upstream image-writing steps.
After boot, check the experimental label and `1127091` in Settings / About.

This procedure has been checked against the pinned builder and its shell syntax;
a complete fresh image build has not been run for this guide. It builds the same
application revision, but byte-for-byte reproduction of the maintainer's image
has not been established. The maintainer's staged image uses a different version
file timestamp. A published release should supply its exact metadata and build
receipt; equal application commits alone do not imply equal firmware hashes.

## Safe tester smoke checks

Use only these public shares (threshold 2, identifier NAME):

```text
A: MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM
C: MS12NAMECACDEFGHJKLMNPQRSTUVWXYZ023FTR2GDZMPY6PN
Expected recovered master fingerprint: fab6868a
```

These are public test data; never send funds to their wallets.

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
