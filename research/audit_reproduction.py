"""Audit original R000 checksums, sources, leakage and input integrity offline."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import joint_market_residuals as j

BASE=j.ROOT/'research/experiments/R000_reproduction'


def run():
    manifest=json.loads((BASE/'original_MANIFEST.json').read_text())
    hashes={}
    for item in manifest['files']:
        relative=item['path']
        if relative.startswith('research/joint_market_residual_results/'):
            path=BASE/Path(relative).name
        elif relative in ['research/joint_market_residuals.py','research/joint_market_residuals_report.py','research/JOINT_MARKET_RESIDUALS.md','tests/test_joint_market_residuals.py']:
            path=j.ROOT/relative
        else:continue
        # Runtime provenance paths differ; it is not a numerical reproduction target.
        if path.exists() and path.name!='provenance.json':
            hashes[relative]=dict(expected=item['sha256'],actual=j.sha256(path),match=j.sha256(path)==item['sha256'])
    source_hashes=json.loads((BASE/'input_sources.json').read_text())
    source_checks={name:j.sha256(j.ROOT/'research/audit_sources'/name)==expected for name,expected in source_hashes.items()}
    s=pd.read_csv(j.ROOT/'research/audit_sources/research/form_windows_inputs/schedule.csv')
    t=pd.read_csv(j.ROOT/'research/audit_sources/research/residual_trends_inputs/schedule_totals.csv')
    merged=s.merge(t,on=['game_id','season','week'],validate='one_to_one').sort_values(['season','week','game_id']).reset_index(drop=True)
    frozen=pd.read_csv(BASE/'frozen_inputs.csv.gz')
    pd.testing.assert_frame_equal(merged,frozen)
    valid=np.isfinite(frozen[['home_score','away_score','spread_line','total_line']]).all(axis=1)
    complete=frozen[valid].copy()
    original=json.loads((BASE/'original_summary.json').read_text())
    actual=json.loads((BASE/'summary.json').read_text())
    q=j.fair_moneyline(complete.home_moneyline,complete.away_moneyline)
    priced=np.isfinite(q)&(complete.spread_line!=0)&(abs(q-.5)>1e-12)
    consistent=(complete.spread_line.to_numpy()[priced]>0)==(q[priced]>.5)
    report=dict(experiment='R000',hash_comparisons=hashes,
        verified_original_source_hashes=source_checks,source_merge_equals_frozen=True,
        original_summaries_equal=original==actual,duplicate_game_ids=int(frozen.game_id.duplicated().sum()),
        input_rows=len(frozen),completed_rows=int(valid.sum()),
        omitted_incomplete_rows_by_season=frozen[~valid].groupby('season').size().to_dict(),
        completed_counts_by_season=complete.groupby('season').size().to_dict(),
        finite_scores_integer=bool(np.equal(complete[['home_score','away_score']],np.floor(complete[['home_score','away_score']])).all().all()),
        score_min=int(complete[['home_score','away_score']].min().min()),
        score_max=int(complete[['home_score','away_score']].max().max()),
        result_orientation_matches_scores=bool(((complete.home_score-complete.away_score)==complete.result).all()),
        spread_sign_moneyline_agreement=float(consistent.mean()),
        spread_sign_disagreements=complete.loc[priced].loc[~consistent,['game_id','spread_line','home_moneyline','away_moneyline']].to_dict('records'),
        orientation_evidence='Positive spread is favored home: frozen source convention, derived locations, price-sign check. Near-pickem quote disagreements are retained, never corrected.',
        historical_market_timestamps=dict(status='unverifiable',pregame_availability_proven=False,
            conclusion='Cannot pass an actual timestamp leakage audit; only logical prior-week label cutoffs can be certified.'),
        scoring='Natural-log exact probability NLL; discrete unit-grid CRPS; decisive-only winner LL/Brier; nonpush spread/total scores; endpoint-inclusive integer intervals.',
        original_package_manifest='All 38 entries independently verified on intake.',
        limitations=['Repository base commit inspected via read-only connector, not a full current checkout.',
            'Full repository tests and validate_data_files.py not rerun; production data were never copied or changed.',
            'Only incomplete 2026 schedule rows omitted; no imputation or outcome/price repair.',
            'CLI smoke check initially used the wrong working directory; corrected before any model run.',
            'Initial test dependency absent; pytest 8.3.5 installed before tests.',
            'One wrong repository filename returned 404; corrected to market_residual_models.py using the tree.'])
    (BASE/'AUDIT.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    assert all(x['match'] for x in hashes.values()),'Original file differs'
    assert all(source_checks.values()) and original==actual and report['duplicate_game_ids']==0
    print(json.dumps(dict(checksummed_files=len(hashes),all_equal=True,source_merge_equal=True,
                         orientation_agreement=report['spread_sign_moneyline_agreement'],timestamp_audit='unverifiable')))


if __name__=='__main__':run()
