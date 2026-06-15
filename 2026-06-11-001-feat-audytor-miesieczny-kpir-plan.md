---
title: "feat: Audytor miesięczny KPiR (kontrola domknięcia miesiąca)"
type: feat
status: active
date: 2026-06-11
origin: docs/dev-brainstorms/2026-06-11-audytor-kpir-requirements.md
---

# feat: Audytor miesięczny KPiR

## Przegląd

Nowe, samodzielne narzędzie: parser KPiR (XLSX "wydruk szeroki" z Enova 365) + silnik 5 kontroli sterowanych kartą charakterystyki klienta we Frappe CRM + raport wyników w Streamlit (Streamlit Cloud, upload ręczny). Silnik od dnia 1 oddzielony od UI i wywoływalny headless (przyszły folder-watcher na serwerze).

## Ujęcie problemu

Brak systemowej kontroli kompletności domknięcia miesiąca klienta KPiR; braki wychodzą późno. Szczegóły: zob. źródło `docs/dev-brainstorms/2026-06-11-audytor-kpir-requirements.md`.

## Śledzenie wymagań

- R1–R2: parser XLSX z walidacją sum (Unit 1)
- R3–R4: znormalizowana lista faktur + adapter JPK_FA + kontrola kompletności (Unit 2, Unit 4)
- R5–R8: kontrole listy płac, kas, paliwa, DRA (Unit 4)
- R9: karta charakterystyki we Frappe + odczyt przez API (Unit 3)
- R10: raport wyników (Unit 5)
- R11: silnik headless + CLI (Unit 1, Unit 6)

## Granice scope'u

- MVP: pojedynczy klient, upload ręczny w Streamlit Cloud; folder-watcher i powiadomienia = etap 2 (poza tym planem, ale CLI z Unit 6 jest jego przyszłym punktem wejścia).
- Tylko adapter JPK_FA XML; adapter Saldeo poza planem.
- Tylko KPiR; bez ksiąg pełnych. Narzędzie nie modyfikuje księgowań.

## Kontekst i research

### Relevantny kod i wzorce (własne projekty Marcina)

- `symfonia_year_end_auditor` — wzorzec: czysty moduł kontroli (pure functions, wynik per kontrola) + cienki frontend Streamlit. Audytor KPiR powiela ten podział.
- `generator-masowych-pism` — wzorzec: Streamlit Cloud + auth i sekrety przez `st.secrets`.
- `abacusvoice` — wzorzec: rozwój unitami z kompletem testów pytest (107/107), pełna dokumentacja PL.

### Ustalenia z analizy próbki (SMAKOSZ, kwiecień 2026)

- XLSX: rekord = 3 wiersze (główny: Lp./data/NIP-lub-identyfikator/opis/kwoty kol. 09–18; drugi: kontrahent + nr KSeF; trzeci: nr dowodu + adres). Nagłówki kończą się ~wiersz 17; dane od wiersza 18.
- Identyfikatory w opisie/dowodzie: `zakup paliwa 20|50|75`, `LPU`/`LPE` + dowód `LPU/F/RRRR/MM/...`, `DRA` + dowód `DRA/RRRR/MM/NN`, `Amortyzacja`, `RMK/RRRR/MM`, znacznik `!INCYDENTALNY`, korekty z kwotami ujemnymi.
- Plik zawiera "Suma miesiąca" + "Narastająco" → kotwica walidacji parsera (R2).

### Referencje zewnętrzne

- Schemat JPK_FA(4) (MF) — struktura `Faktura` (P_2A nr faktury, P_1 data, NIP nabywcy, P_15 kwota brutto). Weryfikacja na realnym pliku w implementacji.
- Frappe REST API — odczyt DocType przez `/api/resource/<DocType>` z token auth (api key + secret).

## Kluczowe decyzje techniczne

- **Stack: Python + Streamlit + pytest, bez bazy w MVP** — wynik audytu jest efemeryczny (raport na ekranie); Supabase niepotrzebne, dopóki nie chcemy historii audytów (świadomie odroczone).
- **Silnik jako czysty pakiet `audytor/` z funkcją `run_audit(kpir, faktury, karta) -> AuditResult`** — UI i przyszły watcher to tylko adaptery wejścia/wyjścia (R11).
- **Wzorce identyfikacji wpisów w konfigurowalnym module `patterns.py` (regexy + stałe)** — konwencje Enovy mogą się różnić niuansami między klientami; jedna zmiana w jednym miejscu zamiast rozsianych literałów.
- **Karta klienta: nowy DocType "Karta Charakterystyki" we Frappe**, powiązany z istniejącym rekordem klienta (link po NIP); odczyt read-only przez REST. W UI fallback: ręczne wpisanie parametrów karty, gdy Frappe niedostępne / klient nie ma jeszcze karty — MVP nie może być zablokowane przez kompletność CRM.
- **Statusy kontroli: OK / OSTRZEŻENIE / BŁĄD / POMINIĘTO** — POMINIĘTO gdy kontrola nie dotyczy klienta (np. brak kas) albo brak danych źródłowych (np. nie wgrano JPK_FA); jawność zamiast cichego "OK".

## Otwarte pytania

### Rozwiązane podczas planowania

- Gdzie działa MVP: **Streamlit Cloud**, Frappe przez API z internetu, sekrety w `st.secrets`.
- Przechowywanie wyników: **brak w MVP** (raport efemeryczny + eksport).

### Odroczone do implementacji

- Dokładny wzorzec raportu z kasy fiskalnej — wymaga próbki KPiR klienta z kasą (oraz z 2 kasami); do czasu pozyskania kontrola R6 implementowana na konfigurowalnym regexie z placeholderem w `patterns.py`.
- Klucz dopasowania faktur i tolerancje (korekty, groszowe różnice) — do kalibracji na realnej parze KPiR + JPK_FA tego samego klienta i miesiąca (Unit 2/4 zawierają decyzję wstępną, kalibracja na danych).
- Czy DocType "Karta Charakterystyki" rozszerzać o pola pod przyszłe kontrole (amortyzacja, RMK) — poza MVP.

## Implementation Units

- [x] **Unit 1: Szkielet repo, modele i parser KPiR** ✅ 2026-06-11

**Cel:** Repo `audytor-kpir` z czystym pakietem silnika; parser XLSX zwracający listę wpisów KPiR + sumy kontrolne.

**Wymagania:** R1, R2, R11 (separacja silnika)

**Zależności:** Brak. Próbka: `KPiR_-_wydruk_szeroki.xlsx` (SMAKOSZ) jako fixture testowy.

**Pliki:**
- Stwórz: `audytor/models.py` (dataclasses: `WpisKPiR` — lp, data, identyfikator, kontrahent, nr_ksef, nr_dowodu, opis, kwoty per kolumna 09–18, flaga_incydentalny; `KsiegaMiesiac` — wpisy, suma_miesiaca, narastajaco, nip_podatnika, okres)
- Stwórz: `audytor/parser_kpir.py`
- Stwórz: `audytor/patterns.py` (regexy: paliwo z proporcją, LPU/LPE, DRA, raport kasy [placeholder], RMK, amortyzacja, !INCYDENTALNY)
- Stwórz: `tests/test_parser_kpir.py`, `tests/fixtures/kpir_smakosz_2026_04.xlsx`
- Stwórz: `requirements.txt`, `README.md` (PL)

**Podejście:**
- Iteracja po wierszach openpyxl; detekcja początku rekordu po wartości Lp. w kol. A; sklejanie 3 wierszy w jeden `WpisKPiR`.
- NIP podatnika i okres ("Za kwiecień 2026") czytane z nagłówka pliku — potrzebne do dopasowania karty klienta i reguł M-1.
- Walidacja: suma kwot wpisów per kolumna == "Suma miesiąca"; rozjazd → wyjątek `ParserError` (R2).

**Notatka wykonawcza:** Test-first na fixture: najpierw asercje na znanych faktach z próbki (136 wpisów, suma przychodu 172 476,44, wpisy paliwowe z proporcjami 20 i 75), potem parser.

**Wzorce do naśladowania:** podział models/parser jak w narzędziu "Analyzer Oszczędności" (`models.py` + `parser.py`).

**Scenariusze testowe:**
- Parsuje fixture: poprawna liczba wpisów, sumy zgodne z podsumowaniem.
- Wpis paliwowy → wyekstrahowana proporcja 20/75; wpis LPU/LPE → rozpoznany typ i okres z nr dowodu; DRA → okres `2026/02`.
- Wpis `!INCYDENTALNY` oznaczony flagą; kwota ujemna (korekta −42,84) nie psuje sum.
- Plik z celowo zepsutą kwotą → `ParserError` o niezgodności sum.

**Weryfikacja:** pytest zielony; parser zwraca komplet danych potrzebnych wszystkim 5 kontrolom bez ponownego czytania pliku.

**Status wykonania (2026-06-11):** 12/12 testów pytest zielonych na realnej próbce SMAKOSZ. Potwierdzone: 136 wpisów, suma przychodu 172 476,44, proporcje paliwa {20, 75}, LPU/LPE za 2026/03, DRA za 2026/02, korekta −42,84, 2 wpisy `!INCYDENTALNY`, zepsuta kwota → `ParserError`. Mapowanie kolumn kwotowych dynamiczne po etykietach `(09)`–`(18)` z wiersza 17 wydruku (odporne na przesunięcia kolumn). Środowisko: Python 3.12.10 (venv), openpyxl 3.1.5, pytest 8.3.5.

- [x] **Unit 2: Adapter JPK_FA → znormalizowana lista faktur** ✅ 2026-06-15

**Cel:** Wczytanie JPK_FA XML do listy `Faktura(numer, data, nip_kontrahenta, kwota_brutto)` niezależnej od źródła (R3).

**Wymagania:** R3

**Zależności:** Unit 1 (models). Potrzebny realny plik JPK_FA od Marcina jako fixture (do czasu: syntetyczny XML wg schematu FA(4)).

**Pliki:**
- Stwórz: `audytor/sources/jpk_fa.py`, `audytor/sources/base.py` (protokół adaptera — pod przyszłe Saldeo)
- Stwórz: `tests/test_jpk_fa.py`, `tests/fixtures/jpk_fa_sample.xml`

**Podejście:**
- Parsowanie `lxml`/`ElementTree` z tolerancją na wersję schematu (namespace-agnostic wyszukiwanie pól P_2A/P_1/P_15).
- Normalizacja numerów faktur (trim, redukcja wielokrotnych spacji — w próbce KPiR widać numery ze spacjami typu `C401F00018 /202604`).

**Scenariusze testowe:**
- Poprawny XML → lista faktur z polami; brak pola obowiązkowego → czytelny błąd z nr faktury.
- Normalizacja: `"FV 1/26 "` i `"FV 1/26"` dają ten sam klucz.

**Weryfikacja:** adapter zwraca dane wystarczające dla kontroli kompletności bez wiedzy o formacie źródła w silniku.

**Status wykonania (2026-06-15):** 9/9 testów zielonych na realnym pliku JPK_FA(4) (ABACUS, marzec 2026, 3 faktury, **eksport z Saldeo**). Parser namespace-agnostic (`xml.etree.ElementTree` — bez nowej zależności `lxml`), mapowanie pól P_2A/P_1/P_5B/P_15, suma brutto uzgodniona z `FakturaCtrl/WartoscFaktur` (1335,83). `normalizuj_numer` w `sources/base.py` + protokół `ZrodloFaktur` pod przyszłe inne źródła. Błędy → `JpkFaError`.

**Korekta założenia planu:** JPK_FA(4) to standardowy format MF — XML jest identyczny niezależnie od programu eksportującego (Enova/Saldeo). Rozróżnienie "adapter Enova" vs "adapter Saldeo" jest więc dla JPK_FA bezprzedmiotowe: jeden adapter `jpk_fa.py` obsługuje oba. Osobny adapter Saldeo byłby potrzebny dopiero dla **natywnego** eksportu Saldeo (nie-JPK), co pozostaje poza MVP.

**⚠️ Uwaga do kalibracji (Unit 4):** dostarczony plik to JPK_FA **sprzedażowy biura ABACUS** (Podmiot1 = ABACUS, NIP 7162819366), a nie faktury kontrahenta SMAKOSZ. Do kalibracji klucza dopasowania faktur (R4) potrzebny JPK_FA **tego samego klienta i miesiąca co KPiR** (SMAKOSZ, kwiecień 2026). Obecny plik służy wyłącznie jako fixture poprawności adaptera. Źródłem KPiR pozostaje Enova (wydruk szeroki); źródłem faktur — JPK_FA (tu z Saldeo).

- [x] **Unit 3: Karta charakterystyki — DocType we Frappe + klient odczytu** ✅ 2026-06-15

**Cel:** Pola sterujące kontrolami dostępne przez API; w narzędziu obiekt `KartaKlienta`.

**Wymagania:** R9

**Zależności:** Dostęp admin do Frappe (Marcin tworzy DocType wg specyfikacji z tego unitu — przez UI Frappe, bez kodu).

**Pliki:**
- Stwórz: `audytor/frappe_client.py` (GET `/api/resource/Karta Charakterystyki?filters=[["nip","=",...]]`, token z `st.secrets`)
- Stwórz: `audytor/models.py` → dataclass `KartaKlienta` (nip, zatrudnia_pracownikow: bool, termin_wyplaty: enum["do_10_nastepnego","do_konca_miesiaca"], liczba_kas: int, proporcje_paliwa: set[int])
- Stwórz: `docs/frappe-doctype-karta-charakterystyki.md` (specyfikacja pól DocType do wyklikania we Frappe: nazwy pól, typy, wartości)
- Stwórz: `tests/test_frappe_client.py` (mock HTTP)

**Podejście:**
- Klient read-only; brak karty dla NIP → zwraca `None`, UI przechodzi w tryb ręcznego wprowadzenia parametrów (decyzja: MVP niezablokowane przez CRM).
- Timeout i błędy sieci → komunikat w UI + tryb ręczny (Streamlit Cloud → self-hosted Frappe bywa kapryśne).

**Scenariusze testowe:**
- Karta istnieje → poprawne mapowanie pól; karta nie istnieje → `None`; HTTP 500/timeout → wyjątek domenowy `FrappeUnavailable`.

**Weryfikacja:** `KartaKlienta` dostarcza komplet parametrów dla kontroli R5–R7 dla NIP-u z pliku KPiR.

**Status wykonania (2026-06-15):** 6/6 testów zielonych (mock HTTP, bez żywego Frappe — dostępu na razie brak). `KartaKlienta` + enum `TerminWyplaty` w `models.py`; `frappe_client.pobierz_karte` (read-only GET, token auth) z mapowaniem pól i tolerancją formatu proporcji (CSV/lista). Brak karty → `None`; HTTP 5xx/timeout → `FrappeUnavailable`; zepsuty rekord → `FrappeError`. Spec DocType: `docs/frappe-doctype-karta-charakterystyki.md`. Nowa zależność: `requests==2.32.3` (i tak wymagana przez Streamlit w Unit 5).

**Odroczone (wymaga dostępu do Frappe):** test na żywym `/api/resource/Karta Charakterystyki` + faktyczne utworzenie DocType wg specyfikacji. Nie blokuje Units 4–6 (karta z trybu ręcznego / JSON).

- [ ] **Unit 4: Silnik reguł — 5 kontroli**

**Cel:** `run_audit(ksiega, faktury|None, karta) -> AuditResult` z wynikami per kontrola (R4–R8, R10-dane).

**Wymagania:** R4, R5, R6, R7, R8, R11

**Zależności:** Unit 1; Unit 2 (dla kontroli kompletności); Unit 3 (KartaKlienta — może być z trybu ręcznego).

**Pliki:**
- Stwórz: `audytor/rules/engine.py` (`AuditResult`, `WynikKontroli(status, szczegoly: list[str], pozycje: list)`)
- Stwórz: `audytor/rules/checks.py` (5 funkcji-kontroli, każda pure: wejście → `WynikKontroli`)
- Stwórz: `tests/test_checks.py`

**Podejście:**
- **Kompletność faktur (R4):** dopasowanie wielostopniowe: (1) nr KSeF jeśli obecny po obu stronach, (2) znormalizowany nr dowodu, (3) heurystyka NIP+kwota+data jako "prawdopodobne dopasowanie" (status OSTRZEŻENIE, nie OK). Faktura z JPK_FA bez dopasowania → BŁĄD z listą braków. Brak pliku JPK_FA → POMINIĘTO.
- **Lista płac (R5):** oczekiwany okres = M-1 lub M wg `termin_wyplaty` z karty; szukanie wpisów LPU/LPE i porównanie okresu z nr dowodu; pracownicy=tak i brak wpisu → BŁĄD; okres inny niż oczekiwany → OSTRZEŻENIE.
- **Kasy fiskalne (R6):** zliczenie wpisów pasujących do wzorca raportu kasowego; liczba < liczba_kas → BŁĄD; wzorzec w `patterns.py` (placeholder do kalibracji — odroczone).
- **Paliwo (R7):** każdy wpis paliwowy z proporcją ∉ `proporcje_paliwa` karty → BŁĄD z listą pozycji (lp., data, kontrahent, proporcja znaleziona vs dozwolone).
- **DRA (R8):** wpis DRA obecny i okres == M-1 → OK; obecny, inny okres → OSTRZEŻENIE (jak w próbce: DRA za luty w kwietniu); brak → BŁĄD.
- Wpisy `!INCYDENTALNY`, RMK, amortyzacja: wyłączone z dopasowania fakturowego (nie generują fałszywych braków), uwzględniane w sumach.

**Notatka wykonawcza:** Test-first; fixture SMAKOSZ jako test integracyjny end-to-end silnika z oczekiwanym wynikiem: paliwo OK (przy karcie {20,75}), DRA = OSTRZEŻENIE, lista płac = OK przy terminie "do 10. następnego".

**Scenariusze testowe:**
- Klient bez pracowników → kontrola płac POMINIĘTO; z pracownikami i bez LPU/LPE → BŁĄD.
- 2 kasy, 1 raport → BŁĄD z informacją "znaleziono 1 z 2".
- Paliwo 75 przy dozwolonym tylko {20} → BŁĄD wskazujący konkretne wpisy.
- JPK_FA z fakturą nieobecną w KPiR → BŁĄD z numerem faktury; dopasowanie heurystyczne → OSTRZEŻENIE.
- DRA za M-2 → OSTRZEŻENIE; brak DRA → BŁĄD.

**Weryfikacja:** `run_audit` działa bez importów Streamlit/HTTP (czysty silnik, R11); wszystkie scenariusze zielone.

- [ ] **Unit 5: UI Streamlit**

**Cel:** Aplikacja na Streamlit Cloud: upload KPiR (+opcjonalnie JPK_FA), pobranie/ręczne podanie karty, czytelny raport (R10).

**Wymagania:** R10; kryterium "wynik < 1 min od wgrania"

**Zależności:** Units 1–4.

**Pliki:**
- Stwórz: `app.py`
- Stwórz: `tests/test_app_smoke.py` (smoke: import + funkcje pomocnicze)
- Modyfikuj: `README.md` (instrukcja wdrożenia na Streamlit Cloud + sekrety)

**Podejście:**
- Flow: upload XLSX → parser czyta NIP/okres → próba pobrania karty z Frappe → (fallback: formularz parametrów) → opcjonalny upload JPK_FA → `run_audit` → raport.
- Raport: nagłówek klient/okres, 5 kontroli ze statusami (kolor: zielony/żółty/czerwony/szary) i rozwijanymi szczegółami pozycji; przycisk eksportu wyniku do pliku (markdown/CSV braków) — przyszły załącznik powiadomienia z etapu 2.
- Auth jak w `generator-masowych-pism` (st.secrets).

**Scenariusze testowe:**
- Happy path na fixture SMAKOSZ (ręczna karta) → raport z 5 kontrolami, DRA żółte.
- Zły plik (PDF zamiast XLSX, plik bez nagłówka KPiR) → czytelny komunikat, bez traceback.

**Weryfikacja:** działa na Streamlit Cloud na realnym pliku; księgowa rozumie raport bez instrukcji.

- [ ] **Unit 6: Wejście headless (CLI)**

**Cel:** `python -m audytor <kpir.xlsx> [--jpk-fa plik.xml] [--karta-json plik.json] --out raport.md` — punkt wejścia przyszłego folder-watchera (R11).

**Wymagania:** R11

**Zależności:** Unit 4.

**Pliki:**
- Stwórz: `audytor/__main__.py`
- Stwórz: `tests/test_cli.py`

**Podejście:**
- Cienki wrapper na `run_audit`; exit code 0 = same OK/POMINIĘTO, 1 = ostrzeżenia, 2 = błędy (watcher/cron łatwo rozróżni).
- Karta z JSON lub z Frappe (te same zmienne środowiskowe co st.secrets).

**Scenariusze testowe:** uruchomienie na fixture → raport.md powstaje, exit code 1 (bo DRA-ostrzeżenie).

**Weryfikacja:** pełny audyt bez Streamlit, jedną komendą.

## Wpływ systemowy

- **Frappe:** nowy DocType "Karta Charakterystyki" stanie się źródłem prawdy także dla przyszłych narzędzi (HR/payroll, fakturowanie) — pola nazywać generycznie, nie "pod audytor".
- **Propagacja błędów:** parser i adapter rzucają wyjątki domenowe; silnik nigdy nie zgaduje — brak danych = POMINIĘTO, nie OK.
- **Parytet interfejsów:** UI i CLI muszą wołać dokładnie tę samą funkcję `run_audit` — żadnej logiki kontrolnej w `app.py`.

## Ryzyka i zależności

- **Stabilność konwencji Enovy między klientami** (opisy, format dowodów) — mitygacja: `patterns.py` + szybki test na plikach 3–5 różnych klientów zaraz po Unit 1.
- **Brak próbki raportu kasowego i pliku JPK_FA** — blokuje kalibrację R4/R6; reszta unitów niezależna. Marcin dostarcza próbki równolegle z Units 1–3.
- **Dostępność self-hosted Frappe z Streamlit Cloud** (firewall/HTTPS) — mitygacja: tryb ręczny karty w UI; test dostępu wcześnie.
- **Fałszywe alarmy dopasowania faktur** (korekty, zaliczki, paragony z NIP) — kalibracja na realnych parach plików przed wdrożeniem masowym (kryterium sukcesu ze źródła).

## Dokumentacja / Notatki operacyjne

- `README.md` po polsku: instrukcja dla księgowej (skąd wziąć wydruk szeroki w Enovie, jak czytać raport) + instrukcja wdrożenia.
- `docs/frappe-doctype-karta-charakterystyki.md`: krok po kroku dodanie DocType przez UI Frappe (bez terminala).

## Źródła i referencje

- **Dokument źródłowy:** docs/dev-brainstorms/2026-06-11-audytor-kpir-requirements.md
- Próbka danych: KPiR "SMAKOSZ" kwiecień 2026 (XLSX wydruk szeroki, Enova 365 2512.9.10)
- Wzorce własne: `symfonia_year_end_auditor`, `generator-masowych-pism`, `mjstrus/abacusvoice`
