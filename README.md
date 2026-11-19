# Offroad Clip Desk

Wtyczka do Claude Code, która robi klipy i składanki z filmów offroad na YouTube. Znajduje świeże filmy, wykrywa najlepsze momenty po ruchu w obrazie (przechyły, wywrotki, błoto i woda w kadrze), tnie je na pionowe klipy po polsku i angielsku, buduje składanki z własnym komentarzem i sprawdza każdy plik przed publikacją. Nazwa kanału źródłowego jest w rogu każdego klipu, a link do źródła w opisie.

Nic nie jest publikowane automatycznie. Ty zatwierdzasz i wrzucasz każdy post.

```
/plugin marketplace add huzoz/Offroad-
/plugin install offroad@offroad
```

## Pierwsze uruchomienie: wklej to do Claude Code

```
Użyj wtyczki offroad. Zrób setup mojej strony, zadaj pytania w jednej wiadomości,
a po jednym "tak": pokaż trendy offroad z ostatnich 72 h, znajdź momenty w 2 najlepszych
filmach, wytnij 3 klipy PL i EN z hookami i sprawdź je przed publikacją.
```

## Skille

| Skill | Co robi |
|---|---|
| `setup` | Instaluje ffmpeg, yt-dlp, faster-whisper i OpenCV, zakłada folder strony |
| `trend-radar` | Świeże filmy offroad (PL + EN) według wyświetleń na godzinę, z oznaczeniem licencji CC |
| `moment-finder` | Najlepsze momenty 12-40 s: ruch w obrazie, "najczęściej odtwarzane" z YouTube, okrzyki PL/EN, głośność |
| `clip-cutter` | Pionowy klip 1080x1920 w każdym języku: napisy słowo po słowie, hook, źródło w rogu, -14 LUFS |
| `hook-writer` | 3 hooki na klip, osobno po polsku i angielsku |
| `top5` | Odliczanka "Top 5" z lektorem AI generowanym lokalnie na Twoim GPU (Chatterbox Multilingual, EN + PL): numer, krótki żart, akcja; pytanie do widzów na koniec |
| `compilation` | Składanka pozioma (YouTube) lub pionowa z kilku filmów: tytuł, komentarz do każdego fragmentu, źródło w rogu, rozdziały i lista źródeł w opisie |
| `rule-check` | Format, długość, źródło w kadrze i w opisie, licencja CC lub zgoda twórcy |
| `learning-loop` | Tabela wyników, jeden test dziennie, tylko prawdziwe liczby |
| `playbook` | Dzienna rutyna, formaty, pory publikacji |

## Jak wykrywane są momenty

Silnik ryczy przez cały film, więc sama głośność słabo pokazuje akcję. `scripts/motion.py` analizuje obraz (5 klatek/s, 320 px, około minuty na godzinę filmu):

- **obrót kamery**: kamera przykręcona do auta obraca się razem z nim, więc przechyły i wywrotki są widoczne jako szybki obrót kadru,
- **ruch w kadrze po odjęciu ruchu kamery**: lecące błoto, woda, auto zsuwające się przed statyczną kamerą,
- **wstrząsy**: skoki i twarde lądowania,
- **cięcia montażowe**: wykrywane i wyzerowane, żeby zmiana ujęcia nie wyglądała jak akcja; granice klipów omijają cięcia.

`moments.py` łączy to z wykresem "najczęściej odtwarzane" z YouTube (gdy jest), okrzykami w transkrypcji ("o matko", "utknął", "send it") i skokami głośności.

## Lektor AI na Twoim GPU

`top5` używa modelu [Chatterbox Multilingual](https://github.com/resemble-ai/chatterbox) (Resemble AI, licencja MIT, także do użytku komercyjnego). Działa lokalnie, bez opłat i bez wysyłania tekstu do chmury. Potrzebuje karty NVIDIA z ok. 6 GB VRAM (działa też na CPU, ale wolno). Instalacja w osobnym środowisku, żeby nie kłóciła się z resztą narzędzi:

```
python scripts/setup_tts.py --test
```

Skrypt rozpoznaje kartę (także RTX 50xx), instaluje odpowiedni torch z CUDA do `~/.offroad-tts` i nagrywa testowe zdanie po polsku i angielsku. Każde nagranie ma niesłyszalny znak wodny Perth (wymóg modelu).

## Uruchamianie skryptów ręcznie (zero tokenów)

```
pip install -r requirements.txt
python scripts/trends.py --hours 72
python scripts/moments.py "https://www.youtube.com/watch?v=..." --top 8
python scripts/cut.py jobs/<id> --pick 2 --hook "pl=Przejedzie czy zostanie?" --hook "en=Will it make it?"
python scripts/compile.py plany/skladanka.json --langs pl,en
python scripts/frames.py jobs/<id>
python scripts/top5.py plany/top5.json --langs en,pl
python scripts/check.py jobs/<id>/edits/clip_2_pl.mp4
```

Plik lokalny zamiast linku: `python scripts/moments.py film.mp4 --channel "Nazwa kanału" --source-url "https://..."`.

Windows, macOS lub Linux, Python 3.10+. Karta NVIDIA przyspiesza transkrypcję; na samym procesorze 12-minutowy film to kilka minut. Tłumaczenia są maszynowe (Google Translate przez deep-translator): przeczytaj je przed publikacją.

## Prawa autorskie

Podanie źródła jest konieczne, ale samo nie wystarcza. Prawo cytatu (art. 29 ustawy o prawie autorskim) pozwala przytaczać fragmenty cudzych utworów w twoim własnym utworze, w zakresie uzasadnionym celem cytatu (np. wyjaśnienie, analiza, krytyka). Dlatego składanki mają pole na komentarz do każdego fragmentu, a `rule-check` ostrzega, gdy kanał nie ma licencji CC i nie dał zgody. Platformy (Content ID, zgłoszenia) działają według własnych zasad, niezależnie od polskiego prawa. To nie jest porada prawna.

## Licencja

MIT. Część kodu (cięcie, napisy, pomocnicze funkcje yt-dlp) pochodzi z [gtavi-claudecode](https://github.com/Bodila51/gtavi-claudecode) autorstwa Bodila51 (MIT).
