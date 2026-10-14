# Compact profile runtime and equality check

Frozen 2013-14 team-game boxes and schedule. Availability is omitted identically in both paths. This is a pipeline equivalence check, not model-performance evidence.

Full h4/h8/h16 path: 12.04s. Raw h8/h16 path: 5.90s. Observed speedup: 2.04× for profile generation only. Single run; not an end-to-end build benchmark.

Every retained profile column is bitwise equal. Final forecasts are bitwise equal for 2014 weeks 1, 8 and 17. Production configuration signature is unchanged. Sources and measurements are in `results.json`.

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/profile_runtime.py`.
