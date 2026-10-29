"""The demo's shot list. Times are seconds on the narration (narration.mp3, 172.4 s); the spoken words at each time are
in /home/claude/p2p/voice/words.json. Source coordinates are screenshot pixels (CSS px x 2) unless noted."""
import json

B = json.load(open("boxes.json"))
B2 = json.load(open("boxes2.json"))
MK = json.load(open("assets/hook_marks.json"))
END = 172.43
S = "shots/"
A = "assets/"
AUD = "/home/claude/p2p/repo/showcase/audits/"
BUN = "/home/claude/p2p/bundles/"
REC_B = AUD + "beetle/units/journal.pone.0256509.s004_s2/receipt.mp4"
REC_P = AUD + "peacock/units/S1_Maratus_s2r1/receipt.mp4"
CONTENT = (60, 40, 1800, 880)
ASP = CONTENT[2] / CONTENT[3]


def px(b, pad=0):
    """CSS box -> screenshot px, padded."""
    return [b[0] * 2 - pad, b[1] * 2 - pad, b[2] * 2 + 2 * pad, b[3] * 2 + 2 * pad]


def span(b0, b1, pad=6):
    """One box covering two CSS boxes (first row to last row)."""
    x0, y0 = min(b0[0], b1[0]), min(b0[1], b1[1])
    x1, y1 = max(b0[0] + b0[2], b1[0] + b1[2]), max(b0[1] + b0[3], b1[1] + b1[3])
    return px([x0, y0, x1 - x0, y1 - y0], pad)


def view(y_css, x_css=20, w_css=1240):
    """A crop of the page starting at CSS y, full content width."""
    return [x_css * 2, y_css * 2, w_css * 2]


def label(t0, t1, text, y=170, size=34):
    return {"type": "text", "t0": t0, "t1": t1, "lines": [
        {"text": text, "y": y, "size": size, "font": "Inter-Regular.otf", "color": "#9aa3b2"}]}


L = []

# 0 — the hook: two published numbers, the data behind them, the title ---------------------------------------------
bb = MK["beetle"]; bb[1] = [bb[1][0], bb[1][1], bb[1][2] + 28, bb[1][3]]          # include "-1" of "m s-1"
L += [label(0.2, 7.6, "Bertone et al. 2022, PLOS ONE"),
      {"type": "img", "t0": 0.2, "t1": 7.6, "src": A + "hook_beetle.png", "dest": (102, 330, 1716, 182),
       "crop": [(0.2, [0, 0, 1915])],
       "hl": [(3.9, 7.6, bb[0]), (3.9, 7.6, bb[1])]},
      label(7.6, 11.7, "Narendra et al. 2025, Journal of Experimental Biology"),
      {"type": "img", "t0": 7.6, "t1": 11.7, "src": A + "hook_peacock.png", "dest": (160, 330, 1600, 203),
       "crop": [(7.6, [0, 0, 1820])],
       "hl": [(8.9, 11.7, MK["peacock"][0]), (9.6, 11.7, MK["peacock"][1])]},
      {"type": "img", "t0": 13.6, "t1": 20.4, "src": A + "csv_peacock.png", "dest": (40, 250, 1010, 377),
       "crop": [(13.6, [0, 0, 1500])], "pad": (255, 255, 255)},
      label(13.6, 20.4, "the data table", y=650, size=30),
      {"type": "vid", "t0": 15.4, "t1": 20.4, "src": BUN + "beetle/journal.pone.0256509.s004.mp4",
       "from": (211 + 230) / 30, "dest": (1080, 40, 760, 427)},
      {"type": "vid", "t0": 16.0, "t1": 20.4, "src": BUN + "peacock/S1_Maratus.mp4", "from": 250 / 30,
       "dest": (1080, 480, 760, 427)},
      {"type": "text", "t0": 20.5, "t1": 24.9, "lines": [
          {"text": "Pixels to Proof", "y": 330, "size": 132},
          {"text": "an agent that checks a paper against its own data", "y": 510, "size": 46,
           "font": "Inter-Regular.otf", "color": "#c9d1dc"}]}]

# 1 — what it is: the recorded run of the beetle paper ---------------------------------------------------------------
bf = S + "beetle_full.png"
hands = [32, B["beetle"]["t_handsoff"][0][1], 1216, 40]
claims = B["beetle"]["tables"][0]
outcome_th = [t for t in B["beetle"]["th"] if t[4].startswith("outcome")][0]
L += [{"type": "img", "t0": 24.9, "t1": 29.4, "src": bf, "crop": [(24.9, view(330)), (29.4, view(350))],
       "hl": [(26.4, 29.4, px(hands, 6))]},
      {"type": "img", "t0": 29.4, "t1": 41.7, "src": bf,
       "crop": [(29.4, view(claims[1] - 20)), (41.7, view(claims[1] + 380))],
       "hl": [(34.6, 37.3, px([claims[0], claims[1], 395, claims[3]], 4)),
              (37.4, 41.7, px([outcome_th[0], claims[1], outcome_th[2], claims[3]], 4))]},
      {"type": "img", "t0": 41.7, "t1": 49.2, "src": bf, "crop": [(41.7, view(0)), (49.2, view(20, 30, 1000))],
       "hl": [(44.6, 49.2, px(B["beetle"]["t_rule"][0], 8))]}]

# 2 — the ledger: a quote rejected, Muse Spark asked again -----------------------------------------------------------
lr = [[r[0], r[1] - B2["ledger"]["rows"][0][1], r[2], r[3], r[4]] for r in B2["ledger"]["rows"]]
L += [{"type": "img", "t0": 49.2, "t1": 63.1, "src": S + "ledger_table.png", "pad": (255, 255, 255),
       "crop": [(49.2, [0, lr[40][1] * 2, 2336]), (54.8, [0, lr[62][1] * 2 - 12, 2336])],
       "hl": [(55.0, 57.2, span(lr[62], lr[73])), (57.2, 63.1, px(lr[74], 6)), (59.9, 63.1, px(lr[75], 6))]}]

# 3 — numbers against the table: circular means, truncations; then thirteen papers ---------------------------------
pf = S + "peacock_full.png"
pr = B["peacock"]["rows"]
L += [{"type": "img", "t0": 63.1, "t1": 65.7, "src": pf, "crop": [(63.1, view(330)), (65.7, view(345))]},
      {"type": "img", "t0": 65.7, "t1": 72.6, "src": pf, "crop": [(65.7, view(pr[8][1] - 80)), (72.6, view(pr[9][1] - 60))],
       "hl": [(67.4, 72.6, span(pr[12], pr[13]))]},
      {"type": "img", "t0": 72.6, "t1": 78.1, "src": pf,
       "crop": [(72.6, view(pr[8][1] - 40)), (75.4, view(pr[8][1] - 40)), (76.3, view(pr[18][1] - 40))],
       "hl": [(73.3, 75.6, span(pr[9], pr[10])), (76.3, 78.1, px(pr[21], 6))]}]
br = [r for r in B2["breadth_rows"] if r[3] > 0]
bt = B["breadth"]["tables"][-1]
rows = lambda *ix: [(t, t + 0.9, px(br[i], 4)) for t, i in ix]
L += [{"type": "img", "t0": 78.1, "t1": 84.4, "src": S + "breadth_full.png",
       "crop": [(78.1, view(380)), (84.4, view(400))],
       "hl": [(80.3, 81.2, px(br[2], 4)), (80.3, 81.2, px(br[7], 4)), (80.3, 81.2, px(br[9], 4)),
              (80.3, 81.2, px(br[10], 4)), (81.1, 82.0, px(br[3], 4)), (81.1, 82.0, px(br[8], 4)),
              (81.9, 82.8, px(br[1], 4)), (82.7, 83.7, px(br[4], 4)), (82.7, 83.7, px(br[6], 4)),
              (83.7, 84.4, px(br[5], 4))]},
      {"type": "text", "t0": 84.4, "t1": 90.6, "lines": [
          {"text": "13 papers", "y": 250, "size": 96},
          {"text": "319 printed numbers", "y": 380, "size": 72, "font": "InterDisplay-SemiBold.otf",
           "color": "#c9d1dc"}]},
      {"type": "text", "t0": 87.6, "t1": 90.6, "fade": 0.25, "lines": [
          {"text": "63 reproduce to the printed digit", "y": 520, "size": 72, "font": "InterDisplay-SemiBold.otf",
           "color": "#5fd08a"}]},
      {"type": "img", "t0": 90.6, "t1": 94.0, "src": S + "breadth_full.png",
       "crop": [(90.6, view(1000)), (94.0, view(1060))]}]

# 4 — the video: eleven shots refused, one tracked, paired blind, reproduced -----------------------------------------
vt = B["beetle"]["tables"][1]
brw = B["beetle"]["rows"]
vrows = [r for r in brw if r[4].startswith("journal.pone")]
verdict_th = [t for t in B["beetle"]["th"] if t[4].startswith("verdict")][0]
refused = [r for r in vrows if "CANNOT MEASURE" in r[4]]
repro = [r for r in vrows if "REPRODUCED" in r[4]][0]
card = B["beetle"]["verdict"][0]
cl = {c[4].split(":")[0].split(" ")[0]: c for c in B["beetle"]["cardlines"]}
L += [{"type": "vid", "t0": 94.0, "t1": 98.1, "src": BUN + "beetle/journal.pone.0256509.s004.mp4",
       "from": (211 + 200) / 30},
      {"type": "img", "t0": 98.1, "t1": 105.9, "src": bf,
       "crop": [(98.1, view(vt[1] - 30, 20, 1180)), (105.9, view(vt[1] - 20, 20, 1160))],
       "hl": [(99.6, 105.9, px([verdict_th[0], refused[0][1], verdict_th[2], refused[-2][1] + refused[-2][3] - refused[0][1]], 3)),
              (99.6, 105.9, px([verdict_th[0], refused[-1][1], verdict_th[2], refused[-1][3]], 3)),
              (105.2, 105.9, px(repro, 4))]},
      {"type": "vid", "t0": 105.9, "t1": 118.0, "src": REC_B, "from": 4.0, "rate": 1.3, "dest": (40, 150, 1020, 574)},
      {"type": "img", "t0": 108.9, "t1": 118.0, "src": bf, "dest": (1090, 180, 800, 559),
       "crop": [(108.9, px(card, 16)[:3])],
       "hl": [(109.4, 113.6, px(cl["Blind"], 2)), (115.2, 118.0, px(cl["REPRODUCED"], 2))]}]

# 5 — the spider: recordings split, playback read, gap measured, refused ---------------------------------------------
pcard = B["peacock"]["verdict"][0]
pl = {c[4].split(":")[0].split(" ")[0]: c for c in B["peacock"]["cardlines"]}
L += [{"type": "vid", "t0": 118.0, "t1": 120.8, "src": BUN + "peacock/S1_Maratus.mp4", "from": 290 / 30},
      {"type": "vid", "t0": 120.8, "t1": 124.1, "src": BUN + "peacock/S1_Maratus.mp4", "from": 372 / 30, "rate": 0.6},
      {"type": "vid", "t0": 124.1, "t1": 127.1, "src": REC_P, "from": 0.0,
       "hl": [(124.4, 127.1, (1555, 985, 280, 85))]},
      {"type": "img", "t0": 127.1, "t1": 129.1, "src": AUD + "peacock/units/S1_Maratus_s2r1/scale_evidence.png",
       "dest": (178, 40, 1564, 880), "crop": [(127.1, [0, 0, 1920]), (129.1, [60, 70, 1800])],
       "hl": [(127.4, 129.1, (190, 920, 1650, 80))]},
      {"type": "vid", "t0": 129.1, "t1": 146.1, "src": REC_P, "from": 0.0, "rate": 0.8, "dest": (40, 180, 1020, 574)},
      {"type": "img", "t0": 129.1, "t1": 146.1, "src": pf, "dest": (1090, 260, 800, 404),
       "crop": [(129.1, px(pcard, 16)[:3])],
       "hl": [(129.5, 131.2, px(pl["CANNOT"], 2)), (131.2, 133.6, px(pl["Self-checks"], 2)),
              (133.6, 141.3, px(pl["Diagnosis"], 2)), (141.3, 146.1, px(pl["CANNOT"], 2))]}]

# 6 — fault injection ------------------------------------------------------------------------------------------------
cf = S + "calib_full.png"
ft = B["calib"]["tables"][-1]
summ = B["calib"]["summary"][0]
L += [{"type": "img", "t0": 146.1, "t1": 151.3, "src": cf, "crop": [(146.1, view(990)), (151.3, view(1480))]},
      {"type": "img", "t0": 151.3, "t1": 159.9, "src": cf,
       "crop": [(151.3, view(summ[1] - 470)), (159.9, view(summ[1] - 430))]},
      {"type": "rect", "t0": 151.3, "t1": 159.9, "opacity": 0.95},
      {"type": "text", "t0": 151.5, "t1": 159.9, "lines": [{"text": "12 kinds of wrong model answers", "y": 150,
                                                          "size": 52, "font": "Inter-Regular.otf", "color": "#c9d1dc"}]},
      {"type": "text", "t0": 151.6, "t1": 159.9, "lines": [{"text": "4  caught", "x": 640, "y": 280, "size": 76}]},
      {"type": "text", "t0": 152.7, "t1": 159.9, "lines": [{"text": "6  repaired", "x": 640, "y": 390, "size": 76}]},
      {"type": "text", "t0": 155.2, "t1": 159.9, "lines": [{"text": "2  no change", "x": 640, "y": 500, "size": 76}]},
      {"type": "text", "t0": 156.8, "t1": 159.9, "lines": [{"text": "0  wrong verdicts", "x": 640, "y": 610,
                                                          "size": 76, "color": "#5fd08a"}]}]

# 7 — close ----------------------------------------------------------------------------------------------------------
L += [{"type": "text", "t0": 159.9, "t1": 167.4, "lines": [{"text": "Muse Spark proposes.", "y": 260, "size": 64}]},
      {"type": "text", "t0": 162.2, "t1": 167.4, "lines": [{"text": "SAM 3.1 tracks.", "y": 370, "size": 64}]},
      {"type": "text", "t0": 164.4, "t1": 167.4, "lines": [
          {"text": "Code checks every step, and writes it down.", "y": 480, "size": 64}]},
      {"type": "text", "t0": 167.4, "t1": END + 0.5, "fade_out": 0, "lines": [
          {"text": "Pixels to Proof", "y": 300, "size": 132},
          {"text": "a second reader for the numbers in science", "y": 480, "size": 48,
           "font": "Inter-Regular.otf", "color": "#c9d1dc"},
          {"text": "Meta Global AI Developer Hackathon 2026  ·  Muse Spark 1.3  ·  SAM 3.1", "y": 640, "size": 30,
           "font": "Inter-Regular.otf", "color": "#8a94a6"}]}]

LAYERS = L
