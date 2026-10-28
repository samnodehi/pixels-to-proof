"""Pixels to Proof — web app (Hugging Face Space).

Audit view: a paper's recorded audit run, rendered from its ledger (every model proposal and every code check), with
the per-claim results and the video receipts. Bundled papers can also be re-run live (labelled live, rate limited).
Calibration view: the synthetic benchmark and the fault-injection results."""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).parent
AUDITS = ROOT / "showcase" / "audits"
BUNDLES = ROOT / "bundles"
MAX_RUNS_PER_DAY = int(os.environ.get("P2P_MAX_RUNS_PER_DAY", "15"))

_lock = threading.Lock()
_runs = {"day": dt.date.today(), "n": 0}

COLOURS = {"REPRODUCED": "#1f9d55", "NOT REPRODUCED": "#cc3333", "CANNOT MEASURE": "#b7791f",
           "MATCHES TABLE": "#1f9d55", "MATCHES OTHER COLUMN": "#2b6cb0", "NOT CHECKED": "#718096",
           "REFUSED": "#b7791f"}


def _e(x) -> str:
    return html.escape(str(x))


def chip(label: str) -> str:
    c = COLOURS.get(label, "#4a5568")
    return (f"<span style='display:inline-block;padding:1px 8px;border-radius:10px;background:{c};color:white;"
            f"font-size:.85em;font-weight:600;white-space:nowrap'>{_e(label)}</span>")


def audits() -> dict[str, Path]:
    out = {}
    for d in sorted(p for p in AUDITS.glob("*") if (p / "report.json").exists()):
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        out[meta.get("title", d.name)] = d
    return out


def load(d: Path) -> tuple[dict, dict, dict]:
    rep = json.loads((d / "report.json").read_text())
    led = json.loads((d / "ledger.json").read_text())
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
    return rep, led, meta


def header_md(rep: dict, led: dict, meta: dict, live: bool = False) -> str:
    s = led.get("summary", {})
    models = [e for e in led["events"] if e["kind"] == "model"]
    replayed = sum(1 for e in models if e.get("cached"))
    gates = [e for e in led["events"] if e["kind"] == "gate" and e["gate"] != "route"]
    rej = sum(1 for g in gates if not g["ok"])
    tag = "LIVE RUN" if live else "RECORDED RUN"
    lines = [f"### {_e(meta.get('title', rep.get('bundle')))}",
             f"{meta.get('citation', '')}  ",
             f"*Licence: {meta.get('licence', '')}*  ",
             f"**{tag}** `{led['run_id']}` · {led['started'][:16].replace('T', ' ')} UTC · code `{led['commit'][:12]}` · "
             f"{s.get('wall_s', '?')} s" + (f" ({replayed} of {len(models)} model outputs replayed from an earlier "
                                            "run on the same files)" if replayed else " (all model calls made in this run)")
             + f" · input files: {len(led.get('inputs', {}))} (hashes in the ledger)  ",
             f"**Hands-off:** the agent received only the files the journal published — "
             f"{', '.join(f'`{k}`' for k in led.get('inputs', {}))}. Nothing was set by hand.  ",
             f"**Work done:** {sum(1 for e in models if e['role'] != 'track')} Muse Spark proposals "
             f"({sum(e['tokens'] or 0 for e in models):,} tokens) · "
             f"SAM 3.1 tracks: {sum(1 for g in gates if g['gate'] == 'G5 track')} · "
             f"{len(gates)} code checks, {rej} of which rejected something."]
    return "\n".join(lines)


def claims_html(rep: dict) -> str:
    rows = []
    for c in rep["claims"]:
        pm = f" ± {c['plus_minus']:g}" if c.get("plus_minus") is not None else ""
        src = "" if c.get("source", "paper") == "paper" else \
            "<br><span style='opacity:.7;font-size:.85em'>printed on the video</span>"
        rows.append(f"<tr><td style='max-width:420px'>“{_e(c['quote'])}”{src}</td>"
                    f"<td>{_e(c['statistic'])}{('<br><span style=\'opacity:.7;font-size:.85em\'>' + _e(c['rows']) + '</span>') if c.get('rows') not in (None, 'all') else ''}</td><td>{_e(c['value'])}{_e(pm)} {_e(c['unit'])}</td>"
                    f"<td>{chip(c['outcome'])}</td><td style='max-width:380px;font-size:.9em'>{_e(c['reason'])}</td></tr>")
    counts = rep.get("summary", {}).get("claims", {})
    head = " · ".join(f"{chip(k)} {v}" for k, v in counts.items())
    return (f"<div style='margin:6px 0'>{len(rep['claims'])} kinematic claims found in the paper and on its videos: {head}</div>"
            "<div style='overflow-x:auto'><table style='font-size:.92em'><tr><th>claim (verbatim from the paper or its video)</th>"
            "<th>kind</th><th>value</th><th>outcome</th><th>why</th></tr>" + "".join(rows) + "</table></div>"
            "<div style='opacity:.75;font-size:.85em'>Statistics over many jumps are recomputed from the paper's own "
            "event table (arithmetic only). MATCHES OTHER COLUMN: the printed digits are reproduced by a different "
            "column than the one proposed for the sentence. NOT CHECKED is not a judgement of the paper: the column or "
            "aggregation behind a printed number is not always stated.</div>")


def videos_html(rep: dict) -> str:
    rows = []
    for v in rep["videos"]:
        rows.append(f"<tr><td>{_e(v['video'])}</td><td>{_e(v.get('shot_label', v['shot']))}</td><td>{v['frames']}</td>"
                    f"<td>{chip(v['verdict'])}</td><td style='font-size:.9em'>{_e(v['reason'])}</td></tr>")
    return ("<div style='overflow-x:auto'><table style='font-size:.92em'><tr><th>video</th><th>shot</th><th>frames</th>"
            "<th>verdict</th><th>why</th></tr>" + "".join(rows) + "</table></div>")


def verdict_card(v: dict) -> str:
    c, m, k, pr = v["claim"], v["measured"], v["kinematics"], v["pairing"]
    col = COLOURS.get(v["verdict"], "#4a5568")
    pm = f" ± {c['plus_minus']:.3f}" if c.get("plus_minus") else ""
    lines = [f"<div style='border-left:6px solid {col};padding:8px 14px'>",
             f"<div style='font-size:1.5em;font-weight:700;color:{col}'>{_e(v['verdict'])}</div>",
             f"<div><b>Published</b> (event table, row <code>{_e(c['row'])}</code>, column <code>{_e(c['column'])}</code>): "
             f"<b>{c['value']:.3f}{pm} m/s</b> <span style='opacity:.7'>({_e(c['plus_minus_note'])})</span></div>"]
    if v["verdict"] != "CANNOT MEASURE":
        lines.append(f"<div><b>Re-measured from the video</b> (ballistic fit of the SAM 3.1 track): "
                     f"<b>{m['mid']:.3f} m/s</b>, interval {m['lo']:.3f}–{m['hi']:.3f}</div>")
    else:
        lines.append("<div><b>Re-measured</b>: not reported, a self-check failed</div>")
    if v.get("accepts_published"):
        a, b = v["accepts_published"]
        lines.append(f"<div><b>Sensitivity</b>: with this interval and this kind of ±, any published value between "
                     f"{a:.3f} and {b:.3f} m/s ({(a / c['value'] - 1):+.0%} to {(b / c['value'] - 1):+.0%} of the "
                     "printed one) would read REPRODUCED.</div>")
    if v.get("authors_method_replica") is not None:
        lines.append(f"<div><b>Second reading</b> — the authors' stated method, approximately replicated on our track "
                     f"({_e(v['authors_method']['parameters'][:80])}): {v['authors_method_replica']:.3f} m/s "
                     "<span style='opacity:.7'>(printed, does not vote)</span></div>")
    lines.append(f"<div><b>Self-checks</b>: gravity from the flight {k['g_fit']:.2f} m/s² (9.81 expected) · "
                 f"sideways acceleration {k['ax_rel_g']:.1%} of vertical (≈0 expected)</div>")
    lines.append(f"<div><b>Blind pairing</b>: this jump is row <code>{_e(pr['row_id'])}</code>, {pr['margin']:.1f}× closer than "
                 f"the runner-up, from {', '.join(pr['features'])} only — the published speed was not looked at.</div>")
    lines.append(f"<div style='opacity:.8'><b>Why</b>: {_e(v['reason'])}</div></div>")
    return "\n".join(lines)


def ledger_html(led: dict, limit: int = 400) -> str:
    rows = []
    for e in led["events"][:limit]:
        if e["kind"] == "model":
            who, what, ok = "MUSE SPARK PROPOSED", f"{e['role']}: {e['proposal']}", None
        elif e["kind"] == "gate":
            who, what, ok = "CODE CHECKED", f"{e['gate']}: {e['note']}", e["ok"]
        else:
            who, what, ok = "CODE", f"{e['what']}: {e.get('note', '')}", None
        mark = "" if ok is None else ("<span style='color:#1f9d55'>✔</span>" if ok else "<span style='color:#cc3333'>✘</span>")
        tag_c = "#6b46c1" if who.startswith("MUSE") else "#2d3748"
        rows.append(f"<tr><td style='opacity:.6'>{e['t']:.1f}s</td><td><span style='color:{tag_c};font-weight:600;"
                    f"font-size:.8em'>{who}</span></td><td>{mark}</td><td style='font-size:.88em'>{_e(what)}"
                    f"{(' <code>' + _e(e['ref']) + '</code>') if e.get('ref') else ''}</td></tr>")
    more = f"<div style='opacity:.6'>… {len(led['events']) - limit} more events in ledger.json</div>" \
        if len(led["events"]) > limit else ""
    return ("<div style='max-height:520px;overflow-y:auto'><table style='font-size:.9em'>" + "".join(rows) +
            "</table></div>" + more)


def refusal_card(v: dict) -> str:
    """A shot that was tracked and measured but refused: what the checks found."""
    k, pr = v["kinematics"], v.get("pairing") or {}
    col = COLOURS.get("CANNOT MEASURE", "#b7791f")
    lines = [f"<div style='border-left:6px solid {col};padding:8px 14px'>",
             f"<div style='font-size:1.5em;font-weight:700;color:{col}'>CANNOT MEASURE</div>",
             f"<div>Shot <code>{_e(v['unit'])}</code> was tracked (SAM 3.1) and measured, and a check refused it.</div>",
             f"<div><b>Self-checks</b>: gravity from the flight {k['g_fit']:.2f} m/s² (9.81 expected) · sideways "
             f"acceleration {k['ax_rel_g']:.1%} of vertical (≈0 expected)</div>"]
    if k.get("drag_like"):
        lines.append(f"<div><b>Diagnosis</b>: {_e(k['drag_like'])}</div>")
    if pr:
        lines.append(f"<div><b>Blind pairing</b>: {_e(pr.get('reason', ''))}</div>")
    lines.append(f"<div style='opacity:.8'><b>Why</b>: {_e(v['reason'])}</div></div>")
    return "\n".join(lines)


def render(d: Path, live: bool = False):
    rep, led, meta = load(d)
    vids = [v for v in rep["videos"] if v["verdict"] in ("REPRODUCED", "NOT REPRODUCED") or v.get("claim")]
    tracked = [v for v in rep["videos"] if v.get("kinematics")]
    hero = vids[0] if vids else (tracked[0] if tracked else None)
    rec = (d / "units" / hero["unit"] / "receipt.mp4") if hero else None
    ev = (d / "units" / hero["unit"] / "scale_evidence.png") if hero else None
    card = (verdict_card(hero) if vids else refusal_card(hero)) if hero else \
        "<i>No video jump could be measured in this bundle.</i>"
    return (header_md(rep, led, meta, live), str(rec) if rec and rec.exists() else None, card,
            str(ev) if ev and ev.exists() else None, claims_html(rep), videos_html(rep), ledger_html(led),
            meta.get("note", ""))


def _quota() -> bool:
    with _lock:
        if _runs["day"] != dt.date.today():
            _runs.update(day=dt.date.today(), n=0)
        if _runs["n"] >= MAX_RUNS_PER_DAY:
            return False
        _runs["n"] += 1
        return True


def live_run(title: str):
    from pixels_to_proof import agent      # lazily: the recorded view loads without an API key

    keep = [gr.update()] * 8
    d = audits().get(title)
    bundle = BUNDLES / d.name if d else None
    if not os.environ.get("MODEL_API_KEY"):
        yield *keep, "Live runs are disabled on this deployment (no MODEL_API_KEY secret)."
        return
    if bundle is None or not bundle.exists():
        yield *keep, "This paper's files are not bundled with the app, so it is shown as recorded only."
        return
    if not _quota():
        yield *keep, f"The daily limit of {MAX_RUNS_PER_DAY} live runs is reached; the recorded run is shown."
        return
    work = Path(tempfile.mkdtemp(prefix="p2p_live_"))
    yield *keep, ("Running the whole audit from the bundled files: Muse Spark reads the paper, tables and videos, "
                  "code checks every proposal, SAM 3.1 tracks. This takes a few minutes.")
    try:
        agent.run_audit(bundle, work, run_id="live-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S"))
        if (d / "meta.json").exists():
            shutil.copy(d / "meta.json", work / "meta.json")
        out = render(work, live=True)
    except Exception as exc:          # shown as is; the recorded run stays available
        yield *keep, f"Live run failed: {type(exc).__name__}: {exc}. Select the paper again to see the recorded run."
        return
    yield *out, "Live run finished; shown above. Select the paper again to return to the recorded run."


INTRO = """
# Pixels to Proof
**An agent that audits the motion numbers in a scientific paper against the paper's own supplementary videos and data.**

Give it what the journal published — the PDF, the videos, the data tables. **Muse Spark 1.3** reads them and *proposes*:
which file is which, what each table column means (with the sentence or script line that says so), which claims the paper
makes, what is printed on each video. **Code checks every proposal** against the files and the physics. **SAM 3.1** tracks
the animal. Each claim ends with a verdict and its evidence, or a refusal that names the check that failed.
*The model proposes; tracking, arithmetic and physics decide. No number in a verdict is written by a language model.*
"""


def build() -> gr.Blocks:
    choices = list(audits())
    with gr.Blocks(title="Pixels to Proof") as demo:
        gr.Markdown(INTRO)
        with gr.Tab("Audit"):
            pick = gr.Dropdown(choices, value=choices[0] if choices else None, label="Paper")
            head = gr.Markdown()
            with gr.Row():
                rec = gr.Video(label="Receipt: the tracked jump with the checks burned in", autoplay=False)
                with gr.Column():
                    card = gr.HTML()
                    note = gr.Markdown()
            gr.Markdown("#### Every claim the paper makes about motion")
            claims = gr.HTML()
            gr.Markdown("#### Every shot in the supplementary videos")
            vids = gr.HTML()
            ev = gr.Image(label="Scale evidence: grid lines measured by OpenCV (green), Spark's object box (orange)",
                          height=320)
            with gr.Accordion("Run ledger: every proposal and every check, in order", open=False):
                led = gr.HTML()
            with gr.Row():
                go = gr.Button("Re-run this audit live", variant="secondary")
                status = gr.Markdown()
            outs = [head, rec, card, ev, claims, vids, led, note]
            pick.change(lambda t: render(audits()[t]), pick, outs)
            demo.load(lambda t: render(audits()[t]) if t else [None] * 8, pick, outs)
            go.click(live_run, pick, outs + [status], concurrency_limit=1)
        with gr.Tab("Breadth"):
            f = ROOT / "showcase" / "breadth.md"
            gr.Markdown(f.read_text() if f.exists() else "No breadth test recorded yet.")
        with gr.Tab("Calibration"):
            for name in ("calibration.md", "faults.md"):
                f = ROOT / "showcase" / name
                if f.exists():
                    gr.Markdown(f.read_text())
        gr.Markdown("Built for the Meta Global AI Developer Hackathon 2026 with Muse Spark 1.3 and SAM 3.1 (Meta Model "
                    "API). Source: github.com/samnodehi/pixels-to-proof")
    return demo


if __name__ == "__main__":
    build().launch(theme=gr.themes.Soft())
