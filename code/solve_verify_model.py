import argparse
import logging
import subprocess
import timeit
from datetime import datetime, timezone
from pathlib import Path

from read_file_as2weight import generate_support_verifymodelpy_dclist, select_diff_window
from verify_model_right import check_dc_validity_newmodel, generate_filename


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def run_satsolver(solver, nr_thread, cnf_file, log_file, timeout_seconds=1_000_000):
    """Run SAT solver and save stdout/stderr into log_file."""
    cmd = [solver, "-t", str(nr_thread), str(cnf_file)]
    try:
        with open(log_file, "w") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=True, timeout=timeout_seconds)
        return True, 0
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Solver timed out after {timeout_seconds} seconds.")
        return False, -1
    except subprocess.CalledProcessError as e:
        if e.returncode in [10, 20]:
            return True, e.returncode
        print(f"[ERROR] SAT solver failed with exit code {e.returncode}.")
        return False, e.returncode


def append_summary_line(summary_log: Path, text: str):
    with open(summary_log, "a") as f:
        f.write(text + "\n")


def check_satisfiability(log_file):
    """Check whether a SAT log contains a satisfiable marker."""
    try:
        with open(log_file, "r") as f:
            content = f.read()
        return "s SATISFIABLE" in content
    except FileNotFoundError:
        print(f"[ERROR] SAT log does not exist: {log_file}")
        return False


def run_command_capture(command, output_file):
    """Run a command and save stdout with header/footer timestamps."""
    started_at = datetime.now(timezone.utc).astimezone().isoformat()
    res = subprocess.run(command, capture_output=True, text=True)
    ended_at = datetime.now(timezone.utc).astimezone().isoformat()
    if res.returncode != 0:
        print(f"[ERROR] Command failed: {' '.join(command)}")
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr)
        return False

    with open(output_file, "w") as f:
        f.write(f"[TIMESTAMP][START] {started_at}\n")
        f.write(res.stdout)
        if res.stdout and not res.stdout.endswith("\n"):
            f.write("\n")
        f.write(f"[TIMESTAMP][END] {ended_at}\n")
    print(f"Output has been saved to {output_file}")
    return True


def build_rightpair_filename(weight, rounds, trail_path: Path, index):
    trail_tag = trail_path.stem.split("_")[0]
    return f"AS{weight}_{trail_tag}_{rounds}round_final_rightpair_no{index}.log"


def build_summary_filename(rounds, weight, trail_path: Path, mode_suffix: str):
    trail_tag = trail_path.stem.split("_")[0]
    return f"{rounds}R_AS{weight}_{trail_tag}_{mode_suffix}_kmt.log"


def resolve_verification_plan(mode, extend_direction, rounds, search_rounds, start_round):
    """Resolve SAT search segment and extension-check segment for selected mode."""
    if mode == "direct-n":
        return {
            "model_rounds": rounds,
            "model_start_round": start_round,
            "trace_rounds": rounds,
            "trace_start_round": start_round,
            "candidate_start_round": start_round,
            "strict_window_check": False,
            "search_segment": f"[{start_round}, {start_round + rounds - 1}]",
            "extend_check": "none (direct search over full range)",
        }

    if search_rounds is None:
        search_rounds = rounds - 1
    if search_rounds <= 0 or search_rounds >= rounds:
        raise ValueError("For short-then-extend, search_rounds must satisfy 1 <= search_rounds < rounds.")

    if extend_direction == "forward":
        model_start = start_round
        extend_desc = (
            f"search first {search_rounds} rounds [{model_start}, {model_start + search_rounds - 1}], "
            f"then extend/check round {model_start + search_rounds}"
        )
    else:
        # Search the suffix segment, then extend backward to check the preceding round.
        model_start = start_round + (rounds - search_rounds)
        extend_desc = (
            f"search last {search_rounds} rounds [{model_start}, {model_start + search_rounds - 1}], "
            f"then extend/check round {model_start - 1}"
        )

    return {
        "model_rounds": search_rounds,
        "model_start_round": model_start,
        "trace_rounds": rounds,
        "trace_start_round": start_round,
        "candidate_start_round": model_start,
        "strict_window_check": True,
        "search_segment": f"[{model_start}, {model_start + search_rounds - 1}]",
        "extend_check": extend_desc,
    }


def solve(args, trail_path: Path, cnf_dir: Path, rightpair_dir: Path, satlog_dir: Path, summary_dir: Path):
    diff_bit_lists = generate_support_verifymodelpy_dclist(str(trail_path))
    plan = resolve_verification_plan(
        mode=args.mode,
        extend_direction=args.extend_direction,
        rounds=args.rounds,
        search_rounds=args.search_rounds,
        start_round=args.stratrnd,
    )

    model_diff, _, _ = select_diff_window(
        diff_bit_lists=diff_bit_lists,
        start_round=plan["model_start_round"],
        rounds=plan["model_rounds"],
    )

    print(
        f"#Mode: {args.mode}, #Round: {args.rounds}, "
        f"#ModelRound: {plan['model_rounds']}, #as =: {args.weight}, START:"
    )

    ensure_dir(cnf_dir)
    ensure_dir(rightpair_dir)
    ensure_dir(satlog_dir)
    ensure_dir(summary_dir)

    mode_tag = "directn"
    if args.mode == "short-then-extend":
        mode_tag = f"short_{args.extend_direction}"
    summary_file = summary_dir / build_summary_filename(args.rounds, args.weight, trail_path, mode_tag)
    with open(summary_file, "w") as f:
        f.write("")
    append_summary_line(summary_file, "we have arrived here")
    append_summary_line(summary_file, f"#Round: {args.rounds}, #as =: {args.weight}, START:")
    append_summary_line(summary_file, f"#Mode: {args.mode}")
    append_summary_line(summary_file, f"#SearchSegment: {plan['search_segment']}")
    append_summary_line(summary_file, f"#ExtendCheck: {plan['extend_check']}")

    _, var_num, clause_num = check_dc_validity_newmodel(
        rounds=plan["model_rounds"],
        weight=args.weight,
        start_rnd=plan["model_start_round"],
        output_dir=str(cnf_dir),
        diff=model_diff,
    )
    append_summary_line(summary_file, f"New DC Verify Model Constructed:) var_num:{var_num}, clause_num:{clause_num}")

    model_prefix = generate_filename(str(cnf_dir), plan["model_rounds"], args.weight)
    model_cnf_filename = Path(model_prefix + ".cnf")

    script_dir = Path(__file__).resolve().parent
    print_right_pair_script = script_dir / "print_right_pair.py"
    ban_sol_script = script_dir / "ban_sol.py"

    found = 0
    attempt = 0
    # Measure only the SAT search-and-check loop time (exclude model construction).
    search_started_at = timeit.default_timer()
    while attempt < args.max_attempts and found < args.max_solutions:
        attempt += 1
        print(f"Solve START: no.{attempt}")
        append_summary_line(summary_file, f"START: no.{attempt}")
        solution_logfile = satlog_dir / f"{plan['model_rounds']}round_w{args.weight}_no{attempt}.log"

        start_solve = timeit.default_timer()
        ok, _ = run_satsolver(args.solver, args.thread, model_cnf_filename, solution_logfile)
        if not ok:
            try:
                solution_logfile.unlink(missing_ok=True)
            except Exception:
                pass
            break

        if not check_satisfiability(solution_logfile):
            print("UNSAT")
            end_solve = timeit.default_timer()
            logging.info("solve cost: %f s", end_solve - start_solve)
            print("solve cost: %f s" % (end_solve - start_solve))
            append_summary_line(summary_file, f"UNSAT at no.{attempt}")
            try:
                solution_logfile.unlink(missing_ok=True)
            except Exception:
                pass
            break

        end_solve = timeit.default_timer()
        logging.info("solve cost: %f s", end_solve - start_solve)
        print("solve cost: %f s" % (end_solve - start_solve))
        print("Find!")

        start_check = timeit.default_timer()
        rightpair_name = build_rightpair_filename(args.weight, args.rounds, trail_path, found + 1)
        rightpair_file = rightpair_dir / rightpair_name
        command3 = [
            "python",
            str(print_right_pair_script),
            "-r",
            str(plan["trace_rounds"]),
            "-m",
            str(plan["trace_start_round"]),
            "-s",
            str(solution_logfile),
            "--trail",
            str(trail_path),
            "--candidate-start-round",
            str(plan["candidate_start_round"]),
        ]
        if plan["strict_window_check"]:
            command3.append("--strict-window-check")

        is_valid = run_command_capture(command3, rightpair_file)
        end_check = timeit.default_timer()
        logging.info("check cost: %f s", end_check - start_check)
        print("check cost: %f s" % (end_check - start_check))
        if is_valid:
            found += 1
            append_summary_line(summary_file, f"VALID rightpair found at no.{attempt}")
            append_summary_line(summary_file, f"VALID rightpair has been saved to {rightpair_file.resolve()}")
            try:
                solution_logfile.unlink(missing_ok=True)
            except Exception:
                pass
            continue

        ban_sol_command = [
            "python",
            str(ban_sol_script),
            "-c",
            str(model_cnf_filename),
            "-s",
            str(solution_logfile),
            "-r",
            str(plan["model_rounds"]),
        ]
        result = subprocess.run(ban_sol_command, capture_output=True, text=True)
        if result.returncode != 0:
            print("[ERROR] ban_sol failed.")
            if result.stderr:
                print(result.stderr)
            append_summary_line(summary_file, f"[ERROR] ban_sol failed at no.{attempt}")
            try:
                solution_logfile.unlink(missing_ok=True)
            except Exception:
                pass
            break
        append_summary_line(summary_file, f"Candidate no.{attempt} rejected and banned.")
        try:
            solution_logfile.unlink(missing_ok=True)
        except Exception:
            pass

    search_elapsed = timeit.default_timer() - search_started_at
    append_summary_line(summary_file, f"Search runtime(excluding model build): {search_elapsed:.6f} s")
    append_summary_line(summary_file, f"__________End____________ (found {found} right pair(s))")
    print("search runtime(excluding model build): %f s" % search_elapsed)
    print(f"__________End____________ (found {found} right pair(s))")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SAT verification and export right pairs.")
    parser.add_argument(
        "--mode",
        choices=["direct-n", "short-then-extend"],
        default="direct-n",
        help="Verification mode.",
    )
    parser.add_argument(
        "--extend-direction",
        choices=["forward", "backward"],
        default="forward",
        help="Extension direction for short-then-extend mode.",
    )
    parser.add_argument("--search-rounds", type=int, default=None, help="Round count used for SAT model in short-then-extend mode.")
    parser.add_argument("-r", "--rounds", type=int, required=True, help="Target total number of rounds.")
    parser.add_argument("-f", "--path", type=str, default=None, help="CNF output directory.")
    parser.add_argument("-w", "--weight", type=int, required=True, help="Weight tag used in file names.")
    parser.add_argument("-sat", "--solver", type=str, default="cryptominisat5", help="SAT solver executable path.")
    parser.add_argument("-satTrd", "--thread", type=int, default=20, help="Number of SAT solver threads.")
    parser.add_argument("-m", "--stratrnd", type=int, default=0, help="Trace start round.")
    parser.add_argument("--trail", type=str, required=True, help="Trail log file path.")
    parser.add_argument("--rightpair-dir", type=str, default=None, help="Output directory for right-pair logs.")
    parser.add_argument("--satlog-dir", type=str, default=None, help="Output directory for SAT logs.")
    parser.add_argument("--max-solutions", type=int, default=1, help="Maximum number of valid right pairs to extract.")
    parser.add_argument("--max-attempts", type=int, default=20, help="Maximum SAT assignments to test.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    trail_path = Path(args.trail).resolve()

    mode_suffix = "direct-n"
    if args.mode == "short-then-extend":
        mode_suffix = f"short-then-extend-{args.extend_direction}"

    cnf_dir = Path(args.path) if args.path else project_root / "modelcnfs" / mode_suffix
    satlog_dir = Path(args.satlog_dir) if args.satlog_dir else project_root / "logs" / "tmp" / mode_suffix
    rightpair_dir = Path(args.rightpair_dir) if args.rightpair_dir else project_root / "result" / f"{args.rounds}round"
    summary_dir = project_root / "logs" / f"{args.rounds}round"

    solve(
        args=args,
        trail_path=trail_path,
        cnf_dir=cnf_dir,
        rightpair_dir=rightpair_dir,
        satlog_dir=satlog_dir,
        summary_dir=summary_dir,
    )
