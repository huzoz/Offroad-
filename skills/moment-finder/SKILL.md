---
name: moment-finder
description: Znajdź najlepsze momenty w długim filmie offroad (link YouTube lub plik). Użyj, gdy użytkownik podaje link albo plik i chce highlightów, "znajdź momenty", kandydatów do cięcia lub materiału do składanki.
---

# Moment finder

Uruchom (w folderze strony):

`python "${CLAUDE_PLUGIN_ROOT}/scripts/moments.py" <url-lub-plik> --top 8`

Plik lokalny pobrany skądś: dodaj `--channel "Nazwa kanału" --source-url "https://..."`, inaczej klip nie będzie miał podpisu źródła.

Sygnały (brakujący jest pomijany, nigdy udawany):

- ruch w obrazie (`motion.py`): obrót/przechył kamery, ruch w kadrze po odjęciu ruchu kamery (błoto, woda, auto), wstrząsy. Cięcia montażowe są wykrywane i nie liczą się jako akcja.
- "najczęściej odtwarzane" z YouTube, gdy film je ma (najmocniejszy sygnał),
- okrzyki PL/EN w transkrypcji ("o matko", "utknął", "send it"),
- skoki głośności (niska waga, bo silnik ryczy cały czas).

Opcje: `--model medium` daje lepszą transkrypcję polskiego (wolniej), `--no-transcript` gdy w filmie jest tylko muzyka. Pierwsze uruchomienie pobiera model Whisper (kilkaset MB).

Potem:

1. Przeczytaj `jobs/<id>/candidates.md` i pokaż każdego kandydata: numer, od-do, długość, dlaczego, linia transkrypcji.
2. Odrzuć: wypadki z poszkodowanymi ludźmi, numery rejestracyjne i twarze przypadkowych osób na pierwszym planie, jazdę po terenach chronionych pokazaną jako wzór.
3. Poleć 3 najlepsze i podaj kąt hooka dla każdego.
4. Dopisz kanał do `sources.md`, jeśli go tam nie ma.
5. Następny krok: `clip-cutter --pick <n>` dla pojedynczego klipu albo zapisz numer do planu `compilation`.
