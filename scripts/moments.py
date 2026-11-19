"""Find the best clip moments in an off-road video (YouTube URL or local file).

Signals per second (a missing signal is skipped, never faked):
- motion:        rotation, residual motion and shake from motion.py (tilts, rollovers, splashes, jumps)
- most replayed: the YouTube heatmap, the strongest signal when a video has one
- hype words:    Polish and English exclamations in the transcript ("o matko", "send it", "utknął")
- loudness:      jumps above the local level; weighted low, because engines are loud all the time

Writes jobs/<id>/candidates.md + candidates.json, transcript.json, motion.json, info.json.

usage: python moments.py <url-or-file> [--top 8] [--min 12] [--max 40] [--max-minutes 90]
                         [--model small] [--no-transcript] [--channel NAME --source-url URL]  (local files)
"""
import argparse, math, re, sys, wave
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from common import ffprobe, is_url, job_dir, load_json, run, save_json, tool, ytdlp_base, ytdlp_json
from motion import analyse

HYPE = re.compile(
    r"(?<!\w)("
    # English
    r"no way|oh my god|omg|wow|whoa|holy|send it|let'?s go|go go|oh no|stuck|careful|look at that|insane|crazy|"
    r"wtf|dude|bro|flip(ped)?|roll(ed)? over|winch|full send|nope|"
    # Polish
    r"o matko|matko|o kurde|kurde|kurcze|o jezu|jezu|o boże|uwaga|trzymaj|dawaj|jedziesz|gazu|ale jazda|"
    r"o kurwa|kurwa|ja pierdzie|o żesz|szok|petarda|utknął|utknęła|zakopał|zakopany|przewrócił|wywrotka|"
    r"wyciągarka|stop|nie dam rady|uda się|udało się|łooo+|wooo+"
    r")(?!\w)", re.I)


def fetch(src, d, max_min, channel=None, source_url=None):
    info = {}
    if is_url(src):
        info = ytdlp_json(src)
        save_json(d / "info.json", {k: info.get(k) for k in ("id", "title", "uploader", "channel", "channel_url", "uploader_id",
                                                             "webpage_url", "duration", "view_count", "upload_date",
                                                             "heatmap", "license")})
        vid = d / "source.mp4"
        if not vid.exists():
            args = ytdlp_base() + ["-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b", "--merge-output-format", "mp4",
                                   "-o", str(vid)]
            if (info.get("duration") or 0) > max_min * 60:
                args += ["--download-sections", f"*0-{max_min * 60}"]
            run(args + [src])
    else:
        vid = Path(src).resolve()
        if not vid.exists():
            sys.exit(f"file not found: {vid}")
        prev = load_json(d / "info.json") if (d / "info.json").exists() else {}
        save_json(d / "info.json", {"title": prev.get("title") or vid.stem,
                                    "webpage_url": source_url or prev.get("webpage_url") or "",
                                    "channel": channel or prev.get("channel"), "license": prev.get("license"),
                                    "local_file": not (source_url or prev.get("webpage_url"))})
    return vid, info


def audio_rms(vid, d):
    wav = d / "audio.wav"
    if not wav.exists():
        run([tool("ffmpeg"), "-y", "-v", "error", "-i", str(vid), "-ac", "1", "-ar", "16000", str(wav)])
    with wave.open(str(wav)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    n = max(1, len(x) // 16000)
    x = np.pad(x, (0, max(0, n * 16000 - len(x))))
    rms = np.sqrt((x[: n * 16000].reshape(n, 16000) ** 2).mean(1) + 1e-9)
    return wav, 20 * np.log10(rms)


def transcribe(wav, d, model_name):
    """Word timestamps with faster-whisper. Language is detected and saved (pl, en, ...)."""
    out, meta = d / "transcript.json", d / "transcript_meta.json"
    if out.exists():
        return load_json(out), (load_json(meta) if meta.exists() else {}).get("language")
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("faster-whisper missing. Run: pip install -r requirements.txt")
    try:
        import ctranslate2
        cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        cuda = False
    with wave.open(str(wav)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

    def run_on(device):
        model = WhisperModel(model_name, device=device, compute_type="float16" if device == "cuda" else "int8")
        segs, inf = model.transcribe(pcm, word_timestamps=True, vad_filter=True)
        words = [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in (s.words or [])]
        return words, inf.language
    try:
        try:
            words, lang = run_on("cuda" if cuda else "cpu")
        except RuntimeError as e:  # GPU present but CUDA libraries missing
            print(f"GPU transcription unavailable ({str(e)[:80]}), using CPU")
            words, lang = run_on("cpu")
    except Exception as e:  # model download blocked, no disk space, ...
        print(f"warning: transcription failed ({str(e)[:120]}). Continuing without speech signals and captions.")
        return [], None
    lang = lang if words else None  # language detection on engine noise is meaningless
    save_json(out, words)
    save_json(meta, {"language": lang, "model": model_name})
    return words, lang


def z(a):
    a = np.asarray(a, dtype=float)
    if a.size == 0 or a.std() < 1e-9:
        return np.zeros_like(a)
    return (a - np.median(a)) / (a.std() + 1e-9)


def smooth(a, k):
    k = max(1, int(k))
    return np.convolve(a, np.ones(k) / k, mode="same")


def fit(arr, n):
    arr = np.asarray(arr, dtype=float)
    return arr[:n] if len(arr) >= n else np.pad(arr, (0, n - len(arr)))


def avoid_cuts(s0, e0, peak, cuts, min_len):
    """Shrink [s0, e0] so it does not cross a scene cut, keeping the side with the peak."""
    for c in cuts:
        if s0 + 0.5 < c < e0 - 0.5:
            if c > peak and c - s0 >= min_len:
                e0 = c - 0.1
            elif c <= peak and e0 - c >= min_len:
                s0 = c + 0.1
    return s0, e0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--min", type=float, default=12); ap.add_argument("--max", type=float, default=40)
    ap.add_argument("--max-minutes", type=int, default=90)
    ap.add_argument("--model", default="small", help="whisper model: tiny, base, small, medium, large-v3")
    ap.add_argument("--no-transcript", action="store_true", help="skip speech (no captions, no hype words)")
    ap.add_argument("--channel", help="local file: channel name for the credit")
    ap.add_argument("--source-url", help="local file: link to the original video for the credit")
    a = ap.parse_args()
    d = job_dir(a.src)
    vid, info = fetch(a.src, d, a.max_minutes, a.channel, a.source_url)
    dur = float(ffprobe(vid)["format"]["duration"])
    wav, db = audio_rms(vid, d)
    n = len(db)
    words, lang = ([], None) if a.no_transcript else transcribe(wav, d, a.model)
    mfile = d / "motion.json"
    if mfile.exists():
        mo = load_json(mfile)
    else:
        print("motion analysis...")
        mo = analyse(str(vid))
        save_json(mfile, mo)
    rot, res, shk = (fit(mo[k], n) for k in ("rotation", "residual", "shake"))
    cuts = mo.get("cuts", [])
    # signals
    loud = smooth(np.clip(z(db - smooth(db, 30)), 0, None), 3)
    motion = smooth(np.clip(z(rot), 0, None) + np.clip(z(res), 0, None) + 0.5 * np.clip(z(shk), 0, None), 3)
    hype = np.zeros(n)
    for w in words:
        if HYPE.search(w["w"]) and int(w["s"]) < n:
            hype[int(w["s"])] += 1
    # multi-word phrases ("o matko", "send it") span words: scan the joined text per second too
    by_sec = {}
    for w in words:
        by_sec.setdefault(int(w["s"]), []).append(w["w"])
    for s, ws in by_sec.items():
        if s < n and len(ws) > 1 and HYPE.search(" ".join(ws)) and not hype[s]:
            hype[s] += 1
    hype = smooth(hype, 5)
    heat = np.zeros(n)
    for h in (info.get("heatmap") or []):
        heat[int(h["start_time"]):min(n, int(math.ceil(h["end_time"])))] = h["value"]
    w_heat = 2.0 if heat.any() else 0
    score = 0.6 * loud + 1.2 * motion + 0.8 * z(hype).clip(0) + w_heat * z(heat).clip(0)
    picks, used = [], np.zeros(n, bool)
    for p in np.argsort(-score):
        if len(picks) >= a.top or score[p] <= 0:
            break
        s0 = max(0, p - 0.55 * a.max); e0 = min(dur, s0 + a.max)
        ws = [x for x in words if x["s"] >= s0 and x["e"] <= e0]
        if ws:  # snap to word boundaries so captions do not start mid-word
            s0 = max(0, ws[0]["s"] - 0.3); e0 = min(dur, ws[-1]["e"] + 0.6)
        s0, e0 = avoid_cuts(s0, e0, p, cuts, a.min)
        if e0 - s0 < a.min:
            e0 = min(dur, s0 + a.min)
        e0 = min(e0, s0 + a.max)
        if used[int(s0):int(math.ceil(e0))].any():
            continue
        used[int(s0):int(math.ceil(e0))] = True
        text = " ".join(x["w"] for x in words if s0 <= x["s"] < e0)
        why = []
        if rot[p] > np.median(rot) + 2 * rot.std(): why.append("przechył/obrót kamery")
        if res[p] > np.median(res) + 2 * res.std(): why.append("ruch w kadrze (błoto, woda, auto)")
        if shk[p] > np.median(shk) + 2 * shk.std(): why.append("wstrząsy/skok")
        if loud[p] > 1: why.append("skok głośności")
        if hype[p] > 0: why.append("okrzyki")
        if heat[p] > 0.5: why.append(f"najczęściej odtwarzane {heat[p]:.2f}")
        picks.append({"n": 0, "start": round(s0, 2), "end": round(e0, 2), "peak": int(p), "score": round(float(score[p]), 2),
                      "why": why or ["ogólna energia"], "text": text[:400]})
    picks.sort(key=lambda x: x["start"])
    for i, x in enumerate(picks, 1):
        x["n"] = i
    meta = load_json(d / "info.json")
    signals = ["ruch", "głośność"] + (["transkrypcja"] if words else []) + (["najczęściej odtwarzane"] if w_heat else [])
    save_json(d / "candidates.json", {"source": str(vid), "info": meta, "duration": dur, "language": lang, "candidates": picks,
                                      "signals": {"heatmap": bool(w_heat), "words": len(words), "cuts": len(cuts)}})
    fmt = lambda t: f"{int(t // 60)}:{int(t % 60):02d}"
    md = [f"# Kandydaci: {meta.get('title', '')}", f"źródło: {meta.get('webpage_url', '')}",
          f"kanał: {meta.get('channel') or 'nieznany'} | licencja: {meta.get('license') or 'standardowa YouTube'}",
          f"język mowy: {lang or 'brak mowy/transkrypcji'} | sygnały: {', '.join(signals)} | cięcia montażowe: {len(cuts)}", ""]
    for x in picks:
        md += [f"## {x['n']}. {fmt(x['start'])}-{fmt(x['end'])} ({x['end'] - x['start']:.0f}s) wynik {x['score']}",
               f"dlaczego: {', '.join(x['why'])}", f"> {x['text'] or '(bez mowy)'}", ""]
    (d / "candidates.md").write_text("\n".join(md), encoding="utf-8")
    print(f"job: {d}\n{len(picks)} candidates -> {d / 'candidates.md'}")


if __name__ == "__main__":
    main()
