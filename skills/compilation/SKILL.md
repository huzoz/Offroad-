---
name: compilation
description: Zbuduj składankę (kompilację) z momentów kilku filmów offroad, z nazwą kanału w rogu każdego fragmentu, własnym tytułem i komentarzami oraz listą źródeł z rozdziałami. Użyj, gdy użytkownik chce "składankę", "kompilację", "top 5", "best of" albo dłuższy film na YouTube.
---

# Składanka

## 1. Temat zamiast przypadkowych klipów

Składanka musi mieć myśl przewodnią, bo to twój wkład: np. "5 błędów na podjeździe", "kiedy wyciągarka ratuje dzień", "Jimny vs ciężkie auta w tym samym błocie". Zaproponuj człowiekowi 2-3 tematy z dostępnych kandydatów i poczekaj na wybór.

## 2. Materiał

Dla każdego źródła uruchom `moment-finder`. Wybierz fragmenty pasujące do tematu, zwykle 5-10. Każdy fragment powinien być krótki (8-25 s): krótsze fragmenty i więcej twojego komentarza to mocniejsza pozycja przy prawie cytatu i mniejsze ryzyko Content ID.

## 3. Plan

Zapisz `plany/<nazwa>.json` w folderze strony:

```json
{
  "name": "bledy-na-podjezdzie",
  "format": "horizontal",
  "layout": "blur",
  "title": {"pl": "5 błędów na podjeździe", "en": "5 hill climb mistakes"},
  "segments": [
    {"job": "jobs/<id>", "pick": 2, "note": {"pl": "Za mało rozpędu", "en": "Not enough momentum"}},
    {"job": "jobs/<id2>", "start": 61.5, "end": 78, "note": {"pl": "Zła linia przejazdu", "en": "Wrong line"}}
  ]
}
```

- `format`: `horizontal` (1920x1080, długi YouTube) albo `vertical` (1080x1920, Shorts/TikTok, max 60 s łącznie).
- `note`: twój komentarz do fragmentu, wyświetlany przez 4 s. Pisz go dla każdego fragmentu: wyjaśnia, co się dzieje i dlaczego. To jest twoja własna treść w składance.
- `title`: hook z `hook-writer`, na początku pierwszego fragmentu.

Pokaż plan człowiekowi (kolejność, czasy, notatki) i poczekaj na "tak".

## 4. Render

`python "${CLAUDE_PLUGIN_ROOT}/scripts/compile.py" plany/<nazwa>.json --langs pl,en`

Wynik w `compilations/`: `<nazwa>_pl.mp4`, `<nazwa>_en.mp4` i `<nazwa>_<lang>_opis.md` z rozdziałami YouTube (każdy fragment = rozdział) i listą źródeł z linkami. Każdy fragment ma nazwę kanału w lewym górnym rogu przez cały czas trwania.

## 5. Sprawdzenie

1. Obejrzyj po jednej klatce z każdego fragmentu: podpis kanału widoczny, notatka czytelna.
2. `rule-check` na obu plikach.
3. Opis z `_opis.md` wklejasz do opisu filmu w całości, razem ze źródłami.
4. Pokaż człowiekowi i czekaj na "tak". Niczego nie wrzucaj.

Prawo cytatu (art. 29 ustawy o prawie autorskim) wymaga, żeby cudze fragmenty służyły twojemu utworowi (np. wyjaśnieniu, analizie, krytyce) i były w zakresie uzasadnionym celem. Sama składanka bez komentarza słabo spełnia ten warunek. Nie oceniaj za człowieka, czy dana składanka jest legalna: przypomnij tylko o tym przy pierwszym planie i trzymaj się zasad z punktów 2 i 3.
