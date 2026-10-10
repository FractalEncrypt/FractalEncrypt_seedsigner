# SeedSigner Codex32 Alpha 0.1: build from source

**Experimental independent fork: public practice seeds and testnet/regtest only.
Do not enter real backups or mainnet seeds, or use this alpha to secure funds.
Mainnet is not disabled. This is not an official SeedSigner release.**

For users compiling their own Pi Zero image. 

## Pinned build inputs

| Input | Revision |
| --- | --- |
| Application | `87a4be4de12e24ce1c7f9e0bfcd6b78a535d3537` |
| OS | `d13859392660fe512a753bc14ecd0edc86c35510` |
| Buildroot | `bf2a2858aa675a14b60f1f9142c65b32652609c1` |
| Version metadata | `v0.8.7-Codex32-EC-UX7-test` |
| Target | `--pi0`; device testing covers Pi Zero 1.3 |

The upstream builder defaults to upstream SeedSigner. The steps below select
this fork and provide the version metadata its startup screen needs.

## Build on Linux / WSL2 / macOS

Install Git, Python 3, and Docker Engine or Docker Desktop with Compose support.
Use a fresh directory, not an existing SeedSigner OS build. On Windows, use WSL2
and clone inside its Linux filesystem (for example under `~/`), so Unix symlinks
and executable permissions are preserved. Allow the disk space/build time
specified in the [upstream guide](https://github.com/SeedSigner/seedsigner-os/blob/d13859392660fe512a753bc14ecd0edc86c35510/docs/building.md).

The commands below build Pi Zero / Zero W. They are intentionally pinned rather
than tracking the changing branch tip.

```bash
mkdir codex32-alpha-build
cd codex32-alpha-build

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
export SS_ARGS='--pi0 --skip-repo --app-branch=codex32-alpha-0.1'
docker compose up --force-recreate --build
```

Expected image: `images/seedsigner_os.codex32-alpha-0.1.pi0.img`.
Confirm completion with exit code zero, then hash it before mounting/flashing:

```bash
sha256sum images/seedsigner_os.codex32-alpha-0.1.pi0.img
```

On macOS, use `shasum -a 256` if `sha256sum` is unavailable. For another board,
use the upstream board table and replace `--pi0`; those targets are not validated
by the Pi Zero 1.3 tests. Flash using the existing upstream image-writing steps.
After boot, check `v0.8.7-Codex32-EC-UX7-test` and `87a4be4` in Settings > Version.

These commands pin the runtime used in Alpha 0.1. A fresh build may have a
different image hash from the published binary; an independent identical rebuild
has not been established. The retained version string is the development label
embedded in the tested image, not a different public release name.

After flashing, follow the [recovery and test guide](Codex32_Experimental_Test_Guide.md).
For the published binary's hash and tested hardware, see the
[Alpha 0.1 release notes](Codex32_Experimental_Release_Notes.md).
