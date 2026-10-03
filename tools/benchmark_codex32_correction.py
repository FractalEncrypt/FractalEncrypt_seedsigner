r"""Offline fixed-decoder benchmark using public BIP93 data only.

Run on a Pi with the SeedSigner dependencies already installed:
    python3 tools/benchmark_codex32_correction.py --iterations 1000
From the repository root in Windows PowerShell, use the existing environment:
    .\.venv\Scripts\python.exe tools/benchmark_codex32_correction.py --iterations 1000
No seed input, network access, firmware changes, or disk output are involved.
"""

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def benchmark(iterations=1000):
    started = perf_counter()
    from seedsigner.models.codex32_correction import suggest_correction
    from seedsigner.models.codex32_min import CHARSET
    import_ms = (perf_counter() - started) * 1000
    source = "MS12NAMEA320ZYXWVUTSRQPNMLKJHGFEDCAXRPP870HKKQRM"

    def damage(errors=(), erasures=()):
        values = list(source)
        for position in errors:
            values[position] = CHARSET[CHARSET.index(values[position].lower()) ^ 1].upper()
        for position in erasures:
            values[position] = "?"
        return "".join(values)

    cases = {
        "one_substitution": (damage([17]), True),
        "four_substitutions": (damage([5, 15, 25, 40]), True),
        "eight_erasures": (damage(erasures=[4, 9, 15, 21, 27, 33, 39, 45]), True),
        "mixed_two_substitutions_four_erasures": (damage([15, 40], [9, 21, 27, 33]), True),
        "thirteen_consecutive_erasures": (damage(erasures=range(15, 28)), True),
        "uncorrectable_five_substitutions": (damage([5, 15, 25, 35, 40]), False),
        "unsupported_fourteen_erasures": (damage(erasures=range(15, 29)), False),
    }
    results = []
    for name, (damaged, expected) in cases.items():
        times = []
        first_call_ms = None
        for attempt in range(iterations + 1):
            started = perf_counter()
            proposal = suggest_correction(damaged)
            elapsed_ms = (perf_counter() - started) * 1000
            if expected and (proposal is None or proposal.corrected != source):
                raise RuntimeError(f"Public-vector benchmark failed: {name}")
            if not expected and proposal is not None:
                raise RuntimeError(f"Unexpected benchmark correction: {name}")
            if attempt == 0:
                first_call_ms = elapsed_ms
            else:
                times.append(elapsed_ms)
        results.append({"case": name, "first_call_ms": first_call_ms,
                        "median_ms": statistics.median(times), "max_ms": max(times)})
    model_path = Path("/proc/device-tree/model")
    device = model_path.read_text().rstrip("\0") if model_path.exists() else platform.machine()
    return {"python": platform.python_version(), "device": device,
            "import_ms": import_ms, "iterations": iterations, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=1000)
    arguments = parser.parse_args()
    if not 1 <= arguments.iterations <= 10000:
        parser.error("iterations must be between 1 and 10000")
    try:
        results = benchmark(arguments.iterations)
    except ModuleNotFoundError as error:
        parser.exit(2, f"Missing dependency: {error.name}. Use the SeedSigner Python environment.\n"
                    "Windows PowerShell, from the repository root:\n"
                    "  .\\.venv\\Scripts\\python.exe tools/benchmark_codex32_correction.py --iterations 1000\n")
    print(json.dumps(results, indent=2))
