from pathlib import Path

import pytest

from seedsigner.helpers.anti_exfil import AntiExfilUnavailableError
from seedsigner.helpers import anti_exfil_selftest
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


def test_selftest_pins_host_commit_signer_commit_and_signature(monkeypatch, tmp_path):
    class FakeBackend:
        def __init__(self, library_path):
            self.library_path = library_path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def host_commit(self, rho):
            assert rho == anti_exfil_selftest.HOST_RANDOMNESS
            return anti_exfil_selftest.HOST_COMMITMENT

        def signer_commit(self, secret, message, commitment):
            assert commitment == anti_exfil_selftest.HOST_COMMITMENT
            return anti_exfil_selftest.EXPECTED_OPENING

        def sign(self, secret, message, rho):
            assert rho == anti_exfil_selftest.HOST_RANDOMNESS
            return anti_exfil_selftest.EXPECTED_SIGNATURE

    monkeypatch.setattr(anti_exfil_selftest, "AntiExfilNativeBackend", FakeBackend)
    result = run_selftest(tmp_path / "fixture.so")
    assert result["host_commitment_matches"] is True
    assert result["opening_matches"] is True
    assert result["signature_matches"] is True
