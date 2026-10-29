"""Render the demo video: a timeline of layers (images with pan/zoom and highlights, video clips, text) over the
narration, with the captions burned in. Usage: python3 render.py [start end] (seconds, for previews)."""
import json, subprocess, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
BG = (28, 23, 21)                          # BGR of #15171c, near-black
CONTENT = (60, 40, 1800, 880)              # x, y, w, h above the caption band
HL = (67, 195, 246)                        # BGR of #f6c343 (amber)
F = "/usr/share/fonts/opentype/inter/"
VOICE = "/home/claude/p2p/voice/"
B = json.load(open("boxes.json"))
MARKS = json.load(open("assets/hook_marks.json"))
X2 = lambda b: [v * 2 for v in b[:4]]     # CSS px -> screenshot px (device scale 2)

_img = {}
def img(path):
    if path not in _img:
        _img[path] = cv2.imread(path, cv2.IMREAD_COLOR)
    return _img[path]

def ease(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)

def lerp(a, b, u): return [x + (y - x) * u for x, y in zip(a, b)]

def keyed(keys, t):
    """keys: [(t, value)], value a list of numbers; eased interpolation, held outside the range."""
    if t <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1: return lerp(v0, v1, ease((t - t0) / max(t1 - t0, 1e-6)))
    return keys[-1][1]

def alpha(L, t):
    fi, fo = L.get("fade", 0.35), L.get("fade_out", L.get("fade", 0.35))
    return min(1.0, (t - L["t0"]) / fi if fi else 1.0, (L["t1"] - t) / fo if fo else 1.0)

def fit_dest(dest, aspect):
    """Largest rect of the given aspect (w/h) centred in dest."""
    x, y, w, h = dest
    if w / h > aspect: nw, nh = h * aspect, h
    else: nw, nh = w, w / aspect
    return x + (w - nw) / 2, y + (h - nh) / 2, nw, nh

def blend(canvas, layer, mask_a, x, y):
    h, w = layer.shape[:2]
    x0, y0 = max(int(round(x)), 0), max(int(round(y)), 0)
    x1, y1 = min(int(round(x)) + w, W), min(int(round(y)) + h, H)
    if x1 <= x0 or y1 <= y0: return
    lx, ly = x0 - int(round(x)), y0 - int(round(y))
    sub = layer[ly:ly + y1 - y0, lx:lx + x1 - x0].astype(np.float32)
    dst = canvas[y0:y1, x0:x1].astype(np.float32)
    if np.isscalar(mask_a): a = mask_a
    else: a = mask_a[ly:ly + y1 - y0, lx:lx + x1 - x0, None]
    canvas[y0:y1, x0:x1] = (dst * (1 - a) + sub * a).astype(np.uint8)

def draw_image(canvas, L, t):
    src = img(L["src"])
    dest = L.get("dest", CONTENT)
    crop = keyed(L["crop"], t)                       # x, y, w in source px; h follows the dest aspect
    dx, dy, dw, dh = dest
    cx, cy, cw = crop
    ch = cw * dh / dw
    s = dw / cw
    if s < 1:
        # downscale: area-average a padded crop (warpAffine would alias small screenshot text)
        x0, y0 = int(round(cx)), int(round(cy))
        x1, y1 = int(round(cx + cw)), int(round(cy + ch))
        pl, pt = max(0, -x0), max(0, -y0)
        pr, pb = max(0, x1 - src.shape[1]), max(0, y1 - src.shape[0])
        sub = src[max(y0, 0):min(y1, src.shape[0]), max(x0, 0):min(x1, src.shape[1])]
        if pl or pt or pr or pb:
            sub = cv2.copyMakeBorder(sub, pt, pb, pl, pr, cv2.BORDER_CONSTANT, value=L.get("pad", BG))
        out = cv2.resize(sub, (int(dw), int(dh)), interpolation=cv2.INTER_AREA)
    else:
        M = np.float32([[s, 0, -cx * s], [0, s, -cy * s]])
        out = cv2.warpAffine(src, M, (int(dw), int(dh)), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=L.get("pad", BG))
    for h in L.get("hl", []):
        on, off, box = h[0], h[1], h[2]
        if not (on <= t <= off): continue
        g = ease((t - on) / 0.3) * min(1.0, (off - t) / 0.3)
        bx, by, bw, bh = [(box[0] - cx) * s, (box[1] - cy) * s, box[2] * s, box[3] * s]
        ov = out.copy()
        cv2.rectangle(ov, (int(bx), int(by)), (int(bx + bw), int(by + bh)), HL, -1)
        cv2.addWeighted(ov, 0.18 * g, out, 1 - 0.18 * g, 0, out)
        cv2.rectangle(out, (int(bx), int(by)), (int(bx + bw), int(by + bh)), HL, max(2, int(4 * g)), cv2.LINE_AA)
    blend(canvas, out, alpha(L, t), dx, dy)

_caps = {}
def draw_video(canvas, L, t):
    key = id(L)
    if key not in _caps:
        _caps[key] = {"cap": cv2.VideoCapture(L["src"]), "n": -1, "frame": None}
    st = _caps[key]
    fps = st["cap"].get(cv2.CAP_PROP_FPS) or 30
    total = int(st["cap"].get(cv2.CAP_PROP_FRAME_COUNT))
    want = int(L.get("from", 0) * fps + max(t - L["t0"], 0) * L.get("rate", 1.0) * fps)
    want = min(want, L.get("until", total - 1), total - 1)
    if want < st["n"]:
        st["cap"].set(cv2.CAP_PROP_POS_FRAMES, want); st["n"] = want - 1
    while st["n"] < want:
        ok, fr = st["cap"].read()
        if not ok: break
        st["n"] += 1; st["frame"] = fr
    fr = st["frame"]
    if fr is None: return
    x, y, w, h = fit_dest(L.get("dest", CONTENT), fr.shape[1] / fr.shape[0])
    out = cv2.resize(fr, (int(w), int(h)), interpolation=cv2.INTER_AREA)
    for hb in L.get("hl", []):
        on, off, box = hb
        if not (on <= t <= off): continue
        s = w / fr.shape[1]
        g = ease((t - on) / 0.3)
        cv2.rectangle(out, (int(box[0] * s), int(box[1] * s)), (int((box[0] + box[2]) * s), int((box[1] + box[3]) * s)),
                      HL, max(2, int(4 * g)), cv2.LINE_AA)
    blend(canvas, out, alpha(L, t), x, y)

_text = {}
def text_layer(L):
    k = json.dumps(L["lines"])
    if k not in _text:
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
        for ln in L["lines"]:
            f = ImageFont.truetype(F + ln.get("font", "InterDisplay-Bold.otf"), ln["size"])
            tw = dr.textlength(ln["text"], font=f)
            x = ln.get("x", (W - tw) / 2)
            dr.text((x, ln["y"]), ln["text"], font=f, fill=ln.get("color", "#ffffff"))
        a = np.array(im)
        _text[k] = (cv2.cvtColor(a[:, :, :3], cv2.COLOR_RGB2BGR), a[:, :, 3].astype(np.float32) / 255)
    return _text[k]

def draw_text(canvas, L, t):
    rgb, a = text_layer(L)
    blend(canvas, rgb, a * alpha(L, t), 0, 0)

def draw_rect(canvas, L, t):
    x, y, w, h = L.get("dest", (0, 0, W, H))
    block = np.empty((int(h), int(w), 3), np.uint8); block[:] = L.get("color", BG)
    blend(canvas, block, L.get("opacity", 1.0) * alpha(L, t), x, y)

DRAW = {"img": draw_image, "vid": draw_video, "text": draw_text, "rect": draw_rect}

def frame(layers, t):
    c = np.empty((H, W, 3), np.uint8); c[:] = BG
    for L in layers:
        if L["t0"] <= t < L["t1"]:
            DRAW[L["type"]](c, L, t)
    return c

def render(layers, t_start, t_end, out, captions=True):
    audio = VOICE + "narration.mp3"
    vf = []
    if captions:
        vf = ["-vf", f"setpts=PTS+{t_start}/TB,subtitles={VOICE}narration.srt:force_style='FontName=Inter,FontSize=15,Bold=1,"
                     "PrimaryColour=&H00FFFFFF,OutlineColour=&H00101010,BorderStyle=1,Outline=1.2,Shadow=0,"
                     "Alignment=2,MarginV=22',setpts=PTS-STARTPTS"]
    # captions need the real timeline: shift the frames to t_start for the subtitle filter, then back to zero
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-ss", str(t_start), "-t", str(t_end - t_start), "-i", audio,
           *vf, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n0, n1 = int(round(t_start * FPS)), int(round(t_end * FPS))
    for n in range(n0, n1):
        p.stdin.write(frame(layers, n / FPS).tobytes())
    p.stdin.close(); p.wait()
    if p.returncode: raise SystemExit(f"ffmpeg failed: {p.returncode}")

if __name__ == "__main__":
    from timeline import LAYERS, END
    a = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    b = float(sys.argv[2]) if len(sys.argv) > 2 else END
    out = sys.argv[3] if len(sys.argv) > 3 else "demo.mp4"
    render(LAYERS, a, b, out)
