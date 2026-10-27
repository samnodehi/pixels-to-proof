import numpy as np
import pytest

from pixels_to_proof import measure, scale, verdict


def synthetic_jump(v0=0.5, angle=60.0, fps=3200.0, mm_per_px=0.03, noise_px=0.5, rest=40, seed=0):
    rng = np.random.default_rng(seed)
    a = np.radians(angle)
    vx, vy = v0 * np.cos(a), v0 * np.sin(a)
    t_flight = 2 * vy / measure.G
    n = int(t_flight * fps)
    t = np.arange(n) / fps
    x = np.concatenate([np.zeros(rest), vx * t])
    y = np.concatenate([np.zeros(rest), vy * t - 0.5 * measure.G * t ** 2])
    y = np.concatenate([y, np.zeros(rest)])
    x = np.concatenate([x, np.full(rest, x[-1])])
    cx = 300 + x * 1000 / mm_per_px + rng.normal(0, noise_px, len(x))
    cy = 600 - y * 1000 / mm_per_px + rng.normal(0, noise_px, len(y))
    return np.arange(len(cx)), cx, cy


@pytest.mark.parametrize("v0,angle", [(0.4, 75.0), (0.8, 45.0), (1.2, 30.0)])
def test_kinematics_recovers_known_flight(v0, angle):
    f, cx, cy = synthetic_jump(v0=v0, angle=angle)
    k = measure.kinematics(f, cx, cy, 3200.0, 0.03)
    assert abs(k.g_fit_rel_err) < 0.03
    assert abs(k.v0_ballistic - v0) / v0 < 0.03
    assert abs(k.angle_deg - angle) < 2.0
    mid, lo, hi = measure.speed_interval(k, 0.0)
    assert lo <= v0 * 1.02 and hi >= v0 * 0.98


def test_wrong_time_base_fails_gravity_check():
    f, cx, cy = synthetic_jump(v0=0.6, angle=60.0)
    k = measure.kinematics(f, cx, cy, 1600.0, 0.03)       # half the true fps -> g off by 4x
    v = verdict.decide(0.6, None, *measure.speed_interval(k, 0.0), k.g_fit_rel_err)
    assert v.label == verdict.CANNOT_MEASURE


def test_grid_scale_on_synthetic_image():
    img = np.full((400, 900), 220, np.uint8)
    for x in np.arange(20, 900, 123.4):
        img[:, int(round(x)) - 2:int(round(x)) + 3] = 90
    g = scale.grid_from_frame(img, "x", (0, 400))
    assert abs(g.spacing_px - 123.4) < 0.6
    assert g.mm_per_px(5.0) == pytest.approx(5.0 / g.spacing_px)


def test_verdict_rules():
    assert verdict.decide(0.40, 0.02, 0.41, 0.38, 0.44, 0.01).label == verdict.REPRODUCED
    assert verdict.decide(0.60, 0.02, 0.41, 0.38, 0.44, 0.01).label == verdict.NOT_REPRODUCED
    assert verdict.decide(0.41, None, 0.41, 0.38, 0.44, 0.25).label == verdict.CANNOT_MEASURE


def test_gravity_timebase_recovers_frame_rate():
    f, cx, cy = synthetic_jump(v0=0.7, angle=40.0, fps=3200.0, mm_per_px=0.03, noise_px=0.5)
    fps, lo, hi = measure.gravity_timebase(f, cx, cy, 0.03)
    assert abs(fps - 3200.0) / 3200.0 < 0.02
    assert lo <= 3200.0 * 1.01 and hi >= 3200.0 * 0.99


def test_platform_gap_on_synthetic_median():
    img = np.full((300, 500), 200, np.uint8)
    img[200:206, 0:140] = 120          # take-off rod from the left edge, tip at x = 139
    img[230:236, 380:500] = 120        # landing rod from the right edge, tip at x = 380
    g = scale.platform_gap(img)
    assert abs(g.left_tip_px - 139) <= 3 and abs(g.right_tip_px - 380) <= 3


def test_free_flight_check_is_near_zero_for_ballistic_motion():
    f, cx, cy = synthetic_jump(v0=0.8, angle=45.0)
    k = measure.kinematics(f, cx, cy, 3200.0, 0.03)
    assert k.ax_rel_g < 0.03


def test_sideways_acceleration_fails_the_free_flight_check():
    assert verdict.decide(0.41, None, 0.41, 0.38, 0.44, 0.01, 0.30).label == verdict.CANNOT_MEASURE
    assert verdict.decide(0.41, None, 0.41, 0.38, 0.44, 0.01, 0.02).label == verdict.REPRODUCED


def test_repair_dropped_frames_restores_the_timeline():
    f, cx, cy = synthetic_jump(v0=0.8, angle=30.0, noise_px=0.2)
    keep = np.ones(len(f), bool)
    moving = np.where(np.hypot(np.diff(cx), np.diff(cy)) > 3)[0]
    dropped = moving[20:-20:14]           # one frame in fourteen removed, as in an edited montage
    keep[dropped] = False
    g, x, y = np.arange(keep.sum()), cx[keep], cy[keep]   # the edited video renumbers its frames
    fixed, at = measure.repair_dropped_frames(g, x, y, 0.03)
    assert len(at) == len(dropped)
    assert (fixed == f[keep] - f[keep][0]).all()
    assert abs(measure.kinematics(fixed, x, y, 3200.0, 0.03).g_fit_rel_err) < 0.03
    none_fixed, none_at = measure.repair_dropped_frames(f, cx, cy, 0.03)
    assert none_at == [] and (none_fixed == f).all()
