"""Re-execute R001 in a disposable isolated research output directory."""
import json
import shutil
import tempfile
from pathlib import Path
import numpy as np
import joint_market_residuals as j
import tie_hurdle as t


def run():
    base=j.ROOT/'research/experiments/R000_reproduction'
    out=j.ROOT/'research/experiments/R001_tie_hurdle'
    with tempfile.TemporaryDirectory(prefix='.R001_determinism_',dir=out.parent) as directory:
        tmp=Path(directory)
        shutil.copy2(out/'PROTOCOL.md',tmp/'PROTOCOL.md')
        t.run(base,tmp)
        matches={name:(out/name).read_bytes()==(tmp/name).read_bytes()
                 for name in ['predictions.csv.gz','tie_fit_audit.csv','provenance.json']}
        for name in ['marginal_probabilities.npz','example_joint_probabilities.npz']:
            a,b=np.load(out/name),np.load(tmp/name)
            matches[name+'_arrays']=a.files==b.files and all(np.array_equal(a[k],b[k]) for k in a.files)
        report=dict(experiment='R001',checks=matches,all_passed=all(matches.values()),
                    note='NPZ arrays compared; ZIP container modification times are not semantic.')
        (out/'deterministic_reproduction.json').write_text(json.dumps(report,indent=2)+'\n')
        assert report['all_passed'],report
        print(json.dumps(report))


if __name__=='__main__':run()
