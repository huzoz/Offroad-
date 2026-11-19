---
name: trend-radar
description: Ranking świeżych filmów offroad na YouTube według wyświetleń na godzinę. Użyj, gdy użytkownik pyta, co jest na topie, co dziś klipować albo chce nowych źródeł.
---

# Trend radar

Uruchom (w folderze strony):

`python "${CLAUDE_PLUGIN_ROOT}/scripts/trends.py" --hours 72 --limit 25`

Domyślnie szuka po polsku i angielsku (offroad 4x4, off road polska, offroad mud, terenówki błoto, overlanding). Własne zapytania: powtarzane `--query "jimny offroad" --query "land cruiser mud"`. Krótkie filmy (< 4 min) i Shortsy są pomijane: z długich filmów wychodzą lepsze klipy.

Potem:

1. Pokaż top 10 jako krótką tabelę: tytuł, kanał, wyświetlenia, wyśw./h, wiek, czy ma "najczęściej odtwarzane", czy CC, link.
2. Wybierz 3 pasujące do profilu strony. Preferuj kolejno: licencję CC BY, kanały z `permissions.md`, potem resztę.
3. Kanały, które są w `blocked.md` (zgłaszały nas), pomijaj i mów dlaczego.
4. Zaproponuj następny krok: `moment-finder <url>`.

Jeśli skrypt zwróci błąd, pokaż ostatnią linię i napraw przyczynę (stary yt-dlp, sieć). Nie wymyślaj listy.
