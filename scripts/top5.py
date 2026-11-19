"""Countdown video: "Top 5 times offroaders went crazy", narrated by a local AI voice (Chatterbox, GPU).

For each item: the voice says the number and a short joke while the lead-up of the clip plays
(original sound ducked, big "#5" badge, word-by-word captions of the voice), then the action plays
with full sound for a few seconds. Every item carries the source channel in the corner. One video per
language, each with its own voice-over.

plan.json (items listed from #5 down to #1, the best one last):
{
  "name": "top5-crazy",
  "format": "vertical",                        // vertical 1080x1920 (Shorts) or horizontal 1920x1080
  "layout": "blur",
  "title": {"en": "Top 5 times offroaders went crazy", "pl": "Top 5: offroadowcy, którzy przesadzili"},
  "intro": {"en": "Top 5 times offroaders went completely crazy.", "pl": "Pięć razy, kiedy offroadowcy kompletnie przesadzili."},
  "outro": {"en": "Which one would you send it with?", "pl": "A Ty, z którym byś pojechał?"},
  "action_seconds": 6,
  "items": [
    {"job": "jobs/abc-1a2b3c4d", "pick": 3,
     "voice": {"en": "Number five. He said it's only ankle deep.", "pl": "Numer pięć. Mówił, że tam jest po kostki."}},
    ...
  ]
}
Optional per item: "action" (seconds of action after the voice), "peak" (second in the source where
the action happens, default: the candidate's peak), "focus" (fill layout crop position).

usage: python top5.py plan.json [--langs en,pl] [--out-dir compilations] [--voice-pl s.wav] [--voice-en s.wav]
                     [--exaggeration 0.65] [--duck 0.18]
The voice runs in the TTS environment from setup_tts.py (~/.offroad-tts); generated lines are cached in
tts_cache/ so re-rendering after a timing change does not regenerate the voice.
"""
import argparse, hashlib, json, os, re, subprocess, sys, tempfile, wave
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe, load_json, run, save_json, tool
from compile import SIZES, fmt, read_plan, slug, text_for
from cut import CAP_Y, CREDIT, build_ass, credit_xy, src_size, video_filter
from setup_tts import tts_python

NUMBER_WORDS = {"en": "Number", "pl": "Numer"}


def wav_info(path):
    """duration, (speech start, speech end) found by a simple energy gate."""
    with wave.open(str(path)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    dur = len(x) / sr
    hop = int(sr * 0.02)
    n = max(1, len(x) // hop)
    e = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    on = np.where(e > max(0.01, e.max() * 0.06))[0]
    if not len(on):
        return dur, (0.0, dur)
    return dur, (on[0] * hop / sr, min(dur, (on[-1] + 1) * hop / sr))


def spread_words(text, t0, t1):
    """Word timings for captions: words spread over the speech by length (plus a little per word)."""
    ws = text.split()
    if not ws:
        return []
    weights = np.array([len(w) + 2 for w in ws], dtype=float)
    edges = t0 + np.concatenate([[0], np.cumsum(weights)]) / weights.sum() * (t1 - t0)
    return [{"w": w, "s": float(edges[i]), "e": float(edges[i + 1])} for i, w in enumerate(ws)]


def badge_ass(ass_text, label, w, h, dur, scale):
    f = lambda v: int(round(v * scale))
    y = f(330) if h > w else f(40)
    x = w // 2 if h > w else w - f(60)
    an = 8 if h > w else 9
    style = (f"Style: Num,Arial Black,{f(190)},&H0000E5FF,&H0000E5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,"
             f"{f(10)},{f(4)},{an},40,40,0,1")
    ev = (f"Dialogue: 3,0:00:00.00,{int(dur // 3600)}:{int(dur % 3600 // 60):02d}:{dur % 60:05.2f},Num,,0,0,0,,"
          f"{{\\an{an}\\pos({x},{y})\\fscx130\\fscy130\\t(0,160,\\fscx100\\fscy100)}}{label}")
    ass_text = ass_text.replace("\n[Events]", style + "\n\n[Events]", 1)
    return ass_text.rstrip("\n") + "\n" + ev + "\n"


def make_voice(lines, a):
    """Run tts.py in the TTS venv for all lines that are not cached yet."""
    todo = [l for l in lines if not Path(l["out"]).exists()]
    if not todo:
        return
    py = Path(os.environ.get("OFFROAD_TTS_PYTHON") or tts_python())
    if not py.exists():
        sys.exit(f"TTS environment not found ({py}). Run once: python \"{Path(__file__).parent / 'setup_tts.py'}\" --test")
    tmp = Path(tempfile.mkdtemp(prefix="tts-")) / "lines.json"
    tmp.write_text(json.dumps(todo, ensure_ascii=False), encoding="utf-8")
    cmd = [str(py), str(Path(__file__).parent / "tts.py"), "--batch", str(tmp), "--exaggeration", str(a.exaggeration)]
    if a.voice_pl: cmd += ["--voice-pl", a.voice_pl]
    if a.voice_en: cmd += ["--voice-en", a.voice_en]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit("voice generation failed (see the error above)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan"); ap.add_argument("--langs", default="en,pl")
    ap.add_argument("--out-dir", default="compilations"); ap.add_argument("--cache", default="tts_cache")
    ap.add_argument("--voice-pl"); ap.add_argument("--voice-en")
    ap.add_argument("--exaggeration", type=float, default=0.65)
    ap.add_argument("--duck", type=float, default=0.18, help="original sound level under the voice (0-1)")
    ap.add_argument("--speed", type=float, default=1.08, help="voice tempo (1.0 = as generated)")
    a = ap.parse_args()
    plan = read_plan(a.plan)
    form = plan.get("format", "vertical")
    w, h = SIZES[form]
    layout = plan.get("layout", "blur")
    scale = 0.75 if form == "horizontal" else 1.0
    cap_y = int(h * 0.82) if form == "horizontal" else CAP_Y[layout]
    items = plan.get("items") or []
    if not items:
        sys.exit("plan has no items")
    name = slug(plan.get("name") or Path(a.plan).stem) or "top"
    langs = [x.strip().lower() for x in a.langs.split(",") if x.strip()]
    act_default = float(plan.get("action_seconds", 6))
    cache = Path(a.cache)
    # 1. voice lines for every language (written by the human/Claude per language, never machine translated)
    lines = {}
    for lang in langs:
        for i, it in enumerate(items):
            txt = text_for(it.get("voice"), lang) if isinstance(it.get("voice"), dict) and it["voice"].get(lang) else ""
            if not txt:
                sys.exit(f"item {i + 1}: no voice text for '{lang}'. Write it in the plan (jokes do not translate well).")
            if i == 0 and isinstance(plan.get("intro"), dict) and plan["intro"].get(lang):
                txt = plan["intro"][lang].strip() + " " + txt
            key = hashlib.sha1(json.dumps([txt, lang, a.voice_pl if lang == "pl" else a.voice_en, a.exaggeration]).encode()).hexdigest()[:16]
            lines[(lang, i)] = {"text": txt, "lang": lang, "out": str(cache / f"{key}.wav")}
        if isinstance(plan.get("outro"), dict) and plan["outro"].get(lang):
            txt = plan["outro"][lang].strip()
            key = hashlib.sha1(json.dumps([txt, lang, a.voice_pl if lang == "pl" else a.voice_en, a.exaggeration]).encode()).hexdigest()[:16]
            lines[(lang, "outro")] = {"text": txt, "lang": lang, "out": str(cache / f"{key}.wav")}
    make_voice(list(lines.values()), a)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="top5-"))
    n = len(items)

    def render(lang, k, c, s0, e0, vo, hook, badge, focus):
        """One part: source [s0, e0], voice from the start (ducked bed), captions of the voice, badge, credit."""
        info = c.get("info", {})
        ch = info.get("channel") or info.get("uploader") or ""
        seg = e0 - s0
        words, vend = [], 0.0
        if vo:
            vdur, (sp0, sp1) = wav_info(vo["out"])
            words = spread_words(vo["text"], s0 + sp0 / a.speed, s0 + sp1 / a.speed)
            vend = vdur / a.speed + 0.15
        credit = CREDIT.get(lang, CREDIT["en"]).format(ch=ch) if ch else ""
        ass_txt = build_ass(words, s0, e0, hook, cap_y, credit, w=w, h=h, scale=scale,
                            credit_xy=credit_xy(layout, src_size(c["source"]), w, h))
        if hook and vo and vend > 2.6:  # keep the title/question on screen while it is spoken
            ass_txt = ass_txt.replace(",0:00:02.60,Hook,", f",0:00:{vend:05.2f},Hook,", 1)
        if badge:
            ass_txt = badge_ass(ass_txt, badge, w, h, seg, scale)
        ass = tmp / f"{lang}_{k}.ass"
        ass.write_text(ass_txt, encoding="utf-8")
        has_audio = any(x.get("codec_type") == "audio" for x in ffprobe(c["source"])["streams"])
        part = tmp / f"{lang}_{k}.mp4"
        cmd = [tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{s0:.2f}", "-to", f"{e0:.2f}", "-i", c["source"]]
        nxt = 1
        if vo:
            cmd += ["-i", vo["out"]]; nxt = 2
        bed_in = "0:a"
        if not has_audio:
            cmd += ["-f", "lavfi", "-t", f"{seg:.2f}", "-i", "anullsrc=r=48000:cl=stereo"]
            bed_in = f"{nxt}:a"
        tempo = f"atempo={a.speed:.3f}," if abs(a.speed - 1) > 1e-3 else ""
        if vo:
            audio = (f"[{bed_in}]aresample=48000,aformat=channel_layouts=stereo,"
                     f"volume='if(lt(t,{vend:.2f}),{a.duck},1)':eval=frame[bed];"
                     f"[1:a]{tempo}aresample=48000,aformat=channel_layouts=stereo,volume=1.6,apad[voice];"
                     f"[bed][voice]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[ao]")
        else:
            audio = f"[{bed_in}]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
        cmd += ["-filter_complex", video_filter(layout, ass, focus, w, h) + ";" + audio,
                "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
                "-t", f"{seg:.2f}", str(part)]
        run(cmd)
        return part, ch, info

    for lang in langs:
        parts, chapters, sources, t = [], [], [], 0.0
        title = text_for(plan.get("title"), lang) if isinstance(plan.get("title"), dict) else (plan.get("title") or "")
        last = None
        for i, it in enumerate(items):
            num = n - i
            d = Path(it["job"]); c = load_json(d / "candidates.json")
            pk = next((x for x in c["candidates"] if x["n"] == it.get("pick")), None)
            if pk is None and "peak" not in it:
                sys.exit(f"item {i + 1}: pick {it.get('pick')} not found in {d} (or give \"peak\")")
            peak = float(it.get("peak", pk["peak"] if pk else 0))
            vo = lines[(lang, i)]
            vplay = wav_info(vo["out"])[0] / a.speed
            action = float(it.get("action", act_default))
            src_dur = float(c.get("duration") or ffprobe(c["source"])["format"]["duration"])
            s0 = peak - vplay - 1.0          # the lead-up plays under the voice, the action lands right after it
            e0 = s0 + vplay + action
            if s0 < 0:
                s0, e0 = 0.0, vplay + action
            if e0 > src_dur:
                e0 = src_dur; s0 = max(0.0, e0 - vplay - action)
            part, ch, info = render(lang, i, c, s0, e0, vo, title if i == 0 else "", f"#{num}", float(it.get("focus", 0.5)))
            parts.append(part)
            chapters.append((t, f"#{num}" + (f" {ch}" if ch else "")))
            url = "" if info.get("local_file") else (info.get("webpage_url") or "")
            sources.append({"channel": ch, "title": info.get("title"), "url": url, "license": info.get("license"),
                            "start": round(s0, 2), "end": round(e0, 2), "voice": vo["text"]})
            t += float(ffprobe(part)["format"]["duration"])
            last = (c, e0, src_dur, float(it.get("focus", 0.5)))
        if (lang, "outro") in lines:  # question to the viewers over the end of the #1 clip
            vo = lines[(lang, "outro")]
            c, e_last, src_dur, focus = last
            ln = wav_info(vo["out"])[0] / a.speed + 0.8
            s0 = e_last if e_last + ln <= src_dur else max(0.0, src_dur - ln)
            q = plan["outro"][lang]
            part, _, _ = render(lang, "outro", c, s0, s0 + ln, vo, q, "", focus)
            parts.append(part)
            t += float(ffprobe(part)["format"]["duration"])
        lst = tmp / f"{lang}_list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        mp4 = out / f"{name}_{lang}.mp4"
        run([tool("ffmpeg"), "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
             "-movflags", "+faststart", str(mp4)])
        save_json(mp4.with_suffix(".json"), {"file": str(mp4), "kind": "compilation", "format": form, "lang": lang,
                                             "start": 0, "end": t, "hook": title, "credit_in_video": True,
                                             "voice": "Chatterbox Multilingual (local AI)", "segments": sources})
        head = "Źródła" if lang == "pl" else "Sources"
        rows = []
        for x in sources:
            r = f"- {x['channel'] or '?'}: {x['title'] or ''} {x['url']}".rstrip()
            if r not in rows:
                rows.append(r)
        desc = [title, ""]
        if form == "horizontal":
            desc += [f"{fmt(ct)} {txt}" for ct, txt in chapters] + [""]
        desc += [f"{head}:", *rows]
        (out / f"{name}_{lang}_opis.md").write_text("\n".join(desc) + "\n", encoding="utf-8")
        if form == "vertical" and t > 60:
            print(f"warning: {mp4.name} is {t:.0f} s, over 60 s. Shorten the lines or lower action_seconds.", file=sys.stderr)
        print(f"{mp4}  ({t:.0f} s)")
        print(out / f"{name}_{lang}_opis.md")

if __name__ == "__main__":
    main()
