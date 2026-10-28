"""Breadth test: run the hands-off audit on many bundles (table checks need no video) and summarise the outcomes.

Usage: python scripts/batch_audit.py OUT_DIR BUNDLE_DIR [BUNDLE_DIR ...]
Each bundle folder holds a paper's files as published (PDF, tables, any videos) plus an optional source.json
{"citation": ..., "doi": ..., "licence": ..., "files": {name: url}}. Writes OUT_DIR/<bundle>/ (full run) and
OUT_DIR/BREADTH.md (one row per paper, every non-matching claim listed with the agent's reason)."""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pixels_to_proof import agent  # noqa: E402


def one(bundle: Path, out: Path) -> dict:
    run = out / bundle.name
    t = time.time()
    try:
        rep = agent.run_audit(bundle, run, f"{bundle.name}-{time.strftime('%Y%m%d')}")
        return {"bundle": bundle.name, "report": rep, "seconds": round(time.time() - t), "error": None}
    except Exception as exc:                       # one paper's failure must not stop the batch
        return {"bundle": bundle.name, "report": None, "seconds": round(time.time() - t),
                "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    out, bundles = Path(sys.argv[1]), [Path(p) for p in sys.argv[2:]]
    out.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(3) as ex:
        results = list(ex.map(lambda b: one(b, out), bundles))
    lines = ["# Breadth test: table checks on papers with published per-event data", "",
             "| paper | claims | MATCHES TABLE | other column | NOT CHECKED | REFUSED | video shots | seconds |",
             "|---|---|---|---|---|---|---|---|"]
    notes = []
    for r, b in zip(results, bundles):
        src = json.loads((b / "source.json").read_text()) if (b / "source.json").exists() else {}
        name = src.get("short", b.name)
        if r["error"]:
            lines.append(f"| {name} | error: {r['error'][:80]} | | | | | | {r['seconds']} |")
            continue
        rep = r["report"]
        c = rep["summary"].get("claims", {})
        stopped = rep["summary"].get("stopped")
        vids = rep["summary"].get("videos", {})
        lines.append(f"| {name} | {sum(c.values()) if not stopped else 'stopped: ' + stopped[:40]} | "
                     f"{c.get('MATCHES TABLE', 0)} | {c.get('MATCHES OTHER COLUMN', 0)} | {c.get('NOT CHECKED', 0)} | "
                     f"{c.get('REFUSED', 0)} | {len(vids)} | {r['seconds']} |")
        flagged = [x for x in rep["claims"] if x["outcome"] in ("MATCHES OTHER COLUMN", "NOT CHECKED")]
        if flagged:
            notes.append(f"\n## {name}\n{src.get('citation', '')} {src.get('doi', '')}\n")
            for x in flagged:
                notes.append(f"- **{x['outcome']}** — “{x['quote'][:160]}” — {x['reason'][:260]}")
    (out / "BREADTH.md").write_text("\n".join(lines + notes) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
