"""Copy a finished audit run into showcase/audits/<name>/ for the app: report, ledger, checked plan and the media of
the measured shots. meta.json (title, citation, licence, note) is written by hand once per paper and kept."""
import json
import shutil
import sys
from pathlib import Path

run, name = Path(sys.argv[1]), sys.argv[2]
dst = Path(__file__).resolve().parent.parent / "showcase" / "audits" / name
dst.mkdir(parents=True, exist_ok=True)
for f in ("report.json", "ledger.json", "plan_checked.json"):
    shutil.copy(run / f, dst / f)
rep = json.loads((run / "report.json").read_text())
for v in rep["videos"]:
    src = run / "units" / v["unit"]
    for f in ("receipt.mp4", "scale_evidence.png"):
        if (src / f).exists():
            (dst / "units" / v["unit"]).mkdir(parents=True, exist_ok=True)
            shutil.copy(src / f, dst / "units" / v["unit"] / f)
if len(sys.argv) > 3:                     # optional: a fault-injection run to show on the Calibration tab
    faults = Path(sys.argv[3]) / "FAULTS.md"
    shutil.copy(faults, dst.parent.parent / "faults.md")
print(f"exported {run} -> {dst}")
