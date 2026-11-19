---
name: clip-cutter
description: Wytnij wybrany moment jako pionowy klip 1080x1920 po polsku i angielsku, z napisami słowo po słowie, hookiem i nazwą kanału źródłowego w rogu. Użyj po moment-finder albo gdy użytkownik mówi "wytnij", "zrób klip", "zrób pion".
---

# Clip cutter

Najpierw weź 2 hooki z `hook-writer` (osobno PL i EN, nie tłumacz maszynowo). Potem:

`python "${CLAUDE_PLUGIN_ROOT}/scripts/cut.py" jobs/<id> --pick <n> --hook "pl=TEKST" --hook "en=TEXT"`

Opcje:

- `--layout blur` (domyślnie): cały kadr na rozmytym tle. Bezpieczne dla poziomych nagrań offroad.
- `--layout fill --focus 0.5`: kadr przycięty na cały ekran; `--focus` 0 = lewa, 1 = prawa krawędź. Używaj, gdy akcja jest w jednym miejscu kadru.
- `--start S --end E`: własne granice zamiast kandydata.
- `--langs pl` albo `--langs pl,en,de`: języki. Język mowy zostaje oryginalny, pozostałe są tłumaczone maszynowo.
- `--captions none`: bez napisów (np. sama muzyka).

Nazwa kanału jest zawsze w lewym górnym rogu obrazu źródłowego, przez cały klip. `--no-credit` nie używaj przy cudzym materiale.

Po cięciu:

1. Wynik: `jobs/<id>/edits/clip_<n>_pl.mp4`, `clip_<n>_en.mp4` i `clip_<n>_captions.md` (gotowe opisy z linkiem do źródła).
2. Przejrzyj klatkę z 1. i 5. sekundy (ffmpeg `-ss 1 -frames:v 1`): hook czytelny, podpis źródła widoczny, napisy nie zasłaniają akcji.
3. Przeczytaj tłumaczenie napisów EN. Popraw rażące błędy (przetnij ponownie z poprawionym transcript.json albo `--captions none`).
4. Uruchom `rule-check`. Potem pokaż człowiekowi pliki i opisy i czekaj na "tak". Niczego nie wrzucaj.
