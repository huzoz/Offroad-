"""Contact sheets: 4 frames around each candidate's peak in one small JPG, so Claude (or you) can see
what actually happens before writing a joke or ranking the top 5.

usage: python frames.py jobs/<id> [--pick 2] [--width 400]
Writes jobs/<id>/sheets/pick_<n>.jpg (all candidates without --pick).
"""
import argparse, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import load_json


def sheet(video, times, out, width):
    import cv2, numpy as np
    cap = cv2.VideoCapture(str(video))
    tiles = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, t) * 1000)
        ok, f = cap.read()
        if not ok:
            f = np.zeros((360, 640, 3), np.uint8)
        h = int(f.shape[0] * width / f.shape[1]) // 2 * 2
        f = cv2.resize(f, (width, h))
        label = f"{int(t // 60)}:{t % 60:04.1f}"
        cv2.putText(f, label, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(f, label, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(f)
    cap.release()
    hmin = min(t.shape[0] for t in tiles)
    tiles = [t[:hmin] for t in tiles]
    grid = np.vstack([np.hstack(tiles[0:2]), np.hstack(tiles[2:4])])
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), grid, [cv2.IMWRITE_JPEG_QUALITY, 80])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job"); ap.add_argument("--pick", type=int); ap.add_argument("--width", type=int, default=400)
    a = ap.parse_args()
    d = Path(a.job); c = load_json(d / "candidates.json")
    for x in c["candidates"]:
        if a.pick and x["n"] != a.pick:
            continue
        p = x.get("peak", (x["start"] + x["end"]) / 2)
        times = [max(x["start"], p - 2.5), p, min(x["end"], p + 1.5), min(x["end"], p + 3.5)]
        out = d / "sheets" / f"pick_{x['n']}.jpg"
        sheet(c["source"], times, out, a.width)
        print(out)


if __name__ == "__main__":
    main()
