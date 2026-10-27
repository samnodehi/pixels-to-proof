import argparse
import json
from pathlib import Path

from .pipeline import run

p = argparse.ArgumentParser(prog="pixels_to_proof")
p.add_argument("case", type=Path, help="case.json")
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
log = run(a.case, a.out)
print(json.dumps({"verdict": log["verdict"], "scale": log["stages"]["scale"], "time": log["stages"]["time"],
                  "track": log["stages"]["track"],
                  "g_fit": log["kinematics"]["g_fit"]}, indent=2))
