"""Local AI voice-over with Chatterbox Multilingual (Resemble AI, MIT licence), on your GPU.

Runs inside the separate TTS environment made by setup_tts.py (it needs torch and chatterbox-tts,
which are kept away from the main requirements). top5.py calls it for you; you rarely run it by hand.

usage: <tts-python> tts.py --batch lines.json [--voice-pl sample_pl.wav] [--voice-en sample_en.wav]
                           [--exaggeration 0.65] [--cfg-en 0.35] [--cfg-pl 0.0] [--seed 7] [--force]
       <tts-python> tts.py --text "Number one." --lang en --out test.wav

lines.json: [{"text": "Number five...", "lang": "en", "out": "tts_cache/abc.wav"}, ...]

Without a voice sample the model's built-in voice is used. That voice is English, so for Polish the
default cfg is 0 (recommended by Chatterbox for cross-language use, it reduces the English accent).
With a Polish sample (--voice-pl) you can raise --cfg-pl to 0.3-0.5. Every output carries Resemble's
inaudible Perth watermark.
"""
import argparse, json, sys, time, wave
from pathlib import Path


def device_auto(torch):
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def save_wav(path, samples, sr):
    import numpy as np
    a = np.clip(np.asarray(samples, dtype=np.float32).reshape(-1), -1, 1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(int(sr))
        w.writeframes((a * 32767).astype("<i2").tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch"); ap.add_argument("--text"); ap.add_argument("--lang", default="en"); ap.add_argument("--out")
    ap.add_argument("--voice-pl"); ap.add_argument("--voice-en")
    ap.add_argument("--exaggeration", type=float, default=0.65, help="0.5 neutral, 0.7+ more dramatic")
    ap.add_argument("--cfg-en", type=float, default=0.35); ap.add_argument("--cfg-pl", type=float)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--device", default="auto")
    ap.add_argument("--force", action="store_true", help="regenerate files that already exist")
    a = ap.parse_args()
    if a.batch:
        items = json.loads(Path(a.batch).read_text(encoding="utf-8"))
    elif a.text and a.out:
        items = [{"text": a.text, "lang": a.lang, "out": a.out}]
    else:
        sys.exit("give --batch lines.json or --text ... --out file.wav")
    todo = [i for i in items if a.force or not Path(i["out"]).exists()]
    if not todo:
        print(json.dumps({"generated": 0, "cached": len(items)}))
        return
    try:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
    except ImportError as e:
        sys.exit(f"TTS environment missing ({e}). Run: python scripts/setup_tts.py")
    dev = device_auto(torch) if a.device == "auto" else a.device
    if dev == "cpu":
        print("warning: no GPU found, generating on CPU (slow: ~10-30 s per line)", file=sys.stderr)
    t0 = time.time()
    model = ChatterboxMultilingualTTS.from_pretrained(device=dev)
    print(f"model loaded on {dev} in {time.time() - t0:.0f} s", file=sys.stderr)
    voices = {"pl": a.voice_pl, "en": a.voice_en}
    for k, it in enumerate(todo, 1):
        lang = it.get("lang", "en").lower()
        voice = it.get("voice") or voices.get(lang)
        cfg = it.get("cfg")
        if cfg is None:
            cfg = a.cfg_en if lang == "en" else (a.cfg_pl if a.cfg_pl is not None else (0.35 if voice else 0.0))
        torch.manual_seed(a.seed + k)
        t1 = time.time()
        wav = model.generate(it["text"], language_id=lang, audio_prompt_path=voice,
                             exaggeration=float(it.get("exaggeration", a.exaggeration)), cfg_weight=float(cfg),
                             temperature=a.temperature)
        save_wav(it["out"], wav.squeeze(0).cpu().numpy(), model.sr)
        print(f"[{k}/{len(todo)}] {lang} {time.time() - t1:.1f} s -> {it['out']}", file=sys.stderr)
    print(json.dumps({"generated": len(todo), "cached": len(items) - len(todo), "device": dev}))


if __name__ == "__main__":
    main()
