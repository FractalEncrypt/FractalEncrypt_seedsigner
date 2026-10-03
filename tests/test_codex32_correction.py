"""Public vectors and failure boundaries for fixed codex32 correction."""

import ast
import json
from pathlib import Path
from random import Random

import pytest

from seedsigner.models.codex32 import parse_codex32_share
from seedsigner.models.codex32_correction import suggest_correction
from seedsigner.models.codex32_min import CHARSET

SECRET = "MS10TESTSXXXXXXXXXXXXXXXXXXXXXXXXXX4NZVCA9CMCZLW"
SHARE = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"


def damage(source, positions=(), erasures=()):
    values = list(source)
    for position in positions:
        values[position] = CHARSET[CHARSET.index(values[position].lower()) ^ 1].upper()
    for position in erasures:
        values[position] = "?"
    return "".join(values)


@pytest.mark.parametrize("source", [SECRET, SHARE])
def test_every_ordinary_error_erasure_distribution(source):
    rng = Random(93)
    for substitutions in range(5):
        for erasures in range(9):
            if not substitutions + erasures or 2 * substitutions + erasures > 8:
                continue
            for _ in range(10):
                positions = rng.sample(range(3, 48), substitutions + erasures)
                damaged = damage(source, positions[:substitutions], positions[substitutions:])
                proposal = suggest_correction(damaged)
                assert proposal is not None
                assert proposal.corrected == source
                assert proposal.original == damaged
                assert len(proposal.erasure_indices) == erasures
                assert len(proposal.substitution_indices) == substitutions
                assert parse_codex32_share(proposal.corrected).s == source


def test_adjacent_transposition_is_two_substitutions():
    values = list(SHARE)
    values[17], values[18] = values[18], values[17]
    proposal = suggest_correction("".join(values))
    assert proposal.corrected == SHARE
    assert proposal.substitution_indices == (17, 18)


@pytest.mark.parametrize("width", range(9, 14))
def test_every_consecutive_large_erasure_position(width):
    for start in range(3, 49 - width):
        proposal = suggest_correction(damage(SHARE, erasures=range(start, start + width)))
        assert proposal.corrected == SHARE
        assert proposal.large_recovery is True


def test_frozen_upstream_48_character_corpus():
    corpus = json.loads((Path(__file__).parent / "data" / "codex32_correction_vectors.json").read_text())
    assert corpus["source"]["head"] == "610cbad30258c80cd862b3773a20f8099d25e36e"
    for case in corpus["cases"]:
        proposal = suggest_correction(case["damaged"])
        if case["expected"] is None:
            assert proposal is None
        else:
            assert proposal is not None
            assert proposal.corrected == case["expected"].upper()


@pytest.mark.parametrize("value", [
    None, b"MS1", "M" + SECRET[1:].lower(), SECRET[:-1], SECRET + "Q",
    "XS1" + SECRET[3:], SECRET[:10] + "O" + SECRET[11:],
    SECRET[:10] + "-" + SECRET[11:], SECRET[:10] + "é" + SECRET[11:],
    damage(SHARE, [5, 15, 25, 35, 40]),
    damage(SHARE, erasures=range(15, 29)),
    damage(SHARE, erasures=[4, 9, 15, 21, 27, 33, 39, 43, 45]),
    SECRET,
])
def test_malformed_out_of_scope_or_unchanged_input_has_no_proposal(value):
    assert suggest_correction(value) is None


def test_confirmed_prefix_cannot_be_changed():
    assert suggest_correction(damage(SHARE, [5]), immutable_prefix=SHARE[:8]) is None
    assert suggest_correction(damage(SHARE, [17]), immutable_prefix=SHARE[:8]).corrected == SHARE
    assert suggest_correction(damage(SHARE, [17]), immutable_prefix="MS1INVALID") is None


def test_thirteen_erasures_and_an_extra_typo_can_complete_to_the_wrong_seed():
    proposal = suggest_correction(damage(SHARE, [10], range(15, 28)))
    assert proposal is not None and proposal.large_recovery
    assert proposal.corrected != SHARE
    assert parse_codex32_share(proposal.corrected).data != parse_codex32_share(SHARE).data


def test_proposal_repr_does_not_disclose_share_text():
    proposal = suggest_correction(damage(SHARE, [17]))
    assert proposal.original not in repr(proposal)
    assert proposal.corrected not in repr(proposal)


def test_vendored_correction_parses_with_python_310_grammar():
    source = Path(__file__).parents[1] / "src" / "seedsigner" / "models" / "codex32_correction.py"
    ast.parse(source.read_text(), feature_version=(3, 10))
