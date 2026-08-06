from pathlib import Path

import pytest

from seedsigner.helpers.anti_exfil import AntiExfilUnavailableError
from seedsigner.helpers.anti_exfil_selftest import main, run_selftest


def test_selftest_fails_closed_without_library(tmp_path, capsys):
    missing = tmp_path / "missing.so"
    assert main(["--library", str(missing)]) == 1
    result = capsys.readouterr()
    assert '"status": "error"' in result.err
    assert '"production_fallback": false' in result.err


def test_selftest_function_propagates_backend_failure(tmp_path):
    with pytest.raises(AntiExfilUnavailableError):
        run_selftest(Path(tmp_path / "missing.so"))
