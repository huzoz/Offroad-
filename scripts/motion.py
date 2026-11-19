"""Per-second motion signals for off-road footage.

Engines are loud all the time, so loudness alone is a weak signal. This script looks at the picture:

- rotation:  how fast the frame rotates (deg/s). A car-mounted camera rotates with the car, so tilts,
             side slopes and rollovers show up here.
- residual:  motion left after removing the camera's own movement. Mud and water flying, a car
             flipping or sliding in front of a fixed camera.
- shake:     high-frequency jitter of the camera (bumps, jumps, hard landings).
- energy:    plain frame difference (overall action).
- cuts:      hard scene cuts in edited videos; signals are zeroed there so a cut never looks like action.

Frames are decoded by ffmpeg at a low rate (default 5 fps, 320 px wide, grayscale), so a 60-minute
video takes about a minute on a normal CPU.

usage: python motion.py <video> [--fps 5] [--width 320] [--out motion.json]
"""
import argparse, json, math, subprocess, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe, save_json, tool

CUT_DIFF = 45.0  # mean abs gray difference (0-255) above which a frame pair counts as a scene cut


def frames(video, fps, width):
    v = next(s for s in ffprobe(video)["streams"] if s.get("codec_type") == "video")
    sw, sh = int(v["width"]), int(v["height"])
    h = max(2, int(round(width * sh / sw / 2)) * 2)
    cmd = [tool("ffmpeg"), "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={width}:{h},format=gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = width * h
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, width)
    finally:
        p.stdout.close()
        p.wait()


def pair_stats(prev, cur, cv2):
    """rotation (deg), translation (px), residual motion, plain diff for one frame pair."""
    diff = float(cv2.absdiff(prev, cur).mean())
    if diff > CUT_DIFF:
        return None, diff
    p0 = cv2.goodFeaturesToTrack(prev, maxCorners=200, qualityLevel=0.01, minDistance=8)
    rot, tx, ty, resid = 0.0, 0.0, 0.0, diff
    if p0 is not None and len(p0) >= 12:
        p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, cur, p0, None, winSize=(21, 21), maxLevel=3)
        ok = st.reshape(-1) == 1
        if ok.sum() >= 10:
            m, inl = cv2.estimateAffinePartial2D(p0[ok], p1[ok], method=cv2.RANSAC, ransacReprojThreshold=3)
            if m is not None:
                rot = math.degrees(math.atan2(m[1, 0], m[0, 0]))
                tx, ty = float(m[0, 2]), float(m[1, 2])
                warped = cv2.warpAffine(prev, m, (prev.shape[1], prev.shape[0]), borderMode=cv2.BORDER_REPLICATE)
                resid = float(cv2.absdiff(warped, cur)[8:-8, 8:-8].mean())
    return (rot, tx, ty, resid), diff


def analyse(video, fps=5, width=320):
    try:
        import cv2
    except ImportError:
        sys.exit("opencv missing. Run: pip install -r requirements.txt")
    dur = float(ffprobe(video)["format"]["duration"])
    n = int(math.ceil(dur))
    rot = np.zeros(n); resid = np.zeros(n); energy = np.zeros(n); cnt = np.zeros(n)
    trans = [[] for _ in range(n)]
    cuts = []
    prev = None
    for i, f in enumerate(frames(video, fps, width)):
        if prev is not None:
            sec = min(n - 1, int(i / fps))
            st, diff = pair_stats(prev, f, cv2)
            if st is None:
                cuts.append(round(i / fps, 2))
            else:
                r, tx, ty, rs = st
                rot[sec] += abs(r); resid[sec] += rs; energy[sec] += diff; cnt[sec] += 1
                trans[sec].append((tx, ty))
        prev = f
    c = np.maximum(cnt, 1)
    shake = np.zeros(n)
    for s, t in enumerate(trans):
        if len(t) >= 3:
            a = np.asarray(t)
            shake[s] = float(np.abs(np.diff(a, axis=0)).sum(1).mean())  # change of translation = jitter
    out = {"fps": fps, "seconds": n, "rotation": (rot * fps / c).round(3).tolist(),  # deg per second
           "residual": (resid / c).round(3).tolist(), "energy": (energy / c).round(3).tolist(),
           "shake": shake.round(3).tolist(), "cuts": cuts}
    for s in {int(x) for x in cuts}:  # a cut must never look like action
        for k in ("rotation", "residual", "energy", "shake"):
            if s < n:
                out[k][s] = 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--fps", type=float, default=5)
    ap.add_argument("--width", type=int, default=320); ap.add_argument("--out")
    a = ap.parse_args()
    m = analyse(a.video, a.fps, a.width)
    out = Path(a.out) if a.out else Path(a.video).with_name("motion.json")
    save_json(out, m)
    rot = np.asarray(m["rotation"]); res = np.asarray(m["residual"])
    top = np.argsort(-(rot / (rot.std() + 1e-9) + res / (res.std() + 1e-9)))[:8]
    print(f"{m['seconds']} s, {len(m['cuts'])} scene cuts -> {out}")
    for s in sorted(top):
        print(f"  {int(s // 60)}:{int(s % 60):02d}  rotation {rot[s]:.1f} deg/s  residual {res[s]:.1f}")


if __name__ == "__main__":
    main()
