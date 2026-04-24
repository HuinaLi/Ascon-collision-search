import argparse
import sys

from RoundF_anf import *
from read_file_as2weight import generate_support_verifymodelpy_dclist, select_diff_window


def read_sol_ls(sol_path: str, solution_sign="s SATISFIABLE", line_split="v", state=320) -> list:
    """Read the first 320 SAT assignments as Value_in bits."""
    var_num = state
    with open(sol_path, "r") as f:
        contents = f.read()

    i = contents.find(solution_sign)
    if i < 0:
        return None

    i += len(solution_sign) + 1
    lines = contents[i:].split(line_split)
    sol = []

    for line in lines:
        vars_ = line.split()
        for var in vars_:
            if int(var) == 0:
                continue
            sol.append(0 if int(var) < 0 else 1)
        if len(sol) >= var_num:
            break
    sol = sol[:var_num]

    print("--------------------Print Solution Start-------------------------------")
    print("Value_in: ")
    print_state(sol)
    print("-------------------------Print Done :)--------------------------------")
    return sol


def to_ring_bits(value_bits, state=320):
    R = declare_ring([Block("X", state), "u"], globals())
    return [R(1) if value_bits[i] == 1 else R(0) for i in range(state)]


def _invert_lane_linear(y_lane, r0, r1):
    """Solve x from y for y[i] = x[i] + x[i-r0] + x[i-r1]."""
    size = 64
    A = [[0 for _ in range(size)] for _ in range(size)]
    b = [y_lane[i] for i in range(size)]

    for i in range(size):
        A[i][i] = 1
        A[i][(i - r0) % size] ^= 1
        A[i][(i - r1) % size] ^= 1

    row = 0
    for col in range(size):
        pivot = None
        for r in range(row, size):
            if A[r][col] == 1:
                pivot = r
                break
        if pivot is None:
            continue
        if pivot != row:
            A[row], A[pivot] = A[pivot], A[row]
            b[row], b[pivot] = b[pivot], b[row]

        for r in range(size):
            if r != row and A[r][col] == 1:
                for c in range(col, size):
                    A[r][c] ^= A[row][c]
                b[r] = b[r] + b[row]
        row += 1
        if row == size:
            break

    if row != size:
        raise ValueError("Linear layer matrix is not invertible for this lane.")
    return b


def _inverse_linear_layer(value_state):
    """Invert Ascon linear layer on a 320-bit alpha state."""
    shifts = [(19, 28), (61, 39), (1, 6), (10, 17), (7, 41)]
    out = [value_state[i] for i in range(320)]
    for lane_idx, (r0, r1) in enumerate(shifts):
        base = lane_idx * 64
        y_lane = value_state[base : base + 64]
        x_lane = _invert_lane_linear(y_lane, r0, r1)
        out[base : base + 64] = x_lane
    return out


def inverse_one_round_alpha_state(value_state, round_index):
    """Invert one full round alpha->alpha transition."""
    value_state = _inverse_linear_layer(value_state)
    value_state = InvSbox(value_state)
    value_state = addConst(value_state, round_index)
    return value_state


def reconstruct_trace_start_pair(
    candidate_value_in_bits,
    trace_window,
    trace_start_round,
    candidate_start_round,
    state=320,
):
    """Reconstruct (Value_in, Value_out) at trace start from candidate round."""
    if candidate_start_round < trace_start_round:
        raise ValueError("candidate_start_round must be >= trace_start_round.")

    candidate_offset = 2 * (candidate_start_round - trace_start_round)
    if candidate_offset >= len(trace_window):
        raise ValueError("candidate_start_round is out of the selected trace window.")

    value_in = to_ring_bits(candidate_value_in_bits, state=state)
    value_out = [value_in[i] + trace_window[candidate_offset][i] for i in range(state)]

    rounds_to_reverse = candidate_start_round - trace_start_round
    for step in range(rounds_to_reverse):
        round_idx = candidate_start_round - step - 1
        value_in = inverse_one_round_alpha_state(value_in, round_idx)
        value_out = inverse_one_round_alpha_state(value_out, round_idx)

    return value_in, value_out


def verify_trace_and_print(
    value_in,
    value_out,
    rounds,
    start_rnd,
    trace_window,
    strict_window_check=False,
    state=320,
):
    """Replay rounds, print trace, and verify endpoint (plus optional window checks)."""
    diff_start = [value_in[i] + value_out[i] for i in range(state)]
    expected_diff_start = trace_window[0]

    print("##############################################")
    print(f"alpha{start_rnd}: ")
    print_state(diff_start)
    print("##############################################")
    print(f"input Value_in state at round {start_rnd}: ")
    print_state(value_in)
    print("##############################################")
    print(f"input Value_out  state at round {start_rnd}: ")
    print_state(value_out)

    if strict_window_check and diff_start != expected_diff_start:
        return False

    print("start round function")
    for r in range(rounds):
        round_idx = r + start_rnd
        value_in = addConst(value_in, round_idx)
        value_out = addConst(value_out, round_idx)

        value_in = Sbox(value_in)
        value_out = Sbox(value_out)

        beta = [value_in[i] + value_out[i] for i in range(state)]
        print("##############################################")
        print(f"beta{round_idx}: ")
        print_state(beta)
        print("##############################################")
        print(f"Value_in{round_idx}^S: ")
        print_state(value_in)
        print("##############################################")
        print(f"Value_out{round_idx}^S: ")
        print_state(value_out)

        expected_beta = trace_window[2 * r + 1]
        if strict_window_check and beta != expected_beta:
            return False

        if r < rounds - 1:
            value_in = Matrix(value_in)
            value_out = Matrix(value_out)
            alpha_next = [value_in[i] + value_out[i] for i in range(state)]
            print("##############################################")
            print(f"alpha{round_idx + 1}: ")
            print_state(alpha_next)
            print("##############################################")
            print(f"Value_in{round_idx + 1}: ")
            print_state(value_in)
            print("##############################################")
            print(f"Value_out{round_idx + 1}: ")
            print_state(value_out)

            expected_alpha_next = trace_window[2 * r + 2]
            if strict_window_check and alpha_next != expected_alpha_next:
                return False

    final_diff = [value_in[i] + value_out[i] for i in range(state)]
    return final_diff == trace_window[-1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print right-pair details from SAT solution.")
    parser.add_argument("-r", "--rounds", type=int, required=True, help="Number of rounds to replay.")
    parser.add_argument("-s", "--spath", type=str, required=True, help="SAT solver output log path.")
    parser.add_argument("-m", "--stratrnd", type=int, default=0, help="Trace start round.")
    parser.add_argument("--trail", type=str, required=True, help="Trail log file path.")
    parser.add_argument(
        "--candidate-start-round",
        type=int,
        default=None,
        help="Round index where SAT candidate Value_in is defined. Defaults to stratrnd.",
    )
    parser.add_argument(
        "--strict-window-check",
        action="store_true",
        help="Check all intermediate alpha/beta values against the selected trail window.",
    )
    args = parser.parse_args()

    candidate_start_round = args.candidate_start_round
    if candidate_start_round is None:
        candidate_start_round = args.stratrnd

    diff_bit_lists = generate_support_verifymodelpy_dclist(args.trail)
    trace_window, _, _ = select_diff_window(diff_bit_lists, args.stratrnd, args.rounds)
    value_in_bits = read_sol_ls(args.spath)

    if value_in_bits is None:
        print("[ERROR] SAT solution marker not found.")
        sys.exit(1)

    try:
        value_in, value_out = reconstruct_trace_start_pair(
            candidate_value_in_bits=value_in_bits,
            trace_window=trace_window,
            trace_start_round=args.stratrnd,
            candidate_start_round=candidate_start_round,
        )
    except Exception as exc:
        print(f"[ERROR] Failed to reconstruct trace start pair: {exc}")
        sys.exit(1)

    ok = verify_trace_and_print(
        value_in=value_in,
        value_out=value_out,
        rounds=args.rounds,
        start_rnd=args.stratrnd,
        trace_window=trace_window,
        strict_window_check=args.strict_window_check,
    )
    if ok:
        print("check over")
        sys.exit(0)

    print("[ERROR] Output difference does not match trail endpoint.")
    sys.exit(1)
