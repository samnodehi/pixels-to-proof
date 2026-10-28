"""Run ledger: every model call and every gate decision of one audit, in order, with what accepted or rejected it.
The app renders runs from these files; the film reads its numbers from them."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
import time
from pathlib import Path


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _commit(repo: Path) -> str:
    try:
        sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", "pixels_to_proof", "checks.toml"],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("+dirty" if dirty else "")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


class Ledger:
    def __init__(self, path: Path, run_id: str, inputs: dict[str, str], checks_file: Path | None):
        self.path = path
        root = Path(__file__).resolve().parent.parent
        self.data = {"run_id": run_id, "started": _now(), "commit": _commit(root), "inputs": inputs,
                     "checks_sha256": hashlib.sha256(checks_file.read_bytes()).hexdigest() if checks_file else None,
                     "events": [], "verdicts": [], "summary": {}}
        self._t0 = time.perf_counter()

    def _add(self, kind: str, **kw) -> dict:
        ev = {"i": len(self.data["events"]), "t": round(time.perf_counter() - self._t0, 2), "kind": kind, **kw}
        self.data["events"].append(ev)
        self.save()
        return ev

    def model(self, role: str, model: str, usage: dict | None, seconds: float, proposal: str, ref: str = "") -> int:
        tokens = (usage or {}).get("total_tokens")
        return self._add("model", role=role, model=model, tokens=tokens, seconds=round(seconds, 1),
                         proposal=proposal, ref=ref)["i"]

    def gate(self, gate: str, ok: bool, note: str, ref: str = "", on: int | None = None) -> None:
        self._add("gate", gate=gate, ok=bool(ok), note=note, ref=ref, on=on)

    def step(self, what: str, note: str = "", ref: str = "") -> None:
        self._add("step", what=what, note=note, ref=ref)

    def verdict(self, v: dict) -> None:
        self.data["verdicts"].append(v)
        self.save()

    def finish(self, **summary) -> None:
        self.data["summary"] = {**summary, "finished": _now(),
                                "wall_s": round(time.perf_counter() - self._t0, 1)}
        self.save()

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False, default=str))
        tmp.replace(self.path)

    # ---- counts used by the app and the film -------------------------------------------------------------
    def proposals(self) -> dict:
        ev = self.data["events"]
        models = [e for e in ev if e["kind"] == "model"]
        rejected = {e["on"] for e in ev if e["kind"] == "gate" and not e["ok"] and e.get("on") is not None}
        return {"model_calls": len(models), "tokens": sum(e["tokens"] or 0 for e in models),
                "rejected_calls": len(rejected)}
