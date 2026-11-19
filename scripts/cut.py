"""Cut one candidate into finished vertical clips, one per language.

1080x1920, 30 fps, word-by-word burned captions, hook box in the first seconds, a small credit line
with the source channel for the whole clip, loudness normalised to -14 LUFS.

The spoken language (detected by moments.py) keeps the original transcript. Other languages get a
machine translation spread over the same timing. Hooks you do not give for a language are translated
from the first hook you gave.

Writes jobs/<id>/edits/clip_<n>_<lang>.mp4 (+ .json for check.py) and clip_<n>_captions.md with
ready post captions per platform and language, credit included.

usage: python cut.py jobs/<id> --pick 1 [--langs pl,en] [--hook "pl=Tego nikt się nie spodziewał"]
                     [--hook "en=Nobody expected this"] [--layout blur|fill] [--focus 0.5]
                     [--captions word|none] [--start S --end E] [--no-credit] [--allow-profanity]
"""
import argparse, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import load_json, run, save_json, tool

W, H = 1080, 1920
CAP_Y = {"fill": 1380, "blur": 1460}
CREDIT = {"pl": "Źródło: {ch} (YouTube)", "en": "Source: {ch} (YouTube)"}
HASHTAGS = {"pl": ["#offroad", "#4x4", "#offroadpolska", "#terenówka", "#błoto"],
            "en": ["#offroad", "#4x4", "#offroading", "#mud", "#overland"]}

_SLURS = re.compile(r"\b(nigg\w*|n[i1]gg?a\w*|f[a@]gg?\w*|retard\w*|tranny\w*|pedał\w*|ciot\w*)\b", re.I)
_SWEARS = re.compile(r"\b(fuck\w*|motherfuck\w*|shit\w*|bitch\w*|cunt\w*|dick\w*|asshole\w*|bastard\w*|"
                     r"kurw\w*|chuj\w*|huj\w*|pierdol\w*|pierdal\w*|jeb\w*|zajeb\w*|wyjeb\w*|pizd\w*|skurw\w*|spierd\w*)\b", re.I)


def _mask(m):
    w = m.group(0)
    return w[0] + "*" * (len(w) - 1)


def clean(s, profanity=False):
    s = _SLURS.sub(_mask, s)
    return s if profanity else _SWEARS.sub(_mask, s)


def ts(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def esc(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(words, s0, e0, hook, cap_y, credit="", profanity=False, w=W, h=H, note="", note_at=0.0, scale=1.0, credit_xy=None):
    """ASS subtitles: word captions, hook box (first 2.6 s), credit in the top-left corner for the whole
    clip, optional note box (own commentary) from note_at for 4 s."""
    f = lambda x: int(round(x * scale))
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial Black,{f(92)},&H00FFFFFF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{f(7)},3,5,60,60,0,1
Style: Hook,Arial Black,{f(68)},&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,{f(18)},0,8,70,70,{f(190)},1
Style: Note,Arial Black,{f(54)},&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,{f(16)},0,8,70,70,{f(190)},1
Style: Credit,Arial,{f(38)},&H20FFFFFF,&H20FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,7,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    ws = [dict(x, w=clean(x["w"], profanity)) for x in words if s0 <= x["s"] < e0 and x["w"]]
    groups, cur = [], []
    for x in ws:  # up to 3 words per caption, break on punctuation or pauses
        if cur and (len(cur) == 3 or x["s"] - cur[-1]["e"] > 0.6 or cur[-1]["w"][-1:] in ".?!,"):
            groups.append(cur); cur = []
        cur.append(x)
    if cur:
        groups.append(cur)
    for gi, g in enumerate(groups):
        g_end = groups[gi + 1][0]["s"] if gi + 1 < len(groups) else g[-1]["e"] + 0.4
        g_end = min(g_end, g[-1]["e"] + 0.8)
        for k, x in enumerate(g):
            a = x["s"] - s0; b = (g[k + 1]["s"] - s0) if k + 1 < len(g) else g_end - s0
            if b <= a:
                continue
            parts = []
            for j, y in enumerate(g):
                t = esc(y["w"].upper())
                parts.append("{\\c&H0000E5FF&}" + t + "{\\c&H00FFFFFF&}" if j == k else t)
            pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if k == 0 else ""
            ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\pos({w // 2},{cap_y})}}{pop}{' '.join(parts)}")
    if hook:
        ev.append(f"Dialogue: 1,{ts(0)},{ts(2.6)},Hook,,0,0,0,,{{\\fad(0,180)\\fscx92\\fscy92\\t(0,120,\\fscx100\\fscy100)}}{esc(hook)}")
    if note:
        ev.append(f"Dialogue: 1,{ts(note_at)},{ts(min(e0 - s0, note_at + 4))},Note,,0,0,0,,{{\\fad(150,200)}}{esc(note)}")
    if credit:
        cx, cy = credit_xy or (f(36), f(40))
        ev.append(f"Dialogue: 2,{ts(0)},{ts(e0 - s0)},Credit,,0,0,0,,{{\\an7\\pos({cx},{cy})}}{esc(credit)}")
    return hdr + "\n".join(ev) + "\n"


def credit_xy(layout, src, w=W, h=H):
    """Top-left corner of the source picture, kept clear of the app UI at the top of vertical feeds."""
    if w > h:
        return 28, 28
    if layout == "blur" and src:
        fg_h = int(w * src[1] / src[0])
        top = (h - fg_h) // 2 - 80
        if fg_h < h and top >= 200:
            return 30, top + 14
    return 36, 1230  # fill: above the captions, below the top UI


def src_size(path):
    from common import ffprobe
    v = next((s for s in ffprobe(path)["streams"] if s.get("codec_type") == "video"), None)
    return (int(v["width"]), int(v["height"])) if v else None


def video_filter(layout, ass, focus=0.5, w=W, h=H):
    """fill: crop to fill the frame at a horizontal focus point. blur: the whole picture over a blurred copy."""
    if layout == "fill":
        v = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
             f"crop={w}:{h}:(iw-{w})*{focus:.3f}:(ih-{h})/2,setsar=1[v]")
    else:
        dy = -80 if h > w else 0
        v = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=24:2,"
             f"eq=brightness=-0.08[bg];[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
             f"[bg][fg]overlay=(W-w)/2:(H-h)/2+{dy},setsar=1[v]")
    sub = str(ass).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return v + f";[v]fps=30,subtitles='{sub}'[vo]"


# ---- translation -------------------------------------------------------------------------------

_TR = {}


def tr(text, target, source="auto"):
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        sys.exit("deep-translator missing. Run: pip install -r requirements.txt")
    key = (source, target)
    if key not in _TR:
        _TR[key] = GoogleTranslator(source=source, target=target)
    try:
        return (_TR[key].translate(text) or text).strip()
    except Exception as e:  # network or rate limit: keep the original rather than crash
        print(f"warning: translation to {target} failed ({str(e)[:80]}); keeping original text", file=sys.stderr)
        return text


def sentences(words):
    out, cur = [], []
    for w in words:
        if cur and w["s"] - cur[-1]["e"] > 0.8:
            out.append(cur); cur = []
        cur.append(w)
        if w["w"][-1:] in ".?!":
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def translate_words(words, target, source):
    """Translate sentence by sentence, then spread the new words evenly over each sentence's timing."""
    res = []
    for sent in sentences(words):
        new = tr(" ".join(w["w"] for w in sent), target, source or "auto").split()
        if not new:
            continue
        a, b = sent[0]["s"], sent[-1]["e"]
        step = (b - a) / len(new)
        res += [{"w": x, "s": a + i * step, "e": a + (i + 1) * step} for i, x in enumerate(new)]
    return res


# ---- captions for the post ----------------------------------------------------------------------

def post_block(lang, hook, channel, url):
    cred = ("🎥 " + (f"{channel}: {url}" if channel else url)) if url else ""
    tags = HASHTAGS.get(lang, HASHTAGS["en"])
    x = "\n".join(p for p in [hook, cred] if p)
    ig = "\n".join(p for p in [hook, cred, " ".join(tags[:4])] if p)
    tk = "\n".join(p for p in [hook, cred, " ".join(tags[:3])] if p)
    return (f"## {lang}\n\n**X** (bez hashtagów)\n\n{x}\n\n**Instagram Reels** (4 hashtagi)\n\n{ig}\n\n"
            f"**TikTok / YouTube Shorts**\n\n{tk}\n")


def parse_hooks(items):
    hooks = {}
    for it in items:
        if "=" in it and len(it.split("=", 1)[0]) <= 3:
            k, v = it.split("=", 1)
            hooks[k.strip().lower()] = v.strip()
        else:
            hooks.setdefault("_", it.strip())
    return hooks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("job"); ap.add_argument("--pick", type=int, default=1)
    ap.add_argument("--langs", default="pl,en")
    ap.add_argument("--hook", action="append", default=[], help='"pl=TEXT" (repeat per language) or just "TEXT"')
    ap.add_argument("--layout", choices=["blur", "fill"], default="blur")
    ap.add_argument("--focus", type=float, default=0.5, help="fill layout: horizontal crop position 0 (left) .. 1 (right)")
    ap.add_argument("--captions", choices=["word", "none"], default="word")
    ap.add_argument("--start", type=float); ap.add_argument("--end", type=float)
    ap.add_argument("--no-credit", action="store_true", help="no credit line in the video (still in the post captions)")
    ap.add_argument("--allow-profanity", action="store_true")
    a = ap.parse_args()
    d = Path(a.job); c = load_json(d / "candidates.json")
    pick = next((x for x in c["candidates"] if x["n"] == a.pick), None)
    if pick is None and (a.start is None or a.end is None):
        sys.exit(f"candidate {a.pick} not found in {d / 'candidates.json'}")
    s0 = a.start if a.start is not None else pick["start"]
    e0 = a.end if a.end is not None else pick["end"]
    words = load_json(d / "transcript.json") if (d / "transcript.json").exists() and a.captions != "none" else []
    words = [w for w in words if s0 <= w["s"] < e0 and w["w"]]
    src_lang = c.get("language") or "en"
    info = c.get("info", {})
    channel, url = info.get("channel") or info.get("uploader") or "", info.get("webpage_url") or ""
    if info.get("local_file"):
        url = ""
    hooks = parse_hooks(a.hook)
    base_hook = next(iter(hooks.values()), "")
    langs = [x.strip().lower() for x in a.langs.split(",") if x.strip()]
    out = d / "edits"; out.mkdir(exist_ok=True)
    caps = ["# Opisy do posta", "", f"Źródło: {info.get('title') or ''} ({channel})", f"Licencja: {info.get('license') or 'standardowa YouTube'}",
            "Tłumaczenia są maszynowe. Przeczytaj każde przed publikacją.", ""]
    for lang in langs:
        hook = hooks.get(lang) or (tr(base_hook, lang) if base_hook else "")
        lw = words if lang == src_lang else translate_words(words, lang, src_lang)
        credit = "" if a.no_credit or not channel else CREDIT.get(lang, CREDIT["en"]).format(ch=channel)
        ass = out / f"clip_{a.pick}_{lang}.ass"
        ass.write_text(build_ass(lw, s0, e0, hook, CAP_Y[a.layout], credit, a.allow_profanity,
                                 credit_xy=credit_xy(a.layout, src_size(c["source"]))), encoding="utf-8")
        mp4 = out / f"clip_{a.pick}_{lang}.mp4"
        run([tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", c["source"],
             "-filter_complex", video_filter(a.layout, ass, a.focus), "-map", "[vo]", "-map", "0:a?",
             "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", str(mp4)])
        save_json(mp4.with_suffix(".json"), {"file": str(mp4), "lang": lang, "start": s0, "end": e0, "layout": a.layout,
                                             "hook": hook, "credit_in_video": bool(credit), "source_url": url,
                                             "source_title": info.get("title"), "source_channel": channel,
                                             "source_license": info.get("license")})
        caps.append(post_block(lang, hook, channel, url))
        print(mp4)
    cf = out / f"clip_{a.pick}_captions.md"
    cf.write_text("\n".join(caps), encoding="utf-8")
    print(cf)


if __name__ == "__main__":
    main()
