"""Build a compilation (składanka) from moments of several videos, one file per language.

Every segment carries the source channel in the top-left corner for its whole duration. The first
segment can open with a title box, and every segment can have your own short note (commentary box),
which is the part of the video that is your own work. The description file lists every source with a
YouTube chapter per segment.

The plan is a small JSON file, for example plan.json:

{
  "name": "bloto-listopad",
  "format": "horizontal",            // horizontal = 1920x1080 (long YouTube), vertical = 1080x1920 (Shorts)
  "layout": "blur",                  // blur or fill
  "title": {"pl": "5 razy, kiedy błoto wygrało", "en": "5 times the mud won"},
  "segments": [
    {"job": "jobs/abc123-1a2b3c4d", "pick": 2, "note": {"pl": "Za mało gazu na podjeździe", "en": "Not enough throttle"}},
    {"job": "jobs/xyz789-9f8e7d6c", "start": 61.5, "end": 78, "note": "Wyciągarka ratuje sytuację"}
  ]
}

A note given as plain text is machine translated to the other languages.

usage: python compile.py plan.json [--langs pl,en] [--out-dir compilations] [--no-captions]
"""
import argparse, json, re, sys, tempfile, unicodedata
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe, load_json, run, save_json, tool
from cut import CAP_Y, CREDIT, build_ass, credit_xy, src_size, tr, translate_words, video_filter

SIZES = {"horizontal": (1920, 1080), "vertical": (1080, 1920)}


def read_plan(path):
    txt = Path(path).read_text(encoding="utf-8")
    txt = re.sub(r"^\s*//.*$|(?<=[,\[{\"\d\s])\s*//[^\n\"]*$", "", txt, flags=re.M)  # allow // comments
    return json.loads(txt)


def text_for(v, lang):
    if not v:
        return ""
    if isinstance(v, dict):
        if v.get(lang):
            return v[lang]
        first = next((x for x in v.values() if x), "")
        return tr(first, lang) if first else ""
    return tr(v, lang)


def slug(s):
    s = unicodedata.normalize("NFKD", s.replace("ł", "l").replace("Ł", "L")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")


def fmt(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("--langs", default="pl,en")
    ap.add_argument("--out-dir", default="compilations"); ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--allow-profanity", action="store_true")
    a = ap.parse_args()
    plan = read_plan(a.plan)
    name = slug(plan.get("name") or Path(a.plan).stem) or "compilation"
    form = plan.get("format", "horizontal")
    if form not in SIZES:
        sys.exit(f"format must be horizontal or vertical, not {form!r}")
    w, h = SIZES[form]
    layout = plan.get("layout", "blur")
    scale = 0.75 if form == "horizontal" else 1.0
    cap_y = int(h * 0.82) if form == "horizontal" else CAP_Y[layout]
    segs = plan.get("segments") or []
    if not segs:
        sys.exit("plan has no segments")
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    langs = [x.strip().lower() for x in a.langs.split(",") if x.strip()]
    tmp = Path(tempfile.mkdtemp(prefix="compile-"))
    for lang in langs:
        parts, chapters, sources, t = [], [], [], 0.0
        title = text_for(plan.get("title"), lang)
        for i, sg in enumerate(segs):
            d = Path(sg["job"]); c = load_json(d / "candidates.json")
            if "start" in sg and "end" in sg:
                s0, e0 = float(sg["start"]), float(sg["end"])
            else:
                pk = next((x for x in c["candidates"] if x["n"] == sg.get("pick")), None)
                if pk is None:
                    sys.exit(f"segment {i + 1}: pick {sg.get('pick')} not found in {d}")
                s0, e0 = pk["start"], pk["end"]
            info = c.get("info", {})
            ch = info.get("channel") or info.get("uploader") or ""
            url = "" if info.get("local_file") else (info.get("webpage_url") or "")
            words = []
            if not a.no_captions and (d / "transcript.json").exists():
                words = [x for x in load_json(d / "transcript.json") if s0 <= x["s"] < e0 and x["w"]]
                src_lang = c.get("language") or "en"
                if lang != src_lang:
                    words = translate_words(words, lang, src_lang)
            note = text_for(sg.get("note"), lang)
            hook = title if i == 0 else ""
            credit = CREDIT.get(lang, CREDIT["en"]).format(ch=ch) if ch else ""
            ass = tmp / f"{lang}_{i}.ass"
            ass.write_text(build_ass(words, s0, e0, hook, cap_y, credit, a.allow_profanity, w=w, h=h, note=note,
                                     note_at=2.8 if hook else 0.3, scale=scale,
                                     credit_xy=credit_xy(layout, src_size(c["source"]), w, h)), encoding="utf-8")
            part = tmp / f"{lang}_{i}.mp4"
            has_audio = any(s.get("codec_type") == "audio" for s in ffprobe(c["source"])["streams"])
            cmd = [tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", c["source"]]
            if not has_audio:
                cmd += ["-f", "lavfi", "-t", f"{e0 - s0:.2f}", "-i", "anullsrc=r=48000:cl=stereo"]
            cmd += ["-filter_complex", video_filter(layout, ass, float(sg.get("focus", 0.5)), w, h),
                    "-map", "[vo]", "-map", "0:a" if has_audio else "1:a", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-shortest", str(part)]
            run(cmd)
            parts.append(part)
            chapters.append((t, note or (f"{ch}" if ch else f"Klip {i + 1}")))
            sources.append({"channel": ch, "title": info.get("title"), "url": url, "license": info.get("license"),
                            "start": s0, "end": e0})
            t += float(ffprobe(part)["format"]["duration"])
        lst = tmp / f"{lang}_list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        mp4 = out / f"{name}_{lang}.mp4"
        run([tool("ffmpeg"), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
             "-movflags", "+faststart", str(mp4)])
        save_json(mp4.with_suffix(".json"), {"file": str(mp4), "kind": "compilation", "format": form, "lang": lang,
                                             "start": 0, "end": t, "hook": title, "credit_in_video": True,
                                             "segments": sources})
        head = "Źródła" if lang == "pl" else "Sources"
        lines = [title, "", *(f"{fmt(ct)} {txt}" for ct, txt in chapters), "", f"{head}:"]
        seen = []
        for s in sources:
            row = f"- {s['channel'] or '?'}: {s['title'] or ''} {s['url']}".rstrip()
            if row not in seen:
                seen.append(row)
        lines += seen
        (out / f"{name}_{lang}_opis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(mp4)
        print(out / f"{name}_{lang}_opis.md")


if __name__ == "__main__":
    main()
