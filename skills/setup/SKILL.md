---
name: setup
description: Pierwsze uruchomienie Offroad clip desk. Użyj, gdy użytkownik instaluje wtyczkę, mówi "setup", "zacznij", albo gdy brakuje ffmpeg, yt-dlp, faster-whisper lub folderu strony.
---

# Setup

Rób wszystko sam. Pytaj człowieka tylko o to, co jest niżej.

## 1. Narzędzia (bez pytań)

Sprawdź: `ffmpeg -version`, `python -m yt_dlp --version`, `python -c "import faster_whisper, cv2, numpy"`. Instaluj tylko to, czego brakuje:

- ffmpeg. Windows: `winget install --id Gyan.FFmpeg -e --source winget`. macOS: `brew install ffmpeg`. Linux: `sudo apt install -y ffmpeg`
- Deno (silnik JavaScript, którego yt-dlp potrzebuje do YouTube; bez niego część filmów się nie pobierze). Sprawdź `deno --version`. Windows: `winget install --id DenoLand.Deno -e`. macOS: `brew install deno`. Linux: `curl -fsSL https://deno.land/install.sh | sh`
- Pakiety Pythona: `python -m pip install -U -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"`
- Linię pip powtarzaj raz w tygodniu: YouTube często się zmienia, a stary yt-dlp dostaje błąd 403.

Jeśli YouTube odpowiada "Sign in to confirm you're not a bot", ustaw zmienną `YTDLP_BROWSER=chrome` (albo `firefox`, `edge`): yt-dlp użyje ciasteczek z przeglądarki, w której człowiek jest zalogowany na YouTube. Powiedz to w jednej linii, nie proś o hasło.

Jeśli po instalacji trzeba nowego terminala (PATH), powiedz to w jednej linii i sprawdź ponownie. Nigdy nie wydawaj pieniędzy.

Lektor AI (dla `top5`) instaluje się osobno, dopiero gdy będzie potrzebny: `python "${CLAUDE_PLUGIN_ROOT}/scripts/setup_tts.py" --test`.

## 2. Maks. 3 pytania w JEDNEJ wiadomości

1. Nazwa strony i @handle.
2. Platformy (np. YouTube Shorts, TikTok, Instagram Reels, długie filmy na YouTube).
3. Profil (jeden): wywrotki i akcje ratunkowe, błoto i woda, podjazdy i technika jazdy, wyprawy/overlanding, konkretne auta (np. Land Cruiser, Jimny, UAZ).

Nie pytaj o to, co już padło.

## 3. Plan, jedno "tak", potem folder

Pokaż listę plików i poproś o jedno "tak". Potem utwórz w bieżącym katalogu folder o nazwie strony:

- `playbook.md`: skopiuj `${CLAUDE_PLUGIN_ROOT}/skills/playbook/references/playbook.md` i uzupełnij pola w [NAWIASACH]
- `scoreboard.csv` z nagłówkiem: `post_id,data,godzina,platforma,format,jezyk,hook,dlugosc_s,zrodla,wysw_12h,wysw_24h,wysw_72h,polubienia,udostepnienia,komentarze,zapisania,obserwujacy,test,notatki`
- `learning.md` z nagłówkami: Wygrane, Przegrane, Aktualne zasady
- `log.md` (co i kiedy poszło, użyte hooki)
- `sources.md` (kanały, z których klipujesz: nazwa, link, licencja, uwagi)
- `permissions.md` (kanały, które zgodziły się na klipowanie: nazwa kanału, data, gdzie jest zgoda). `check.py` czyta ten plik.
- `blocked.md` (zgłoszenia, Content ID, blokady: co, kiedy, czyje)

## 4. Koniec

3 linie: co zainstalowano, gdzie jest folder, następny krok (`trend-radar`). Przypomnij: nic nie jest publikowane automatycznie, człowiek wrzuca każdy post sam.
