"""Repeat a registered distribution experiment without altering its outputs."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
import numpy as np
import distribution_ablations as d
import joint_market_residuals as j


def run(experiment):
    out=j.ROOT/'research/experiments'/d.EXPERIMENTS[experiment]
    with tempfile.TemporaryDirectory(prefix='.'+experiment+'_repeat_',dir=out.parent) as directory:
        tmp=Path(directory)
        for name in ['PROTOCOL.md','registration_record.json']:shutil.copy2(out/name,tmp/name)
        d.run(experiment,tmp)
        checks={name:(out/name).read_bytes()==(tmp/name).read_bytes() for name in
            ['predictions.csv.gz','transform_audit.csv','provenance.json']}
        for name in ['marginal_probabilities.npz','example_joint_probabilities.npz']:
            a,b=np.load(out/name,allow_pickle=False),np.load(tmp/name,allow_pickle=False)
            checks[name+'_arrays']=a.files==b.files and all(np.array_equal(a[k],b[k]) for k in a.files)
        if experiment=='R003':checks['support_mask.npy']=(out/'support_mask.npy').read_bytes()==(tmp/'support_mask.npy').read_bytes()
        result=dict(experiment=experiment,all_passed=all(checks.values()),checks=checks,
            note='NPZ arrays, not archive metadata timestamps, are numerical model content.')
        (out/'deterministic_reproduction.json').write_text(json.dumps(result,indent=2)+'\n')
        if not result['all_passed']:raise AssertionError(result)
        print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',choices=list(d.EXPERIMENTS))
    run(parser.parse_args().experiment)
