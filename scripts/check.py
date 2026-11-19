"""Pre-post check of a finished clip or compilation.

usage: python check.py <video.mp4> [--caption "post text"] [--permissions permissions.md] [--strict]

Reads the .json written by cut.py / compile.py next to the video. Checks:
- format: 1080x1920 for clips and vertical compilations, 1920x1080 for horizontal ones; ~30 fps; audio
- length: 7-60 s for vertical clips (Shorts/Reels/TikTok), at least 60 s for horizontal compilations
- credit: the channel name is burned into the video, and the post text names the channel or links it
  (pass --caption, or the script reads clip_<n>_captions.md / <name>_<lang>_opis.md)
- source rights: CC licence or a permission noted in permissions.md -> PASS, otherwise WARN
  (FAIL with --strict). This is a reminder, not a legal opinion.
Exit code 1 on any FAIL.
"""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe, load_json


def fps_of(s):
    try:
        a, b = s.split("/"); return float(a) / float(b)
    except Exception:
        return 0.0


def post_text(clip, meta):
    """The caption file written next to the video, if any."""
    m = re.match(r"(clip_\d+)_[a-z]{2}$", clip.stem)
    cands = []
    if m:
        cands.append(clip.with_name(f"{m.group(1)}_captions.md"))
    cands.append(clip.with_name(f"{clip.stem}_opis.md"))
    for c in cands:
        if c.exists():
            return c.read_text(encoding="utf-8", errors="replace"), c.name
    return "", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip"); ap.add_argument("--caption", default="")
    ap.add_argument("--permissions", default="permissions.md"); ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    clip = Path(a.clip)
    if not clip.exists():
        sys.exit(f"FAIL file not found: {clip}")
    side = clip.with_suffix(".json")
    meta = load_json(side) if side.exists() else {}
    res = []

    def add(level, name, detail=""):
        res.append((level, name, detail))

    p = ffprobe(clip)
    st = p.get("streams", [])
    v = next((s for s in st if s.get("codec_type") == "video"), None)
    au = next((s for s in st if s.get("codec_type") == "audio"), None)
    dur = float(p.get("format", {}).get("duration", 0) or 0)
    horizontal = meta.get("format") == "horizontal"
    want = (1920, 1080) if horizontal else (1080, 1920)
    got = (v.get("width"), v.get("height")) if v else None
    add("PASS" if got == want else "FAIL", f"rozdzielczość {want[0]}x{want[1]}", f"{got[0]}x{got[1]}" if got else "brak wideo")
    f = fps_of(v.get("r_frame_rate", "0/1")) if v else 0
    add("PASS" if 29 <= f <= 31 else "FAIL", "ok. 30 fps", f"{f:.2f}")
    add("PASS" if au else "FAIL", "jest dźwięk")
    if horizontal:
        add("PASS" if dur >= 60 else "WARN", "długość składanki min. 60 s", f"{dur:.1f}s")
    else:
        add("PASS" if 7 <= dur <= 60 else "FAIL", "długość 7-60 s", f"{dur:.1f}s")
        if dur > 40:
            add("WARN", "krótsze klipy zwykle lepiej trzymają widza", f"{dur:.0f}s > 40 s")
    # credit
    sources = meta.get("segments") or ([{"channel": meta.get("source_channel"), "url": meta.get("source_url"),
                                          "license": meta.get("source_license")}] if meta else [])
    if not meta:
        add("WARN", "brak pliku .json obok wideo", "nie da się sprawdzić źródeł")
    add("PASS" if meta.get("credit_in_video") else "FAIL", "nazwa kanału w rogu kadru",
        "" if meta.get("credit_in_video") else "przytnij ponownie bez --no-credit")
    text, fname = (a.caption, "--caption") if a.caption else post_text(clip, meta)
    if not text:
        add("WARN", "opis posta", "nie podano --caption i brak pliku z opisem")
    else:
        low = text.lower()
        missing = [s.get("channel") or s.get("url") for s in sources
                   if not ((s.get("channel") and s["channel"].lower() in low) or (s.get("url") and s["url"].lower() in low))]
        add("FAIL" if missing else "PASS", f"źródło w opisie ({fname})", ("brak: " + ", ".join(m for m in missing if m)) if missing else "")
    # rights
    perm = Path(a.permissions).read_text(encoding="utf-8", errors="replace").lower() if Path(a.permissions).exists() else ""
    done = set()
    for s in sources:
        ch = s.get("channel") or "?"
        if ch in done:
            continue
        done.add(ch)
        if "creative commons" in (s.get("license") or "").lower():
            add("PASS", f"prawa: {ch}", "licencja CC BY")
        elif ch != "?" and ch.lower() in perm:
            add("PASS", f"prawa: {ch}", f"zgoda w {a.permissions}")
        else:
            add("FAIL" if a.strict else "WARN", f"prawa: {ch}", "brak licencji CC i brak zgody: możliwe zgłoszenie / Content ID")
    for lvl, n, d in res:
        print(f"{lvl:4}  {n}" + (f"  [{d}]" if d else ""))
    bad = [r for r in res if r[0] == "FAIL"]
    print("WYNIK: " + ("FAIL" if bad else "PASS") + (f" ({sum(r[0] == 'WARN' for r in res)} ostrzeżeń)" if not bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
