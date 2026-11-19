---
name: top5
description: Zrób odliczankę "Top 5" (np. "Top 5 times offroaders went crazy") z lektorem AI generowanym lokalnie na GPU, po angielsku i polsku. Użyj, gdy użytkownik chce top 5, ranking, odliczankę, film z lektorem albo "number one" ze śmiesznym komentarzem.
---

# Top 5 z lektorem AI

Wzór: "Top five... At number five, [żart], [akcja]... And finally, number one... Which one would you...?" Każda pozycja to ok. 9-11 s: lektor mówi numer i jedno krótkie zdanie, a pod spodem leci rozbieg klipu (oryginalny dźwięk przyciszony, duże "#5", napisy słowo po słowie). Zaraz po głosie wchodzi akcja z pełnym dźwiękiem. Nazwa kanału jest w rogu przez cały czas.

## 0. Lektor (raz)

Jeśli `~/.offroad-tts` nie istnieje, uruchom `python "${CLAUDE_PLUGIN_ROOT}/scripts/setup_tts.py" --test`. Skrypt sam sprawdzi kartę (nvidia-smi), zainstaluje torch z CUDA i Chatterbox Multilingual (MIT, polski i angielski). Pierwsze uruchomienie pobiera ok. 3 GB modelu. Daj człowiekowi do odsłuchania `~/.offroad-tts/test_en.wav` i `test_pl.wav`.

Głos domyślny jest angielski. Polski brzmi z nim poprawnie, ale może mieć lekki akcent. Lepszy polski: próbka 10-20 s polskiego lektora na licencji, która pozwala na takie użycie, przez `--voice-pl probka.wav`. Nie klonuj głosu żadnej realnej osoby bez jej zgody.

## 1. Materiał

1. `trend-radar`, potem `moment-finder` na 3-6 filmach. Potrzeba 5 mocnych momentów z wyraźną akcją.
2. Dla każdego kandydata: `python "${CLAUDE_PLUGIN_ROOT}/scripts/frames.py" jobs/<id>` i obejrzyj `jobs/<id>/sheets/pick_<n>.jpg` (Read). Pisz żart tylko o tym, co naprawdę widać.
3. Ułóż ranking: najlepsza akcja jako #1, druga najlepsza jako #5 (otwarcie musi trzymać widza).

## 2. Scenariusz

Dla każdej pozycji jedno zdanie po angielsku i osobno po polsku. Pisz je od nowa w każdym języku, nie tłumacz.

- 4-10 słów po numerze. Lektor ma ok. 3 s na pozycję.
- Rodzaje: suchy komentarz ("He said it was only ankle deep"), ironia ("Physics called. He didn't answer"), fakt o aucie, jeśli na pewno rozpoznajesz model.
- #1 zaczyna się od "And finally, number one" / "I wreszcie numer jeden".
- Bez wyśmiewania poszkodowanych i bez wulgaryzmów.
- `intro`: jedno zdanie z tytułem. `outro`: pytanie do widzów (komentarze).

## 3. Plan

Zapisz `plany/<nazwa>.json`:

```json
{
  "name": "top5-crazy",
  "format": "vertical",
  "title": {"en": "Top 5 times offroaders went crazy", "pl": "Top 5: offroadowcy, którzy przesadzili"},
  "intro": {"en": "Top five times offroaders went completely crazy.", "pl": "Pięć razy, kiedy offroadowcy kompletnie przesadzili."},
  "outro": {"en": "Which one would you send it with?", "pl": "A Ty, z którym byś pojechał?"},
  "action_seconds": 6,
  "items": [
    {"job": "jobs/<id>", "pick": 3, "voice": {"en": "At number five. He said it was only ankle deep.", "pl": "Numer pięć. Mówił, że tam jest po kostki."}}
  ]
}
```

Pozycje wpisujesz od #5 do #1. Opcjonalnie dla pozycji: `"action": 5` (sekundy akcji po głosie), `"peak": 312.5` (sekunda w źródle, w której dzieje się akcja, gdy szczyt kandydata jest źle ustawiony).

Pokaż człowiekowi ranking i wszystkie zdania i czekaj na "tak".

## 4. Render

`python "${CLAUDE_PLUGIN_ROOT}/scripts/top5.py" plany/<nazwa>.json --langs en,pl`

Głos jest zapisywany w `tts_cache/`, więc poprawki czasu nie generują go ponownie. Opcje: `--exaggeration 0.75` (bardziej dramatycznie), `--speed 1.1` (szybciej), `--duck 0.1` (cichszy oryginał pod głosem).

Wynik: `compilations/<nazwa>_en.mp4`, `_pl.mp4` i `_opis.md` ze źródłami. Ponad 60 s: skróć zdania albo `action_seconds`.

## 5. Sprawdzenie

1. Klatka z każdej pozycji: numer, napisy, nazwa kanału widoczne.
2. Odsłuch: czy lektor poprawnie wymawia nazwy aut i polskie słowa. Źle wymówione słowo zapisz fonetycznie w planie i wyrenderuj ponownie.
3. `rule-check` na obu plikach, potem pokaż człowiekowi. Niczego nie wrzucaj.
