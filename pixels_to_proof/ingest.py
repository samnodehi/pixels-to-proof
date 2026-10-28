"""Input bundle: inventory the files a paper ships with, extract text from the PDF and the tables, and decide
whether the material may be sent to a model at all (licence gate G0). No model is called here."""
from __future__ import annotations

import csv
import hashlib
import re
import subprocess
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
TABLE_EXT = {".xlsx", ".xls", ".csv", ".tsv"}

# Licences under which the material may be uploaded (free Model API credits allow Meta to use content).
_LICENCE_PATTERNS = [
    ("CC BY", r"creative\s+commons\s+attribution(?!\s*[-–]\s*non)(?!\s+non)|\bCC[\s-]?BY\b(?![\s-]*(NC|ND|SA))"),
    ("CC0", r"\bCC0\b|creative\s+commons\s+zero|public\s+domain\s+dedication"),
    ("public domain", r"\bin\s+the\s+public\s+domain\b|free\s+of\s+all\s+copyright"),
]
_FORBIDDEN = r"non[-\s]?commercial|no[-\s]?deriv|\bCC[\s-]?BY[\s-]?(NC|ND)\b|all rights reserved"


@dataclass
class Table:
    file: str
    sheet: str
    header: list[str]
    rows: list[list]            # data rows, values as read (numbers stay numbers)
    header_row: int             # 0-based row index of the header in the sheet


@dataclass
class Bundle:
    root: str
    pdfs: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    archives: list[str] = field(default_factory=list)
    other: list[str] = field(default_factory=list)
    hashes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inventory(root: Path) -> Bundle:
    """Every file under root, by role guessed from its extension (Spark later proposes the finer roles)."""
    b = Bundle(root=str(root))
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        rel = str(p.relative_to(root))
        ext = p.suffix.lower()
        bucket = (b.pdfs if ext == ".pdf" else b.videos if ext in VIDEO_EXT else b.tables if ext in TABLE_EXT
                  else b.archives if ext == ".zip" else b.other)
        bucket.append(rel)
        b.hashes[rel] = sha256(p)
    return b


def pdf_text(pdf: Path) -> str:
    """Reading-order text plus layout text: two-column pages interleave margins in layout mode, tables keep their
    rows only in layout mode; quote checks search both."""
    raw = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    lay = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True).stdout
    return raw + "\n\f\n" + lay


def normalise(text: str) -> str:
    """For verbatim-quote checks: unify whitespace, dashes, minus signs and ligatures produced by PDF extraction."""
    t = text.replace("−", "-").replace("–", "-").replace("—", "-").replace("±", "+/-")
    t = t.replace("ﬁ", "fi").replace("ﬂ", "fl").replace(" ", " ")
    t = re.sub(r"-\s*\n\s*", "", t)            # words hyphenated across lines
    # "take-off" broken as "take-|off" at a line end extracts as "takeoff": compare compounds without their hyphen
    t = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def quote_in_text(quote: str, text_norm: str, min_len: int = 12) -> bool:
    """Whitespace-insensitive containment: PDF extraction breaks lines and spaces superscripts ('m s -1'). A quote
    may join non-adjacent passages with '...' or '…'; then every passage must be found."""
    t = re.sub(r"\s+", "", text_norm)
    parts = [re.sub(r"\s+", "", normalise(x)) for x in re.split(r"\.\.\.|…|\[\.\.\.\]", quote)]
    parts = [x for x in parts if x]
    if not parts or sum(len(x) for x in parts) < min_len or any(len(x) < 8 for x in parts if len(parts) > 1):
        return False
    return all(x in t for x in parts)


def licence(text: str) -> tuple[str | None, str]:
    """(allowed licence name or None, the matched or explaining snippet). Looks at the whole text; a forbidden term
    near a licence statement wins."""
    flat = re.sub(r"\s+", " ", text)
    flat = re.sub(r"[\u2010-\u2015\u2212\u00ad]", "-", flat)        # every dash-like character is a hyphen
    for m in re.finditer(_FORBIDDEN, flat, re.I):
        ctx = flat[max(0, m.start() - 120): m.end() + 120]
        if re.search(r"licen[cs]e|creative commons|copyright", ctx, re.I):
            return None, ctx.strip()
    for name, pat in _LICENCE_PATTERNS:
        m = re.search(pat, flat, re.I)
        if m:
            return name, flat[max(0, m.start() - 80): m.end() + 80].strip()
    return None, "no CC BY, CC0 or public-domain statement found in the PDF text"


def _header_index(rows: list[list]) -> int:
    """First row in the top 15 whose cells are mostly non-empty strings and that is followed by numeric rows."""
    for i, r in enumerate(rows[:15]):
        cells = [c for c in r if c not in (None, "")]
        if len(cells) >= 2 and sum(isinstance(c, str) for c in cells) >= 0.6 * len(cells):
            nxt = rows[i + 1] if i + 1 < len(rows) else []
            if sum(isinstance(c, (int, float)) for c in nxt if c not in (None, "")) >= 1:
                return i
    return 0


def read_tables(path: Path) -> list[Table]:
    ext = path.suffix.lower()
    sheets: list[tuple[str, list[list]]] = []
    if ext in (".xlsx", ".xls"):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        for ws in wb.worksheets:
            sheets.append((ws.title, [list(r) for r in ws.iter_rows(values_only=True)]))
    else:
        delim = "\t" if ext == ".tsv" else ","
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            raw = list(csv.reader(f, delimiter=delim))
        sheets.append((path.stem, [[_num(c) for c in r] for r in raw]))
    out = []
    for name, rows in sheets:
        rows = [r for r in rows if any(c not in (None, "") for c in r)]
        if not rows:
            continue
        hi = _header_index(rows)
        header = [str(c).strip() if c is not None else "" for c in rows[hi]]
        width = max(len(header), max(len(r) for r in rows))
        header += [""] * (width - len(header))
        data = [list(r) + [None] * (width - len(r)) for r in rows[hi + 1:]]
        out.append(Table(file=path.name, sheet=name, header=header, rows=data, header_row=hi))
    return out


def _num(s: str):
    try:
        v = float(s)
        return int(v) if v.is_integer() and "." not in s and "e" not in s.lower() else v
    except (TypeError, ValueError):
        return s


def table_digest(t: Table, max_rows: int = 40) -> str:
    """Compact text for the model: header with column letters, column stats, and the first rows."""
    lines = [f"file {t.file} | sheet '{t.sheet}' | {len(t.rows)} data rows"]
    for j, h in enumerate(t.header):
        col = [r[j] for r in t.rows if j < len(r)]
        nums = [c for c in col if isinstance(c, (int, float)) and not isinstance(c, bool)]
        if nums:
            desc = f"numeric n={len(nums)} min={min(nums):.4g} max={max(nums):.4g}"
        else:
            vals = [str(c) for c in col if c not in (None, "")]
            desc = f"text n={len(vals)} e.g. {', '.join(sorted(set(vals))[:3])}"
        lines.append(f"  col {j} '{h}': {desc}")
    lines.append("  first rows:")
    for r in t.rows[:max_rows]:
        lines.append("   " + " | ".join("" if c is None else (f"{c:.6g}" if isinstance(c, float) else str(c)) for c in r))
    return "\n".join(lines)


def unzip(archive: Path, dst: Path) -> list[Path]:
    dst.mkdir(parents=True, exist_ok=True)
    out = []
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            name = Path(info.filename)
            if info.is_dir() or name.is_absolute() or ".." in name.parts:
                continue            # never write outside dst
            target = dst / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as f:
                f.write(src.read())
            out.append(target)
    return out
