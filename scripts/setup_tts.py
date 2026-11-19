"""Create the local AI voice environment (Chatterbox Multilingual on your NVIDIA GPU).

Chatterbox needs its own torch build and pins library versions that clash with the main tools, so it
lives in a separate virtual environment: ~/.offroad-tts (override with OFFROAD_TTS_HOME).

What it does:
1. Reads your GPU with nvidia-smi (name, VRAM).
2. Creates the venv and installs a CUDA build of torch that fits the GPU:
   - RTX 50xx (Blackwell) or Python 3.13+: newest torch from the cu128 index
   - other NVIDIA cards: torch 2.6.0 from the cu124 index (the version Chatterbox is tested with)
   - no NVIDIA card: CPU torch (works, but slow)
3. Installs chatterbox-tts without its web demo (gradio).
4. Optional --test: says one line in Polish and English into ~/.offroad-tts/test_pl.wav / test_en.wav.
   The first run downloads the model (about 3 GB) from Hugging Face.

usage: python setup_tts.py [--test] [--cpu]
"""
import argparse, os, re, shutil, subprocess, sys, venv
from pathlib import Path

HOME = Path(os.environ.get("OFFROAD_TTS_HOME", Path.home() / ".offroad-tts"))
DEPS = ["librosa==0.11.0", "s3tokenizer", "transformers==5.2.0", "diffusers==0.29.0", "resemble-perth>=1.0.0",
        "conformer==0.3.2", "safetensors==0.5.3", "spacy-pkuseg", "pykakasi==2.3.0", "pyloudnorm", "omegaconf",
        "huggingface_hub", "tqdm"]


def tts_python():
    """Path of the venv interpreter (also used by top5.py)."""
    p = HOME / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return p


def gpu():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run([smi, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
    except Exception:
        return None
    if not out:
        return None
    name, mem = [x.strip() for x in out[0].split(",")[:2]]
    return name, int(float(mem))


def pip(py, *args):
    cmd = [str(py), "-m", "pip", "install", "--upgrade", *args]
    print("+", " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit(f"pip failed ({r.returncode}). Fix the error above and run setup_tts.py again.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true"); ap.add_argument("--cpu", action="store_true")
    a = ap.parse_args()
    g = None if a.cpu else gpu()
    if g:
        print(f"GPU: {g[0]}, {g[1]} MB VRAM")
        if g[1] < 6000:
            print("warning: Chatterbox wants about 6 GB VRAM; it may run out of memory on this card")
    else:
        print("no NVIDIA GPU found: installing the CPU build (slow but works)")
    py = tts_python()
    if not py.exists():
        print(f"creating {HOME}")
        venv.EnvBuilder(with_pip=True).create(HOME)
    pip(py, "pip", "wheel", "setuptools")
    new_gpu = bool(g and re.search(r"RTX\s*50\d\d|RTX PRO|Blackwell", g[0], re.I))
    if not g:
        pip(py, "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cpu")
    elif new_gpu or sys.version_info >= (3, 13):
        pip(py, "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu128")
    else:
        pip(py, "torch==2.6.0", "torchaudio==2.6.0", "--index-url", "https://download.pytorch.org/whl/cu124")
    numpy = "numpy>=2.0.0" if sys.version_info >= (3, 13) else "numpy>=1.24,<2.0"
    pip(py, numpy, *DEPS)
    pip(py, "--no-deps", "chatterbox-tts")
    chk = subprocess.run([str(py), "-c", "import torch, chatterbox.mtl_tts; print(torch.__version__, torch.cuda.is_available())"],
                         capture_output=True, text=True)
    if chk.returncode != 0:
        sys.exit("import check failed:\n" + chk.stderr[-1500:])
    ver, cuda = chk.stdout.split()
    print(f"torch {ver}, CUDA available: {cuda}")
    if g and cuda != "True":
        print("warning: GPU present but torch cannot use it. Update the NVIDIA driver, then run setup_tts.py again.")
    if a.test:
        here = Path(__file__).parent
        for lang, text in (("pl", "Numer jeden. Tego kierowcy nikt już nie uratuje."),
                           ("en", "Number one. Nobody could save this driver.")):
            out = HOME / f"test_{lang}.wav"
            subprocess.run([str(py), str(here / "tts.py"), "--text", text, "--lang", lang, "--out", str(out), "--force"], check=True)
            print(f"test voice: {out}")
    print(f"\nTTS ready. Interpreter: {py}")


if __name__ == "__main__":
    main()
