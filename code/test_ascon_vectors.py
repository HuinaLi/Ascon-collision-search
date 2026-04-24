"""
ACVP vector tests for Ascon SP 800-232 implementations.
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from RoundF_anf import InvMatrix, Matrix
from ascon_algorithms import (
    ascon_aead128_decrypt,
    ascon_aead128_decrypt_with_taglen,
    ascon_aead128_encrypt,
    ascon_cxof128,
    ascon_hash256,
    ascon_xof128,
)


ACVP_BASE_URL = "https://raw.githubusercontent.com/usnistgov/ACVP-Server/master/gen-val/json-files"
ACVP_FOLDERS = {
    "Ascon-AEAD128": "Ascon-AEAD128-SP800-232",
    "Ascon-Hash256": "Ascon-Hash256-SP800-232",
    "Ascon-XOF128": "Ascon-XOF128-SP800-232",
    "Ascon-CXOF128": "Ascon-CXOF128-SP800-232",
}


@dataclass
class CaseFailure:
    algorithm: str
    tg_id: int
    tc_id: int
    reason: str


@dataclass
class TestSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    def add(self, ok: bool):
        self.total += 1
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def add_skip(self):
        self.skipped += 1


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ensure_acvp_vectors(target_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    for folder in ACVP_FOLDERS.values():
        dst = target_dir / folder
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("prompt.json", "expectedResults.json"):
            out = dst / name
            if out.exists():
                continue
            url = f"{ACVP_BASE_URL}/{folder}/{name}"
            data = _fetch_json(url)
            out.write_text(json.dumps(data), encoding="utf-8")


def _load_case_pair(base: Path, algorithm_name: str) -> tuple[dict, dict]:
    folder = ACVP_FOLDERS[algorithm_name]
    prompt = json.loads((base / folder / "prompt.json").read_text(encoding="utf-8"))
    expected = json.loads((base / folder / "expectedResults.json").read_text(encoding="utf-8"))
    return prompt, expected


def _bytes_from_hex_bits(hex_string: str, bit_len: int | None = None) -> bytes:
    hex_string = hex_string or ""
    if bit_len is None:
        return bytes.fromhex(hex_string)
    data = bytes.fromhex(hex_string)
    byte_len = (bit_len + 7) // 8
    data = data[:byte_len]
    if bit_len % 8 == 0:
        return data
    if not data:
        return b""
    rem = bit_len % 8
    mask = (0xFF << (8 - rem)) & 0xFF
    return data[:-1] + bytes([data[-1] & mask])


def _hex(data: bytes) -> str:
    return data.hex()


def _expected_lookup(expected: dict) -> dict[tuple[int, int], dict]:
    out = {}
    for tg in expected["testGroups"]:
        tg_id = tg["tgId"]
        for tc in tg["tests"]:
            out[(tg_id, tc["tcId"])] = tc
    return out


def _select_tests(tests: list[dict], limit: int | None) -> list[dict]:
    if limit is None or limit >= len(tests):
        return tests
    return tests[:limit]


def run_aead_vectors(
    prompt: dict, expected: dict, max_per_group: int | None, byte_aligned_only: bool
) -> tuple[TestSummary, list[CaseFailure]]:
    summary = TestSummary()
    failures: list[CaseFailure] = []
    exp = _expected_lookup(expected)

    for tg in prompt["testGroups"]:
        direction = str(tg.get("direction", "encrypt")).lower()
        tg_id = tg["tgId"]
        tests = _select_tests(tg["tests"], max_per_group)
        for tc in tests:
            tc_id = tc["tcId"]
            et = exp[(tg_id, tc_id)]
            try:
                if byte_aligned_only and (
                    tc.get("adLen", 0) % 8 != 0 or tc.get("payloadLen", 0) % 8 != 0 or tc.get("tagLen", 0) % 8 != 0
                ):
                    summary.add_skip()
                    continue
                key = _bytes_from_hex_bits(tc["key"])
                nonce = _bytes_from_hex_bits(tc["nonce"])
                ad = _bytes_from_hex_bits(tc.get("ad", ""), tc.get("adLen"))
                if direction == "encrypt":
                    pt = _bytes_from_hex_bits(tc.get("pt", ""), tc.get("payloadLen"))
                    got_ct, got_tag = ascon_aead128_encrypt(key, nonce, ad, pt)
                    exp_ct = str(et.get("ct", "")).lower()
                    exp_tag = str(et.get("tag", "")).lower()
                    tag_bytes = tc.get("tagLen", 128) // 8
                    ok = _hex(got_ct).lower() == exp_ct and _hex(got_tag[:tag_bytes]).lower() == exp_tag
                    if not ok:
                        failures.append(
                            CaseFailure(
                                "Ascon-AEAD128",
                                tg_id,
                                tc_id,
                                f"encrypt mismatch: got ct={_hex(got_ct)} tag={_hex(got_tag[:tag_bytes])} expected ct={et.get('ct','')} tag={et.get('tag','')}",
                            )
                        )
                    summary.add(ok)
                else:
                    ct = _bytes_from_hex_bits(tc.get("ct", ""), tc.get("payloadLen"))
                    tag = _bytes_from_hex_bits(tc.get("tag", ""), tc.get("tagLen"))
                    if tc.get("tagLen", 128) == 128:
                        dec = ascon_aead128_decrypt(key, nonce, ad, ct, tag)
                    else:
                        dec = ascon_aead128_decrypt_with_taglen(key, nonce, ad, ct, tag, tc.get("tagLen", 128))

                    if "testPassed" in et:
                        should_pass = bool(et["testPassed"])
                        ok = (dec is not None) == should_pass
                    elif "pt" in et:
                        expected_pt = _bytes_from_hex_bits(et["pt"], tc.get("payloadLen"))
                        ok = dec is not None and dec == expected_pt
                    else:
                        ok = dec is not None

                    if not ok:
                        failures.append(
                            CaseFailure(
                                "Ascon-AEAD128",
                                tg_id,
                                tc_id,
                                f"decrypt mismatch: got={None if dec is None else _hex(dec)} expected={et}",
                            )
                        )
                    summary.add(ok)
            except Exception as exc:  # pylint: disable=broad-except
                failures.append(CaseFailure("Ascon-AEAD128", tg_id, tc_id, f"exception: {exc}"))
                summary.add(False)
    return summary, failures


def run_hash_like_vectors(
    algorithm_name: str, prompt: dict, expected: dict, max_per_group: int | None, byte_aligned_only: bool
) -> tuple[TestSummary, list[CaseFailure]]:
    summary = TestSummary()
    failures: list[CaseFailure] = []
    exp = _expected_lookup(expected)

    runners: dict[str, Callable[[dict], bytes]] = {
        "Ascon-Hash256": lambda tc: ascon_hash256(_bytes_from_hex_bits(tc.get("msg", ""), tc.get("len"))),
        "Ascon-XOF128": lambda tc: ascon_xof128(
            _bytes_from_hex_bits(tc.get("msg", ""), tc.get("len")), tc.get("outLen", 0) // 8
        ),
        "Ascon-CXOF128": lambda tc: ascon_cxof128(
            _bytes_from_hex_bits(tc.get("msg", ""), tc.get("len")),
            _bytes_from_hex_bits(tc.get("cs", ""), tc.get("csLen")),
            tc.get("outLen", 0) // 8,
        ),
    }

    run_case = runners[algorithm_name]
    for tg in prompt["testGroups"]:
        tg_id = tg["tgId"]
        tests = _select_tests(tg["tests"], max_per_group)
        for tc in tests:
            tc_id = tc["tcId"]
            et = exp[(tg_id, tc_id)]
            try:
                if byte_aligned_only and (
                    tc.get("len", 0) % 8 != 0
                    or (tc.get("outLen", 0) % 8 != 0)
                    or (tc.get("csLen", 0) % 8 != 0)
                ):
                    summary.add_skip()
                    continue
                got = run_case(tc)
                got_hex = _hex(got)
                ok = got_hex.lower() == str(et.get("md", "")).lower()
                if not ok:
                    failures.append(
                        CaseFailure(algorithm_name, tg_id, tc_id, f"hash mismatch: got={got_hex} expected={et.get('md','')}")
                    )
                summary.add(ok)
            except Exception as exc:  # pylint: disable=broad-except
                failures.append(CaseFailure(algorithm_name, tg_id, tc_id, f"exception: {exc}"))
                summary.add(False)
    return summary, failures


def _bit_diffs(a: list[int], b: list[int]) -> list[tuple[int, int]]:
    out = []
    for idx, (va, vb) in enumerate(zip(a, b)):
        if va != vb:
            lane, bit = divmod(idx, 64)
            out.append((lane, bit))
    return out


def run_inverse_matrix_regression(samples: int, seed: int = 12345) -> tuple[TestSummary, list[CaseFailure]]:
    rng = random.Random(seed)
    summary = TestSummary()
    failures: list[CaseFailure] = []

    fixed_samples = [
        [0] * 320,
        [1] * 320,
        [1 if i % 2 == 0 else 0 for i in range(320)],
        [1 if (i // 64) == 2 else 0 for i in range(320)],
    ]
    dynamic_samples = [[rng.randint(0, 1) for _ in range(320)] for _ in range(samples)]
    all_samples = fixed_samples + dynamic_samples

    for idx, x in enumerate(all_samples):
        y = Matrix(x)
        back_1 = InvMatrix(y)
        ok_1 = back_1 == x
        summary.add(ok_1)
        if not ok_1:
            diffs = _bit_diffs(back_1, x)[:10]
            failures.append(CaseFailure("InvMatrixRegression", -1, idx, f"InvMatrix(Matrix(x)) != x, diffs={diffs}"))

        z = InvMatrix(x)
        back_2 = Matrix(z)
        ok_2 = back_2 == x
        summary.add(ok_2)
        if not ok_2:
            diffs = _bit_diffs(back_2, x)[:10]
            failures.append(CaseFailure("InvMatrixRegression", -1, idx, f"Matrix(InvMatrix(x)) != x, diffs={diffs}"))

    return summary, failures


def print_report(
    report: dict[str, TestSummary],
    failures: list[CaseFailure],
    max_failure_print: int,
):
    total = sum(v.total for v in report.values())
    passed = sum(v.passed for v in report.values())
    failed = sum(v.failed for v in report.values())
    print("=== Ascon ACVP + inverse-matrix test report ===")
    for name, item in report.items():
        print(f"{name}: total={item.total}, passed={item.passed}, failed={item.failed}, skipped={item.skipped}")
    print(f"ALL: total={total}, passed={passed}, failed={failed}, skipped={sum(v.skipped for v in report.values())}")

    if failures:
        print(f"\nFirst {min(max_failure_print, len(failures))} failures:")
        for item in failures[:max_failure_print]:
            print(f"- [{item.algorithm}] tgId={item.tg_id} tcId={item.tc_id}: {item.reason}")


def main():
    parser = argparse.ArgumentParser(description="Run ACVP vector tests for Ascon SP 800-232 implementations.")
    parser.add_argument(
        "--acvp-dir",
        type=Path,
        default=Path("/home/hnli/Ascon-collision-search/testvectors/acvp"),
        help="Directory storing ACVP prompt/expected JSON files.",
    )
    parser.add_argument("--download", action="store_true", help="Download missing ACVP files from ACVP-Server.")
    parser.add_argument("--max-per-group", type=int, default=None, help="Limit tests per group for quick checks.")
    parser.add_argument("--inverse-samples", type=int, default=128, help="Random samples for inverse matrix regression.")
    parser.add_argument("--max-failure-print", type=int, default=10, help="How many failure details to print.")
    parser.add_argument(
        "--byte-aligned-only",
        action="store_true",
        help="Only run ACVP cases where all bit lengths are byte-aligned.",
    )
    args = parser.parse_args()

    if args.download:
        ensure_acvp_vectors(args.acvp_dir)

    report: dict[str, TestSummary] = {}
    failures: list[CaseFailure] = []

    # AEAD
    p, e = _load_case_pair(args.acvp_dir, "Ascon-AEAD128")
    s, f = run_aead_vectors(p, e, args.max_per_group, args.byte_aligned_only)
    report["Ascon-AEAD128"] = s
    failures.extend(f)

    # Hash/XOF/CXOF
    for name in ("Ascon-Hash256", "Ascon-XOF128", "Ascon-CXOF128"):
        p, e = _load_case_pair(args.acvp_dir, name)
        s, f = run_hash_like_vectors(name, p, e, args.max_per_group, args.byte_aligned_only)
        report[name] = s
        failures.extend(f)

    # inverse matrix regression
    s, f = run_inverse_matrix_regression(samples=args.inverse_samples)
    report["InverseMatrixRegression"] = s
    failures.extend(f)

    print_report(report, failures, args.max_failure_print)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
