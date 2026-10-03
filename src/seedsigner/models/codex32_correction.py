# Copyright (c) 2025 Blockstream
# Copyright (c) 2026 Ben Westgate <benwestgate@protonmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Bounded 48-character codex32 correction; proposals require user confirmation.

Arithmetic vendored from benwestgate/python-codex32, revision
f19d462 (2026-09-28), correction.py and gf32.py, derived from PR #70.
Only fixed substitutions/erasures are supported. No alignment search, wallet
code, generation-padding hints, or external dependencies are included.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache

from .codex32_min import CHARSET, bech32_mul, _is_single_case

_GF32_MUL = tuple(tuple(bech32_mul(a, b) for b in range(32)) for a in range(32))
_GF32_INV = tuple(next((b for b in range(32) if _GF32_MUL[a][b] == 1), 0) for a in range(32))


def _gf32_multiply(left: int, right: int) -> int:
    return _GF32_MUL[left][right]


def _gf32_inverse(value: int) -> int:
    return _GF32_INV[value]


def bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _gf1024(a: int, b: int = 0) -> int:
    return a | (b << 5)


def _gf1024_mul_raw(left: int, right: int) -> int:
    a0, b0 = left & 31, left >> 5
    a1, b1 = right & 31, right >> 5
    b0b1 = _gf32_multiply(b0, b1)
    return _gf1024(
        _gf32_multiply(a0, a1) ^ b0b1,
        _gf32_multiply(a0, b1) ^ _gf32_multiply(a1, b0) ^ b0b1,
    )


def _field_tables() -> tuple[tuple[int, ...], tuple[int, ...]]:
    values = [1]
    for _ in range(1022):
        values.append(_gf1024_mul_raw(values[-1], _gf1024(2, 1)))
    logarithms = [0] * 1024
    for exponent, value in enumerate(values):
        logarithms[value] = exponent
    return tuple(values * 2), tuple(logarithms)


_GF1024_EXP, _GF1024_LOG = _field_tables()


def _gf1024_mul(left: int, right: int) -> int:
    return 0 if not left or not right else _GF1024_EXP[_GF1024_LOG[left] + _GF1024_LOG[right]]


def _gf1024_inv(value: int) -> int:
    return _GF1024_EXP[1023 - _GF1024_LOG[value]]


def _gf1024_pow(value: int, exponent: int) -> int:
    return 0 if not value else _GF1024_EXP[(_GF1024_LOG[value] * exponent) % 1023]


def _poly_sum(left: list[int], right: list[int]) -> list[int]:
    size = max(len(left), len(right))
    return [
        (left[index] if index < len(left) else 0) ^ (right[index] if index < len(right) else 0)
        for index in range(size)
    ]


def _poly_mul(left: list[int], right: list[int], multiply: Callable[[int, int], int]) -> list[int]:
    if not left or not right:
        return []
    result = [0] * (len(left) + len(right) - 1)
    for left_index, left_value in enumerate(left):
        for right_index, right_value in enumerate(right):
            result[left_index + right_index] ^= multiply(left_value, right_value)
    return result


def _horner(
    polynomial: list[int] | tuple[int, ...],
    value: int,
    multiply: Callable[[int, int], int],
) -> int:
    result = 0
    for coefficient in reversed(polynomial):
        result = multiply(result, value) ^ coefficient
    return result


def _poly_diff(polynomial: list[int]) -> list[int]:
    return [coefficient if power & 1 else 0 for power, coefficient in enumerate(polynomial[1:], 1)]


def _poly_mod(polynomial: list[int], modulus: tuple[int, ...]) -> list[int]:
    degree = len(modulus)
    work = list(polynomial)
    if len(work) < degree:
        work.extend([0] * (degree - len(work)))
    modulus_le = list(reversed((1,) + modulus))
    for top in range(len(work) - 1, degree - 1, -1):
        coefficient = work[top]
        if coefficient:
            offset = top - degree
            for index, value in enumerate(modulus_le):
                work[offset + index] ^= _gf32_multiply(coefficient, value)
    return work[:degree]


def _poly_powers(modulus: tuple[int, ...], count: int) -> list[list[int]]:
    degree = len(modulus)
    powers: list[list[int]] = []
    value = [1] + [0] * (degree - 1)
    modulus_le = list(reversed(modulus))
    for _ in range(count):
        powers.append(value)
        carry = value[-1]
        value = [0] + value[:-1]
        if carry:
            value = [
                coefficient ^ _gf32_multiply(carry, reduction)
                for coefficient, reduction in zip(value, modulus_le)
            ]
    return powers


@dataclass(frozen=True, slots=True)
class _Spec:
    base: int
    first_root: int
    target: tuple[int, ...]
    roots: tuple[int, ...]
    generator: tuple[int, ...]
    period: int


_SHORT_SPEC = _Spec(
    256,
    77,
    (16, 25, 24, 3, 25, 11, 16, 23, 29, 3, 25, 17, 10),
    (99, 24, 992, 462, 11, 320, 66, 16),
    (25, 27, 17, 8, 0, 25, 25, 25, 31, 27, 24, 16, 16),
    93,
)


def _residue(spec: _Spec, hrp: str, body: list[int]) -> list[int]:
    initial_and_hrp = [1, *bech32_hrp_expand(hrp)]
    return _poly_mod(list(reversed(initial_and_hrp + body)), spec.generator)


def _syndromes(spec: _Spec, residue: list[int], *, target: bool) -> tuple[int, ...]:
    coefficients = [
        _gf1024(value ^ bias)
        for value, bias in zip(residue, reversed(spec.target) if target else (0,) * len(residue))
    ]
    return tuple(_horner(coefficients, root, _gf1024_mul) for root in spec.roots)


def _generate_next(coefficients: list[int], values: list[int]) -> int:
    result = 0
    for coefficient, value in zip(coefficients, values):
        result ^= _gf1024_mul(coefficient, value)
    return result


def _synthesize_rec(values: list[int]) -> tuple[list[int], list[int]]:
    if not values:
        return [], [0]
    newest, older = values[0], values[1:]
    coefficients, adjustment = _synthesize_rec(older)
    discrepancy = newest ^ _generate_next(coefficients, older)
    if discrepancy:
        updated = _poly_sum(coefficients, [_gf1024_mul(discrepancy, value) for value in adjustment])
    else:
        updated = coefficients
    if len(updated) == len(coefficients):
        updated_adjustment = [0] + adjustment
    else:
        inverse = _gf1024_inv(discrepancy)
        updated_adjustment = [_gf1024_mul(value, inverse) for value in [1] + coefficients]
    return updated, updated_adjustment


def _small_locator(sequence: list[int], maximum: int) -> list[int] | None:
    if not any(sequence):
        return [1]
    if maximum < 2:
        if maximum < 1 or not sequence[0]:
            return None
        coefficient = _gf1024_mul(sequence[1], _gf1024_inv(sequence[0]))
        if all(
            sequence[index] == _gf1024_mul(coefficient, sequence[index - 1])
            for index in range(2, len(sequence))
        ):
            return [1, coefficient]
        return None
    first_row = sequence[1], sequence[0], sequence[2]
    second_row = sequence[2], sequence[1], sequence[3]
    a, b, target = first_row
    c, d, other_target = second_row
    determinant = _gf1024_mul(a, d) ^ _gf1024_mul(b, c)
    if determinant:
        inverse = _gf1024_inv(determinant)
        first = _gf1024_mul(_gf1024_mul(target, d) ^ _gf1024_mul(b, other_target), inverse)
        second = _gf1024_mul(_gf1024_mul(a, other_target) ^ _gf1024_mul(target, c), inverse)
        valid = all(
            sequence[index]
            == _gf1024_mul(first, sequence[index - 1]) ^ _gf1024_mul(second, sequence[index - 2])
            for index in range(4, len(sequence))
        )
        if not valid:
            return None
        if second:
            return [1, first, second]
        return [1, first] if sequence[1] == _gf1024_mul(first, sequence[0]) else None
    if sequence[0]:
        coefficient = _gf1024_mul(sequence[1], _gf1024_inv(sequence[0]))
        if all(
            sequence[index] == _gf1024_mul(coefficient, sequence[index - 1])
            for index in range(2, len(sequence))
        ):
            return [1, coefficient]
    coefficients, _adjustment = _synthesize_rec(list(reversed(sequence)))
    return [1, *coefficients] if len(coefficients) <= maximum else None


def _locator_poly(
    syndromes: list[int],
    erasure_poly: list[int],
    maximum: int | None,
    erasure_products: tuple[tuple[int, ...], ...] | None = None,
) -> list[int] | None:
    degree = len(erasure_poly) - 1
    if degree == 2 and erasure_products is not None:
        first, second = erasure_products
        modified = [
            syndromes[index - 2] ^ first[syndromes[index]] ^ second[syndromes[index - 1]]
            for index in range(2, len(syndromes))
        ]
    else:
        modified = []
        for output_index in range(degree, len(syndromes)):
            value = syndromes[output_index - degree]
            products = erasure_products
            for index, coefficient in enumerate(erasure_poly[:-1]):
                syndrome = syndromes[output_index - index]
                value ^= _gf1024_mul(coefficient, syndrome) if products is None else products[index][syndrome]
            modified.append(value)
    if maximum is not None and maximum <= 2:
        return _small_locator(modified, maximum)
    coefficients, _adjustment = _synthesize_rec(list(reversed(modified)))
    return [1] + coefficients


@cache
def _word_roots(spec: _Spec, length: int) -> tuple[int, ...]:
    return tuple(_gf1024_inv(_gf1024_pow(spec.base, index)) for index in range(length))


def _erasure_state(spec: _Spec, length: int, indices: tuple[int, ...]) -> tuple[tuple[int, ...], list[int]]:
    word_roots = _word_roots(spec, length)
    roots = tuple(word_roots[index] for index in indices)
    polynomial = [1]
    for root in roots:
        polynomial = _poly_mul(polynomial, [root, 1], _gf1024_mul)
    return roots, polynomial


def _bch_syndrome_corrections(
    spec: _Spec,
    erasure_indices: list[int],
    syndromes: list[int],
    word_length: int,
    max_substitutions: int | None,
    erasure_state: tuple[tuple[int, ...], list[int]] | None = None,
    erasure_products: tuple[tuple[int, ...], ...] | None = None,
) -> list[tuple[int, int]] | None:
    word_roots = _word_roots(spec, word_length)
    erasure_roots, erasure_poly = (
        _erasure_state(spec, word_length, tuple(erasure_indices)) if erasure_state is None else erasure_state
    )
    locator = _locator_poly(syndromes, erasure_poly, max_substitutions, erasure_products)
    if locator is None or max_substitutions is not None and len(locator) - 1 > max_substitutions:
        return None
    errors = [
        (index, root) for index, root in enumerate(word_roots) if _horner(locator, root, _gf1024_mul) == 0
    ]
    if len(locator) != 1 + len(errors):
        return None
    full_locator = _poly_mul(locator, erasure_poly, _gf1024_mul)
    omega = _poly_mul(syndromes, full_locator, _gf1024_mul)[: len(spec.roots)]
    derivative = _poly_diff(full_locator)
    positions = [*errors, *zip(erasure_indices, erasure_roots)]
    if len({root for _index, root in positions}) != len(full_locator) - 1:
        return None
    corrections: list[tuple[int, int]] = []
    for index, inverse_root in positions:
        numerator = _horner(omega, inverse_root, _gf1024_mul)
        numerator = _gf1024_mul(numerator, _gf1024_pow(inverse_root, spec.first_root - 1))
        denominator = _horner(derivative, inverse_root, _gf1024_mul)
        error = _gf1024_mul(numerator, _gf1024_inv(denominator))
        if error >> 5:
            return None
        corrections.append((index, error & 31))
    return corrections


def _solve_linear(vectors: list[list[int]], target: list[int]) -> list[int] | None:
    columns = len(vectors)
    if not columns:
        return [] if not any(target) else None
    matrix = [
        [vectors[column][row] for column in range(columns)] + [target[row]] for row in range(len(target))
    ]
    for column in range(columns):
        pivot = next((row for row in range(column, len(matrix)) if matrix[row][column]), None)
        if pivot is None:
            return None
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        inverse = _gf32_inverse(matrix[column][column])
        matrix[column] = [_gf32_multiply(value, inverse) for value in matrix[column]]
        for row_index in range(len(matrix)):
            if row_index == column or not matrix[row_index][column]:
                continue
            scale = matrix[row_index][column]
            matrix[row_index] = [
                value ^ _gf32_multiply(scale, pivot_value)
                for value, pivot_value in zip(matrix[row_index], matrix[column])
            ]
    if any(not any(row[:columns]) and row[-1] for row in matrix):
        return None
    return [matrix[row][-1] for row in range(columns)]


def _linear_error_corrections(
    spec: _Spec, erasure_indices: list[int], residue: list[int]
) -> list[tuple[int, int]] | None:
    checksum_error = [value ^ bias for value, bias in zip(residue, reversed(spec.target))]
    powers = _poly_powers(spec.generator, max(erasure_indices, default=-1) + 1)
    solution = _solve_linear([powers[index] for index in erasure_indices], checksum_error)
    return None if solution is None else list(zip(erasure_indices, solution))


def _error_corrections(
    spec: _Spec,
    erasure_indices: list[int],
    residue: list[int],
    word_length: int | None = None,
    max_substitutions: int | None = None,
) -> list[tuple[int, int]] | None:
    length = spec.period if word_length is None else word_length
    bch = None
    if len(erasure_indices) <= len(spec.roots):
        bch = _bch_syndrome_corrections(
            spec,
            erasure_indices,
            list(_syndromes(spec, residue, target=True)),
            length,
            max_substitutions,
        )
    if bch is not None and _corrections_reach_target(spec, residue, bch):
        return bch
    if max_substitutions is not None and max_substitutions > 0:
        return None
    if len(erasure_indices) > len(spec.generator):
        return None
    linear = _linear_error_corrections(spec, erasure_indices, residue)
    return linear if linear is not None and _corrections_reach_target(spec, residue, linear) else None


def _corrections_reach_target(spec: _Spec, residue: list[int], corrections: list[tuple[int, int]]) -> bool:
    count = max((index for index, _addend in corrections), default=-1) + 1
    powers = _poly_powers(spec.generator, count)
    corrected = list(residue)
    for reverse_index, addend in corrections:
        corrected = _poly_sum(
            corrected,
            [_gf32_multiply(addend, value) for value in powers[reverse_index]],
        )
    return corrected == list(reversed(spec.target))

@dataclass(frozen=True, repr=False)
class Codex32Correction:
    original: str
    corrected: str
    changed_indices: tuple[int, ...]
    erasure_indices: tuple[int, ...]

    @property
    def substitution_indices(self) -> tuple[int, ...]:
        return tuple(i for i in self.changed_indices if i not in self.erasure_indices)

    @property
    def large_recovery(self) -> bool:
        return len(self.erasure_indices) > 8


def suggest_correction(raw: str, immutable_prefix: str = "MS1") -> Codex32Correction | None:
    """Return one untrusted bounded proposal, or None. Never accept or mutate a share.

    The ordinary domain is 2*S + E <= 8. Nine through thirteen erasures
    must be consecutive, with no substitutions. MS1 and confirmed headers
    remain immutable. Out-of-domain damage can still yield a wrong valid
    proposal, so neither uniqueness nor checksum validity authenticates it.
    """
    from .codex32 import (
        Codex32InputError, parse_codex32_share, sanitize_codex32_input,
        validate_codex32_s_share, wipe_codex32_share, _parse_threshold,
    )

    if not isinstance(raw, str) or len(raw) > 192:
        return None
    try:
        text = sanitize_codex32_input(raw)
    except Codex32InputError:
        return None
    if len(text) != 48 or not _is_single_case(text):
        return None
    if (not isinstance(immutable_prefix, str) or len(immutable_prefix) not in (3, 8)
            or not immutable_prefix.upper().startswith("MS1")):
        return None
    text = text.upper()
    locked = immutable_prefix.upper()
    if not text.startswith(locked) or any(c.lower() not in CHARSET and c != "?" for c in text[3:]):
        return None
    erasures = tuple(i for i, c in enumerate(text) if c == "?")
    if len(erasures) > 13:
        return None
    if len(erasures) > 8 and erasures != tuple(range(erasures[0], erasures[-1] + 1)):
        return None
    body = [CHARSET.find(c.lower()) for c in text[3:]]
    residue = _residue(_SHORT_SPEC, "ms", [max(v, 0) for v in body])
    positions = [47 - i for i in erasures]
    corrections = _error_corrections(_SHORT_SPEC, positions, residue, word_length=45)
    if corrections is None:
        return None
    repaired = list(reversed([max(v, 0) for v in body]))
    for reverse_index, addend in corrections:
        if not 0 <= reverse_index < 45:
            return None
        repaired[reverse_index] ^= addend
    corrected = "MS1" + "".join(CHARSET[v].upper() for v in reversed(repaired))
    if not corrected.startswith(locked):
        return None
    changed = tuple(i for i in range(48) if text[i] != corrected[i])
    substitutions = len(changed) - len(erasures)
    if not changed or (len(erasures) <= 8 and 2 * substitutions + len(erasures) > 8):
        return None
    if len(erasures) > 8 and substitutions:
        return None
    parsed = None
    try:
        parsed = parse_codex32_share(corrected)
        if parsed.share_idx.lower() == "s":
            wipe_codex32_share(parsed)
            parsed = validate_codex32_s_share(corrected)
        else:
            _parse_threshold(parsed.k)
    except Codex32InputError:
        return None
    finally:
        wipe_codex32_share(parsed)
    return Codex32Correction(text, corrected, changed, erasures)
