# Ascon-collision-search

This project verifies the validity of Ascon collinding trails and generates corresponding right pairs from SAT tools.

## Project Structure

```text
Ascon-collision-search/
├── code/
│   ├── RoundF_anf.py                # SP800-232 round core + Matrix/InvMatrix compatibility API
│   ├── ascon_algorithms.py          # Ascon-AEAD128 / Hash256 / XOF128 / CXOF128
│   ├── test_ascon_vectors.py        # ACVP prompt/expected parser + regression test runner
│   ├── diff_ddt_suit.py             # DDT and difference helper utilities
│   ├── sum.py                       # Active-S-box support projection helpers
│   ├── read_file_as2weight.py       # Parse trail log -> differential bit lists
│   ├── verify_model_right.py        # Build verify CNF model from trail constraints
│   ├── solve_verify_model.py        # Unified pipeline for direct/extend verification modes
│   ├── print_right_pair.py          # Replay/check right pair with optional strict window checks
│   ├── ban_sol.py                   # Add blocking clause to enumerate more solutions
│   └── run.sh                       # One-command runner for the default 4-round case
├── modelcnfs/                       # Generated CNF files
├── logs/
│   ├── 3round/                      # Round summary logs (kmt style)
│   ├── 4round/
│   ├── 5round/
│   └── tmp/                         # Temporary solver logs (auto-cleaned)
├── testvectors/
│   └── acvp/                        # Downloaded ACVP JSON vectors
├── trails/                          # Input trail logs (3/4/5 rounds)
└── result/
    ├── 3round/                      # 3-round right-pair outputs
    ├── 4round/                      # 4-round right-pair outputs
    └── 5round/                      # 5-round right-pair outputs
```

## Environment Setup

Always activate the Sage-enabled conda environment before running any script.

- Recommended activation rule:
  - `conda activate sage` (or your project environment name)
- Sage conda installation reference:
  - [https://doc.sagemath.org/html/en/installation/conda.html](https://doc.sagemath.org/html/en/installation/conda.html)

Follow this setup sequence:

1. Restart terminal.
2. Create environment:
  - `conda create -n sat sage python=X`
  - or `mamba create -n sage sage python=X`
3. Activate environment:
  - `conda activate sat`
  - or `mamba activate sat`
4. Install PySAT extras:
  - `pip install 'python-sat[aiger,approxmc,cryptosat,pblib]'`
5. Verify PySAT import:
  - `python -c "import pysat; print('pysat installed successfully')"`

## SAT Solver Setup

Install at least one supported SAT solver and ensure it is in `PATH` (or pass full binary path via `-sat`):

- Lingeling: [https://github.com/arminbiere/lingeling](https://github.com/arminbiere/lingeling)
- CaDiCal: [https://github.com/arminbiere/cadical](https://github.com/arminbiere/cadical)

The current scripts default to `cryptominisat5`; you may switch by setting `-sat` explicitly.

## Verification Workflow

### Quickstart (Default 4-round case)

All commands assume the environment is already activated.

```bash
cd /home/hnli/Ascon-collision-search
./code/run.sh
```

This uses:

- Trail input: `trails/W250_4R_S12_M31E33_K5_space_167.log`
- Rounds: `4`
- Weight tag: `78`
- Output right-pair directory: `result/4round`

### Mode 1: direct-n (build n-round model directly)

```bash
cd /home/hnli/Ascon-collision-search
python -u code/solve_verify_model.py \
  --mode direct-n \
  -r 4 \
  -w 78 \
  -m 0 \
  -satTrd 20 \
  -f modelcnfs \
  -sat cryptominisat5 \
  --trail trails/W250_4R_S12_M31E33_K5_space_167.log \
  --satlog-dir logs/tmp/direct-n \
  --rightpair-dir result/4round \
  --max-solutions 1
```

### Mode 2: short-then-extend (build n-1 then extend/check)

Forward extension example:

```bash
cd /home/hnli/Ascon-collision-search
python -u code/solve_verify_model.py \
  --mode short-then-extend \
  --extend-direction forward \
  --search-rounds 3 \
  -r 4 \
  -w 78 \
  -m 0 \
  -satTrd 20 \
  -f modelcnfs/short-then-extend-forward \
  -sat cryptominisat5 \
  --trail trails/W250_4R_S12_M31E33_K5_space_167.log \
  --satlog-dir logs/tmp/short-then-extend-forward \
  --rightpair-dir result/4round \
  --max-solutions 1 \
  --max-attempts 10
```

Backward extension example:

```bash
cd /home/hnli/Ascon-collision-search
python -u code/solve_verify_model.py \
  --mode short-then-extend \
  --extend-direction backward \
  --search-rounds 3 \
  -r 4 \
  -w 78 \
  -m 0 \
  -satTrd 20 \
  -f modelcnfs/short-then-extend-backward \
  -sat cryptominisat5 \
  --trail trails/W250_4R_S12_M31E33_K5_space_167.log \
  --satlog-dir logs/tmp/short-then-extend-backward \
  --rightpair-dir result/4round \
  --max-solutions 1 \
  --max-attempts 10
```

Wrapper script supports both modes through environment variables:

```bash
MODE=direct-n ./code/run.sh
MODE=short-then-extend EXTEND_DIRECTION=forward SEARCH_ROUNDS=3 ./code/run.sh
MODE=short-then-extend EXTEND_DIRECTION=backward SEARCH_ROUNDS=3 ./code/run.sh
```

## Expected Validation Target

For the specified 4-round trail above, successful model construction should print:

```text
New DC Verify Model Constructed:) var_num:3840, clause_num:22795
```

The generated right-pair log should match the same output style as:

- `result/4round/AS78_W250_4round_final_rightpair_no1.log`

## Legacy Log Note

- Old files under `result/` root such as `3round_final_rightpair_no1.log` and `4round_final_rightpair_no1.log` are historical artifacts.
- They may contain repeated `False! not satisfy` lines mixed with final markers and should not be treated as the current validation standard.
- Use round-specific outputs under `result/3round`, `result/4round`, and `result/5round` for current results.

## Notes on Extensibility

- Path customization is supported through CLI options:
  - `--mode`, `--extend-direction`, `--search-rounds`, `--trail`, `-f/--path`, `--satlog-dir`, `--rightpair-dir`, `-sat`
- Output file naming is trail-aware:
  - `AS{weight}_{trailTag}_{rounds}round_final_rightpair_no{index}.log`
- `--max-solutions` controls accepted right pairs; `--max-attempts` controls SAT candidates to test.
- Each run writes a kmt summary log to `logs/{round}round/` with model statistics and attempt progress.

## Ascon SP800-232 APIs (New)

Main implementation file: `code/ascon_algorithms.py`

Public APIs:

- `ascon_aead128_encrypt(key, nonce, associated_data, plaintext) -> (ciphertext, tag)`
- `ascon_aead128_decrypt(key, nonce, associated_data, ciphertext, tag) -> plaintext | None`
- `ascon_hash256(message) -> digest32`
- `ascon_xof128(message, out_len) -> digest`
- `ascon_cxof128(message, customization, out_len) -> digest`

Minimal example:

```python
from ascon_algorithms import ascon_aead128_encrypt, ascon_hash256

key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
nonce = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
ct, tag = ascon_aead128_encrypt(key, nonce, b"ad", b"plaintext")
digest = ascon_hash256(b"message")
```

## ACVP Vector Test (New)

Test runner: `code/test_ascon_vectors.py`

### 1) Pull ACVP vectors (prompt + expected)

```bash
cd /home/hnli/Ascon-collision-search
python - <<'PY'
import base64, json, os, subprocess
base='testvectors/acvp'
paths=[
'Ascon-AEAD128-SP800-232/prompt.json',
'Ascon-AEAD128-SP800-232/expectedResults.json',
'Ascon-Hash256-SP800-232/prompt.json',
'Ascon-Hash256-SP800-232/expectedResults.json',
'Ascon-XOF128-SP800-232/prompt.json',
'Ascon-XOF128-SP800-232/expectedResults.json',
'Ascon-CXOF128-SP800-232/prompt.json',
'Ascon-CXOF128-SP800-232/expectedResults.json',
]
for p in paths:
    meta=json.loads(subprocess.check_output(['gh','api',f'repos/usnistgov/ACVP-Server/contents/gen-val/json-files/{p}'], text=True))
    blob=json.loads(subprocess.check_output(['gh','api',meta['git_url'].replace('https://api.github.com/','')], text=True))
    raw=base64.b64decode(blob['content'].replace('\n',''))
    out=f'{base}/{p}'
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out,'wb').write(raw)
    print('saved', out, len(raw))
PY
```

### 2) Run sampled ACVP + inverse-matrix regression

```bash
cd /home/hnli/Ascon-collision-search
python code/test_ascon_vectors.py --max-per-group 20 --inverse-samples 128 --byte-aligned-only
```

The report includes: total/passed/failed/skipped counts, and top-N failed `(tgId, tcId)` details.

### 3) Full run (long)

```bash
python code/test_ascon_vectors.py --inverse-samples 512 --byte-aligned-only
```

## Verification Boundary

- `result/*` remains the SAT-based differential trail/right-pair workflow.
- `ascon_algorithms.py` + `test_ascon_vectors.py` is the SP800-232 algorithm and ACVP validation workflow.
- Current ACVP runner supports complete JSON parsing for all four algorithms; execution mode in this repo is byte-aligned (`--byte-aligned-only`) to keep behavior explicit and reproducible.

