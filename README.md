# Audytor miesięczny KPiR

Narzędzie kontroli domknięcia miesiąca klienta na KPiR. Porównuje księgę
(wydruk z Enova 365) z dokumentami źródłowymi i parametrami z karty
charakterystyki klienta, a następnie raportuje braki: niezaksięgowane faktury,
brak listy płac, brak raportów z kas, złe proporcje paliwa, brak DRA.

Narzędzie **nie modyfikuje** księgowań — tylko raportuje.

## Skąd wziąć plik wejściowy (instrukcja dla księgowej)

1. W Enova 365 otwórz KPiR klienta za zamykany miesiąc.
2. Wybierz wydruk **"KPiR — wydruk szeroki"** i zapisz jako **XLSX** (nie PDF).
3. Plik wgraj do audytora — wynik kontroli pojawia się w mniej niż minutę.

## Stan projektu

Zrealizowane:

- **Parser KPiR** (`audytor/parser_kpir.py`) — czyta wydruk szeroki XLSX
  (nagłówek: podatnik/NIP/okres; rekordy 3-wierszowe; kwoty kolumn 09–18)
  i waliduje spójność: suma wpisów musi równać się "Sumie miesiąca"
  z podsumowania wydruku. Rozjazd = błąd krytyczny (`ParserError`).
- **Wzorce identyfikacji** (`audytor/patterns.py`) — proporcja paliwa,
  LPU/LPE, DRA, RMK, amortyzacja, `!INCYDENTALNY`.

W planie (kolejne etapy): adapter JPK_FA, karta klienta z Frappe,
silnik 5 kontroli, UI Streamlit, CLI. Szczegóły:
`2026-06-11-001-feat-audytor-miesieczny-kpir-plan.md`.

## Uruchomienie środowiska deweloperskiego

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Architektura

Silnik (`audytor/`) to czysty pakiet Pythona bez zależności od UI —
docelowo wywoływany zarówno ze Streamlit, jak i headless (CLI / watcher
folderu na serwerze).
