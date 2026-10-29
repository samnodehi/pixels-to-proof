import sys, cv2, numpy as np
from render import frame
from timeline import LAYERS
ts = [float(x) for x in sys.argv[2:]]
ims = [cv2.resize(frame(LAYERS, t), (640, 360), interpolation=cv2.INTER_AREA) for t in ts]
for im, t in zip(ims, ts): cv2.putText(im, f"{t:.1f}", (8, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
rows = [np.hstack(ims[i:i + 2] + [np.zeros_like(ims[0])] * (2 - len(ims[i:i + 2]))) for i in range(0, len(ims), 2)]
cv2.imwrite(sys.argv[1], np.vstack(rows))
