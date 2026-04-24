# Final Artifact Cleanup Checklist

This checklist is for manual cleanup after final validation. It does **not** delete files automatically.

## Suggested To Remove

- Runtime cache directories:
  - `**/__pycache__/`
  - `**/.pytest_cache/`
- Intermediate SAT construction outputs:
  - `modelcnfs/`
  - mode-specific temporary CNF subfolders under `modelcnfs/*`
- Process logs and temporary solver outputs:
  - `logs/`
  - SAT candidate trial logs that are not final deliverables
- Temporary downloaded test sources (if no longer needed):
  - `testvectors/acvp/` (only remove if ACVP rerun is not required)

## Suggested To Keep

- Core source code:
  - `code/RoundF_anf.py`
  - `code/ascon_algorithms.py`
  - `code/test_ascon_vectors.py`
  - existing SAT workflow scripts in `code/`
- Final right-pair outputs:
  - `result/3round/`, `result/4round/`, `result/5round/` final accepted logs
- Documentation:
  - `README.md`
  - `CLEANUP_CHECKLIST.md`
- Reproducible vector test reports exported by user (if generated)

## Safe Cleanup Order

1. Confirm final right-pair files and reports are archived.
2. Remove caches and temporary logs first.
3. Remove `modelcnfs/` and non-final SAT artifacts.
4. Remove `testvectors/acvp/` only when no further ACVP replay is needed.
