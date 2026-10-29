import sys, csv, subprocess
sys.path.insert(0, "/home/claude/p2p/repo")
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from pixels_to_proof import shots
A = "assets/"
F = "/usr/share/fonts/opentype/inter/"
def font(name, size): return ImageFont.truetype(F + name, size)

def pdf_crop(path, page, clip, zoom, out, marks):
    d = pymupdf.open(path); pg = d[page]
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(*clip))
    pix.save(A + out)
    # highlight boxes in image pixels, for the renderer
    boxes = []
    for q in marks:
        for r in pg.search_for(q, clip=pymupdf.Rect(*clip)):
            boxes.append([(r.x0 - clip[0]) * zoom - 6, (r.y0 - clip[1]) * zoom - 4, (r.x1 - r.x0) * zoom + 12, (r.y1 - r.y0) * zoom + 8])
    return boxes

hl = {}
hl["beetle"] = pdf_crop("/home/claude/p2p/bundles/beetle/paper.pdf", 0, (196, 424, 579, 464.5), 5, "hook_beetle.png",
                        ["takeoff velocities", "of 0.47 ± 0.15 m s"])
hl["peacock"] = pdf_crop("/home/claude/p2p/bundles/peacock/jeb249416.pdf", 5, (44, 364, 304, 397), 7, "hook_peacock.png",
                         ["take-off angle", "males: 25.08±8.55 deg"])
print(hl)

# raw video frames (no overlays): beetle s004 shot 2 mid-flight, peacock male recording
rng, n = shots.ranges("/home/claude/p2p/bundles/beetle/journal.pone.0256509.s004.mp4")
a, b = rng[1]; print("beetle shot 2", a, b)
shots.frame_at("/home/claude/p2p/bundles/beetle/journal.pone.0256509.s004.mp4", a + 330, A + "raw_beetle.png")
shots.frame_at("/home/claude/p2p/bundles/peacock/S1_Maratus.mp4", 290, A + "raw_peacock.png")

# CSV snippet as a table image
rows = list(csv.reader(open("/home/claude/p2p/bundles/peacock/Maratus_splendens_kinematics.csv")))
cols = [0, 2, 3, 8, 12]
W, H = 1500, 560
im = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(im)
fh, fb = font("Inter-SemiBold.otf", 28), font("Inter-Regular.otf", 28)
xs = [30, 190, 360, 540, 1000]
dr.rectangle([0, 0, W, 70], fill="#eef1f6")
for x, c in zip(xs, cols): dr.text((x, 20), rows[0][c], font=fh, fill="#1a202c")
for k, r in enumerate(rows[1:9]):
    y = 90 + k * 56
    for x, c in zip(xs, cols):
        v = r[c]
        try: v = f"{float(v):.4f}" if "." in v else v
        except ValueError: pass
        dr.text((x, y), v, font=fb, fill="#2d3748")
    dr.line([0, y + 46, W, y + 46], fill="#e2e8f0", width=2)
im.save(A + "csv_peacock.png")
import json; json.dump(hl, open(A + "hook_marks.json", "w"))
