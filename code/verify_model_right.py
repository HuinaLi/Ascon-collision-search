import argparse
import os
import sys

from RoundF_anf import *
from read_file_as2weight import generate_support_verifymodelpy_dclist, select_diff_window
from sage.sat.converters.polybori import CNFEncoder
from sage.sat.solvers.dimacs import DIMACS


# cnf_b0toa1 maps [B_x,y, B_x-r0,y, B_x-r1,y, A_x,y] with 8 clauses.
cnf_b0toa1 = [
    [1, 2, 3, -4],
    [1, 2, 4, -3],
    [1, 3, 4, -2],
    [2, 3, 4, -1],
    [1, -2, -3, -4],
    [2, -1, -3, -4],
    [3, -1, -2, -4],
    [4, -1, -2, -3],
]

# Ascon S-box relation in CNF (46 clauses).
cnf_chi = [
    [2, 3, 5, 8],
    [1, 10, 4, -2],
    [1, 5, 7, -6],
    [1, 8, 9, -5],
    [10, 2, 5, -4],
    [2, 3, 9, -1],
    [2, 4, 5, -10],
    [4, 5, 6, -2],
    [4, 8, 9, -7],
    [1, 2, 4, 7, 8],
    [1, 6, -7, -8],
    [1, 7, -10, -4],
    [10, 2, -3, -8],
    [10, 4, -5, -6],
    [3, 6, -2, -9],
    [5, 8, -1, -7],
    [5, 8, -2, -3],
    [5, 9, -4, -8],
    [6, 7, -1, -5],
    [6, 9, -4, -5],
    [7, 9, -1, -5],
    [7, 9, -2, -3],
    [1, 10, 2, 3, -9],
    [10, 2, 4, 6, -9],
    [10, 6, 7, 8, -2],
    [1, -5, -8, -9],
    [10, -1, -2, -4],
    [2, -1, -3, -9],
    [3, -2, -6, -8],
    [4, -1, -10, -2],
    [4, -5, -6, -7],
    [5, -2, -4, -6],
    [8, -4, -7, -9],
    [1, 2, 9, -6, -7],
    [10, 2, 7, -1, -6],
    [2, 3, 4, -5, -8],
    [2, 6, 7, -10, -3],
    [10, 4, -3, -7, -8],
    [3, 6, -10, -4, -7],
    [6, 7, -10, -3, -8],
    [7, 8, -3, -5, -6],
    [1, -10, -3, -7, -9],
    [3, -1, -4, -6, -9],
    [9, -10, -3, -4, -5],
    [4, 7, 8, -2, -6, -9],
    [-1, -10, -5, -7, -9],
]


def generate_filename(output_dir, rounds, weight):
    return f"{output_dir}/{rounds}round_w{weight}"


def check_dc_validity_newmodel(rounds, weight, start_rnd, output_dir, diff, state=320, rate=64):
    expected_diff_len = 2 * rounds
    if len(diff) < expected_diff_len:
        raise ValueError(f"diff length is {len(diff)}, but at least {expected_diff_len} entries are required for {rounds} rounds.")

    R = declare_ring([Block("X", (3 * rounds) * state), "u"], globals())
    c_vars = [[R(X(state * r + i)) for i in range(state)] for r in range(rounds)]
    a_vars = [[R(X(state * r + rounds * state + i)) for i in range(state)] for r in range(rounds)]
    b_vars = [[R(X(state * r + 2 * rounds * state + i)) for i in range(state)] for r in range(rounds)]

    # c0--pc--a0--ps-->b0--pl-->c1--pc--a1--ps-->b1--pl-->...
    Q = set()
    for r in range(rounds):
        c_vars[r] = addConst(c_vars[r], r + start_rnd)
        for i in range(state):
            Q.add(c_vars[r][i] + a_vars[r][i])

    for r in range(rounds):
        for i in range(state):
            a_vars[r][i] += diff[2 * r][i] * R(u)

        a_vars[r] = Sbox(a_vars[r])

        for i in range(state):
            d = a_vars[r][i] / R(u)
            if diff[2 * r + 1][i] == 1:
                if d == 0:
                    print(diff[2 * r + 1][i], d)
                    print("Impossible")
                    raise ValueError("Impossible differential constraints.")
                if d != 1:
                    Q.add(a_vars[r][i] / R(u) + 1)
            else:
                if d == 1:
                    print(diff[2 * r + 1][i], d)
                    print("Impossible")
                    raise ValueError("Impossible differential constraints.")
                if d != 0:
                    Q.add(a_vars[r][i] / R(u))

    filename = generate_filename(output_dir, rounds, weight) + ".cnf"
    solver = DIMACS(filename=filename)
    e = CNFEncoder(solver, R)
    e(list(Q))
    solver.write()

    with open(filename, "r") as f:
        cnf_info = f.readline().split(" ")
        var_num, clause_num = int(cnf_info[2]), int(cnf_info[3])
        ls_cnf = f.read()

    constraint_cnf = ""
    row = [0] * 4
    for r in range(rounds - 1):
        for y in range(5):
            for x in range(rate):
                if y == 0:
                    row = [(2 * rounds + r) * state + index_xy(x, y), (2 * rounds + r) * state + index_xy(x - 19, y), (2 * rounds + r) * state + index_xy(x - 28, y), (r + 1) * state + index_xy(x, y)]
                if y == 1:
                    row = [(2 * rounds + r) * state + index_xy(x, y), (2 * rounds + r) * state + index_xy(x - 61, y), (2 * rounds + r) * state + index_xy(x - 39, y), (r + 1) * state + index_xy(x, y)]
                if y == 2:
                    row = [(2 * rounds + r) * state + index_xy(x, y), (2 * rounds + r) * state + index_xy(x - 1, y), (2 * rounds + r) * state + index_xy(x - 6, y), (r + 1) * state + index_xy(x, y)]
                if y == 3:
                    row = [(2 * rounds + r) * state + index_xy(x, y), (2 * rounds + r) * state + index_xy(x - 10, y), (2 * rounds + r) * state + index_xy(x - 17, y), (r + 1) * state + index_xy(x, y)]
                if y == 4:
                    row = [(2 * rounds + r) * state + index_xy(x, y), (2 * rounds + r) * state + index_xy(x - 7, y), (2 * rounds + r) * state + index_xy(x - 41, y), (r + 1) * state + index_xy(x, y)]

                for i in range(len(cnf_b0toa1)):
                    cnf_clause = ""
                    for j in range(len(cnf_b0toa1[i])):
                        temp = int(cnf_b0toa1[i][j])
                        if temp > 0:
                            cnf_clause += str(row[temp - 1] + 1) + " "
                        else:
                            cnf_clause += str(-1 * row[abs(temp + 1)] - 1) + " "
                    cnf_clause += "0"
                    constraint_cnf += cnf_clause + "\n"
                    clause_num += 1

    row = [0] * 10
    for r in range(rounds):
        for x in range(rate):
            row = [
                (rounds + r) * state + index_xy(x, 0),
                (rounds + r) * state + index_xy(x, 1),
                (rounds + r) * state + index_xy(x, 2),
                (rounds + r) * state + index_xy(x, 3),
                (rounds + r) * state + index_xy(x, 4),
                (2 * rounds + r) * state + index_xy(x, 0),
                (2 * rounds + r) * state + index_xy(x, 1),
                (2 * rounds + r) * state + index_xy(x, 2),
                (2 * rounds + r) * state + index_xy(x, 3),
                (2 * rounds + r) * state + index_xy(x, 4),
            ]
            for i in range(len(cnf_chi)):
                cnf_clause = ""
                for j in range(len(cnf_chi[i])):
                    temp = int(cnf_chi[i][j])
                    if temp > 0:
                        cnf_clause += str(row[temp - 1] + 1) + " "
                    else:
                        cnf_clause += str(-1 * row[abs(temp + 1)] - 1) + " "
                cnf_clause += "0"
                constraint_cnf += cnf_clause + "\n"
                clause_num += 1

    with open(filename, "w") as f:
        f.write(f"p cnf {var_num} {clause_num}\n")
        f.write(ls_cnf)
        f.write(constraint_cnf)

    print(f"New DC Verify Model Constructed:) var_num:{var_num - 1}, clause_num:{clause_num}")
    return filename, var_num - 1, clause_num


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construct the CNF verify model from a trail file.")
    parser.add_argument("-r", "--rounds", type=int, required=True, help="Number of rounds.")
    parser.add_argument("-f", "--path", type=str, required=True, help="CNF output directory.")
    parser.add_argument("-w", "--weight", type=int, required=True, help="Weight tag used in output file naming.")
    parser.add_argument("-m", "--stratrnd", type=int, default=0, help="Start round index.")
    parser.add_argument("--trail", type=str, required=True, help="Trail log file path.")
    args = parser.parse_args()

    os.makedirs(args.path, exist_ok=True)
    diff_bit_lists = generate_support_verifymodelpy_dclist(args.trail)
    diff_slice, _, _ = select_diff_window(
        diff_bit_lists=diff_bit_lists,
        start_round=args.stratrnd,
        rounds=args.rounds,
    )

    try:
        check_dc_validity_newmodel(args.rounds, args.weight, args.stratrnd, args.path, diff_slice)
    except Exception as exc:
        print(f"[ERROR] Failed to construct verify model: {exc}")
        sys.exit(1)
