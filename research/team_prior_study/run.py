"""Test 45: per-team, coach and QB shrinkage targets vs the league prior; see research/TEAM_PRIOR.md.

    python research/team_prior_study/run.py      # rebuild every table (no network; about 15-25 minutes)

Reads the committed box scores and schedule (research/form_windows_inputs), the frozen coach/QB columns
(research/team_prior_inputs) and committed production reconstructions. Large intermediates go to
research/team_prior_work/ (not committed); the tables in research/team_prior_results/ are copied from there.
Never writes data/, public/ or the ledger. Exploratory development evidence on exposed seasons only.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from paths import INPUTS, RESULTS, ROOT, WORK

HERE = Path(__file__).resolve().parent
STEPS = ['build_profiles.py', 'stat_eval.py', 'stat_summary.py', 'market_test.py', 'market_tables.py',
         'retention_build.py', 'retention_stat_eval.py', 'retention_stat_summary.py',
         'retention_market_test.py', 'retention_market_tables.py']
KEEP = ['stat_pred_pooled_*.csv', 'stat_pred_raw_*.csv', 'stat_pred_recal_*.csv', 'stat_pred_scale.csv',
        'stat_pred_meta.json', 'persistence_table.csv', 'persistence_reliability.csv',
        'market_test_table_*.csv', 'market_test_summary.csv', 'market_test_results.json', 'market_test_predictions.csv.gz',
        'retention_build_coverage.csv', 'retention_build_profile_shift.csv', 'retention_stat_pred_overview.csv',
        'retention_stat_pred_pooled_*.csv', 'retention_stat_pred_stack_b2.csv', 'retention_market_test_table_*.csv',
        'retention_market_test_summary.csv', 'retention_market_test_vs_control.csv',
        'retention_market_test_by_continuity.csv', 'retention_market_test_results.json',
        'retention_market_test_predictions.csv.gz', 'team_prior_validation.json', 'retention_validation.json']
SOURCES = [ROOT/'nfl_model.py', ROOT/'research/TEAM_PRIOR.md', ROOT/'research/form_windows_inputs/boxes.csv',
           ROOT/'research/form_windows_inputs/schedule.csv', INPUTS/'games_coaches_qbs.csv',
           ROOT/'research/out_of_sample_results/predictions.csv',
           ROOT/'research/production_adoption_results/historical_reproduction.csv',
           ROOT/'research/out_of_sample_results/frozen_features_2013_2020.csv.gz',
           ROOT/'research/shrinkage_results/frozen_training_features.csv.gz']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    for step in STEPS:
        print(f'== {step}', flush=True)
        subprocess.run([sys.executable, str(HERE/step)], check=True, cwd=ROOT)
    RESULTS.mkdir(parents=True, exist_ok=True)
    kept = sorted({p for pattern in KEEP for p in WORK.glob(pattern)})
    for p in kept:
        shutil.copyfile(p, RESULTS/p.name)
    prov = {str(p.relative_to(ROOT)): sha(p) for p in [*sorted(HERE.glob('*.py')), *SOURCES]}
    prov['outputs'] = {p.name: sha(RESULTS/p.name) for p in kept}
    (RESULTS/'provenance.json').write_text(json.dumps(prov, indent=2)+'\n')
    print(f'copied {len(kept)} tables to {RESULTS.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
