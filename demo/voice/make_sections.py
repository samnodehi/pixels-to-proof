"""Spoken text of demo/SCRIPT_DRAFT.md, one entry per section (header lines are stage directions, not spoken)."""
import json, re, sys
src = sys.argv[1] if len(sys.argv) > 1 else "../SCRIPT_DRAFT.md"
body = open(src).read().split("---", 1)[1]
secs, cur = [], None
for line in body.splitlines():
    if line.startswith("**"):
        cur = {"title": line, "lines": []}
        secs.append(cur)
    elif line.strip() and cur:
        cur["lines"].append(line.strip())
for s in secs:
    s["text"] = re.sub(r"\s+", " ", " ".join(s["lines"]))
json.dump(secs, open("sections.json", "w"), indent=1)
