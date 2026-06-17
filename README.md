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

MVP kompletne:

- **Parser KPiR** (`audytor/parser_kpir.py`) — wydruk szeroki XLSX z walidacją
  sum ("Suma miesiąca"); rozjazd = `ParserError`.
- **Adapter JPK_FA** (`audytor/sources/jpk_fa.py`) — znormalizowana lista faktur.
- **Karta klienta** (`audytor/frappe_client.py`) — odczyt z Frappe lub tryb ręczny.
- **Silnik 5 kontroli** (`audytor/rules/`) — `run_audit` (kompletność faktur,
  lista płac, kasy, paliwo, DRA); statusy OK/OSTRZEŻENIE/BŁĄD/POMINIĘTO.
- **UI Streamlit** (`app.py`) i **CLI** (`python -m audytor`) — wspólny silnik.

Odroczone (wymaga dostępu/próbek): test na żywym Frappe, kalibracja
dopasowania faktur i wzorca raportu z kasy. Szczegóły:
`2026-06-11-001-feat-audytor-miesieczny-kpir-plan.md`.

## Uruchomienie środowiska deweloperskiego

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Aplikacja webowa (Streamlit)

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

W aplikacji: wgraj wydruk szeroki KPiR (XLSX), opcjonalnie JPK_FA (XML),
uzupełnij kartę klienta (NIP, pracownicy, termin wypłaty, liczba kas,
dozwolone proporcje paliwa) i kliknij **Uruchom audyt**. Wynik to 5 kontroli
ze statusami (zielony/żółty/czerwony/szary) i przycisk pobrania raportu.

### Wdrożenie na Streamlit Cloud

1. Wypchnij repo na GitHub i połącz ze [Streamlit Cloud](https://share.streamlit.io).
2. Main file path: `app.py`. Streamlit Cloud sam zainstaluje `requirements.txt`.
3. Sekrety (gdy podłączysz Frappe) w **Settings → Secrets** w formacie TOML,
   np. `frappe_url`, `frappe_api_key`, `frappe_api_secret` — odczyt przez
   `st.secrets`. Bez nich aplikacja działa w trybie ręcznego wprowadzania karty.

## Uruchomienie audytu z linii poleceń (CLI)

```powershell
# karta klienta w JSON (gdy brak dostępu do Frappe)
# pola: nip, zatrudnia_pracownikow, termin_wyplaty
# ("do_10_nastepnego" | "do_konca_miesiaca"), liczba_kas, proporcje_paliwa
.\.venv\Scripts\python.exe -m audytor "KPiR - wydruk szeroki.xlsx" `
    --karta-json karta.json [--jpk-fa faktury.xml] [--out raport.md]
```

`--jpk-fa` można podać **wielokrotnie** (np. zbiór sprzedaż i zbiór dokumenty);
faktury są scalane bez duplikatów.

Kod wyjścia: `0` = same OK/POMINIĘTO, `1` = ostrzeżenia, `2` = błędy
(do rozróżnienia wyniku przez watcher/cron).

## Architektura

Silnik (`audytor/`) to czysty pakiet Pythona bez zależności od UI —
docelowo wywoływany zarówno ze Streamlit, jak i headless (CLI / watcher
folderu na serwerze).
