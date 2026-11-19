---
name: rule-check
description: Sprawdź gotowy klip lub składankę przed publikacją (format, długość, podpis źródła w kadrze i w opisie, prawa do materiału). Użyj przed każdym wrzuceniem albo gdy użytkownik pyta "czy to można wrzucić".
---

# Rule check

Uruchom w folderze strony:

`python "${CLAUDE_PLUGIN_ROOT}/scripts/check.py" <plik.mp4>`

Opcjonalnie `--caption "tekst posta"` (inaczej czyta wygenerowany plik z opisami) i `--strict` (brak zgody/licencji = FAIL).

Sprawdza: rozdzielczość (1080x1920 pion, 1920x1080 poziom), ok. 30 fps, dźwięk, długość (7-60 s dla pionu), nazwę kanału w rogu kadru, źródło w opisie oraz prawa: licencja CC BY albo wpis w `permissions.md` = PASS, w innym razie WARN.

Potem:

1. Pokaż PASS / WARN / FAIL krótką listą.
2. FAIL: napraw przyczynę (przetnij ponownie, dodaj źródło do opisu) i uruchom znowu. Nie dyskutuj z FAIL.
3. WARN o prawach: powiedz w jednej linii, że kanał nie dał zgody i nie ma licencji CC, więc klip może dostać Content ID lub zgłoszenie. Decyzja należy do człowieka.
4. Przeczytaj opis sam: źródło podane, brak zmyślonych faktów, brak sugestii, że to nasze nagranie.
5. Jeśli kanał kiedyś zgłosił nasz klip (`blocked.md`), zatrzymaj się i powiedz to.
6. Dopiero gdy nie ma FAIL, pokaż człowiekowi plik i opis i czekaj na "tak". Człowiek wrzuca sam.
