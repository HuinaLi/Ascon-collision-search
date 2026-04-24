import argparse
import math

from diff_ddt_suit import *
from sum import *


def extract_hex_lists_from_file(file_path):
    """Extract B and A hex-lists from a trail log file."""
    hex_lists = {"B": [], "A": []}
    current_list = None

    with open(file_path, "r") as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith("B["):
            current_list = "B"
            hex_lists[current_list].append([])
        elif line.startswith("A["):
            current_list = "A"
            hex_lists[current_list].append([])
        elif line.startswith("0x") and current_list is not None:
            hex_value = int(line, 16)
            formatted_hex = f"0x{hex_value:016x}"
            hex_lists[current_list][-1].append(formatted_hex)

    return hex_lists["B"], hex_lists["A"]


def ddt_intlist2binlistWithWeight(inlist: list, S_box_size: int = 32) -> list:
    binlist = []
    for l in inlist:
        diff_in = [int(x) for x in int2bin(l[0], 5)]
        diff_out = [int(x) for x in int2bin(l[1], 5)]
        tmp = diff_in + diff_out + [l[2]]
        binlist.append(tmp)
    return binlist


# Weight = 2*AS(B0) + w(A1) + w(A2) + w(A3)
def compute_wA1A2(B_bit_lists, A_bit_lists, relationDiffInOut, rounds):
    """Compute the weighted active S-box contribution for A1..A(r-2)."""
    pattern = [0, 0, 0]
    for r in range(rounds - 2):
        for x in range(64):
            pair = [A_bit_lists[r][index_xy(x, i)] for i in range(5)] + [B_bit_lists[r + 1][index_xy(x, i)] for i in range(5)]
            for vaildiff in relationDiffInOut:
                if pair == vaildiff[:10] and pair != [0 for _ in range(10)]:
                    n = vaildiff[10]
                    N = int(math.log(32 // n, 2))
                    pattern[N - 2] += 1
                else:
                    continue
    wA12 = 2 * pattern[0] + 3 * pattern[1] + 4 * pattern[2]
    return wA12


def compute_wA3(A_bit_lists):
    """Compute the weighted active S-box contribution for A_last."""
    pattern = [0, 0, 0]
    for x in range(64):
        pair = [A_bit_lists[-1][index_xy(x, i)] for i in range(5)]
        if pair == [0, 1, 1, 0, 0]:
            pattern[0] += 1
        if pair == [1, 1, 0, 0, 1] or pair == [0, 0, 0, 1, 1] or pair == [1, 1, 1, 0, 0] or pair == [1, 1, 1, 0, 1]:
            pattern[1] += 1
        if pair == [1, 0, 0, 1, 0] or pair == [0, 1, 0, 0, 1] or pair == [0, 1, 1, 0, 1] or pair == [1, 0, 1, 1, 0]:
            pattern[2] += 1
        else:
            continue
    wA3 = 2 * pattern[0] + 3 * pattern[1] + 4 * pattern[2]
    print(pattern)
    return wA3


def from_dclog_compute_weight(file_path, rounds):
    """Print the estimated total trail weight from a trail file."""
    B_list, A_list = extract_hex_lists_from_file(file_path)

    print(B_list)
    print(A_list)

    B_bit_lists = convert_diff_to_bit_list(B_list)
    A_bit_lists = convert_diff_to_bit_list(A_list)

    inlist = VaildDiffInOutWithWeight(AsconSbox)
    relationDiffInOut = ddt_intlist2binlistWithWeight(inlist)
    wA12 = compute_wA1A2(B_bit_lists, A_bit_lists, relationDiffInOut, rounds)
    wA3 = compute_wA3(A_bit_lists)

    print(6 + wA12 + wA3)


def generate_support_verifymodelpy_dclist(file_path):
    """Build the differential bit-list expected by verify_model_right.py."""
    B_list, A_list = extract_hex_lists_from_file(file_path)

    # Get A0 from B[0] by active-S-box support projection.
    bin_a0, hex_a0 = compute_as_number(B_list[0])

    Diff = []
    Diff.append(hex_a0)
    for i in range(len(B_list)):
        Diff.append(B_list[i])
        Diff.append(A_list[i])

    bin_last, hex_blast = compute_as_number(A_list[-1])
    Diff.append(hex_blast)
    diff_bit_lists = convert_diff_to_bit_list(Diff)

    return diff_bit_lists


def select_diff_window(diff_bit_lists, start_round, rounds):
    """Select a contiguous differential window for a round segment."""
    if rounds <= 0:
        raise ValueError("rounds must be positive.")
    if start_round < 0:
        raise ValueError("start_round must be non-negative.")

    start_idx = 2 * start_round
    end_idx = start_idx + 2 * rounds
    if end_idx > len(diff_bit_lists):
        raise ValueError(
            f"Requested window [{start_idx}:{end_idx}] exceeds diff list length {len(diff_bit_lists)}."
        )
    return diff_bit_lists[start_idx:end_idx], start_idx, end_idx


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse trail logs for model support.")
    parser.add_argument("--trail", required=True, help="Path to the trail log file.")
    parser.add_argument("--rounds", type=int, default=5, help="Round count used for weight estimation.")
    parser.add_argument("--weight-only", action="store_true", help="Only compute and print estimated trail weight.")
    args = parser.parse_args()

    if args.weight_only:
        from_dclog_compute_weight(args.trail, args.rounds)
    else:
        diff_bit_lists = generate_support_verifymodelpy_dclist(args.trail)
        print(len(diff_bit_lists))
