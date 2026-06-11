---
date: 2026-06-11
topic: audytor-miesieczny-kpir
---

# Audytor miesięczny KPiR

## Problem

Po zamknięciu miesiąca klienta na KPiR nie ma systemowej kontroli, czy księgowa "domknęła" miesiąc kompletnie i poprawnie. Braki (niezaksięgowana faktura, brak listy płac, brak raportu z kasy, zła proporcja paliwa, brak DRA) wychodzą późno lub wcale. Narzędzie automatyzuje tę kontrolę: porównuje KPiR z dokumentami źródłowymi i z oczekiwaniami wynikającymi z karty charakterystyki klienta we Frappe CRM.

Projekt ma **dwa produkty**:
1. **Karta charakterystyki klienta** — nowy DocType we Frappe CRM z polami sterującymi kontrolami (projektowany "od kontroli wstecz").
2. **Silnik audytu + UI** — parser KPiR, silnik reguł, raport wyników (MVP: Streamlit).

## Wymagania

### Wejście i parsowanie
- R1. Narzędzie parsuje KPiR z Enova 365 w formacie **XLSX "wydruk szeroki"** (struktura: rekord = 3 wiersze; główny z Lp./datą/NIP/opisem/kwotami w kol. 09–18, wiersz kontrahenta + nr KSeF, wiersz nr dowodu + adres). PDF nie jest parsowany — służy tylko człowiekowi.
- R2. Parser waliduje spójność: suma zaksięgowanych pozycji = "Suma miesiąca" z podsumowania pliku. Rozjazd = błąd krytyczny parsowania (nie raportujemy kontroli z niepewnych danych).
- R3. Silnik porównania faktur działa na **znormalizowanej liście faktur** (numer, data, NIP, kwota) niezależnej od źródła. Adapter nr 1: **JPK_FA XML** z Enovy. Adapter nr 2 (po MVP): eksport z Saldeo.

### Kontrole (wszystkie 5 w MVP)
- R4. **Kompletność faktur**: każda faktura z JPK_FA ma odpowiednik w KPiR; raportowane są faktury brakujące w KPiR (i opcjonalnie wpisy KPiR bez pokrycia w źródle).
- R5. **Lista płac**: jeśli karta klienta mówi "zatrudnia pracowników", w miesiącu musi być wpis listy płac (opisy/dowody typu `LPU/...`, `LPE/...`, kwota w kol. 12). Oczekiwany **okres** listy wynika z pola "termin wypłaty" na karcie klienta (do 10. następnego miesiąca → w M lista za M-1; do końca miesiąca → w M lista za M).
- R6. **Raporty z kas fiskalnych**: jeśli karta mówi, że klient ma N kas, w miesiącu musi być N wpisów raportu okresowego (rozpoznawalna konwencja opisu/nr dowodu), **również raporty zerowe**.
- R7. **Proporcja paliwa/eksploatacji**: opis wpisu zawiera proporcję wprost ("zakup paliwa 20/50/75/100"). Każdy taki wpis musi mieć proporcję zgodną ze zbiorem proporcji przysługujących klientowi wg karty (pojazdy ciężarowe / pełne odliczenie VAT → wyższe proporcje).
- R8. **DRA**: w miesiącu M musi być wpis DRA za okres **M-1** (identyfikacja po dowodzie `DRA/RRRR/MM/...`). Inny okres lub brak = ostrzeżenie/błąd.

### Karta charakterystyki (Frappe DocType) — pola minimum
- R9. Karta zawiera co najmniej: zatrudnia pracowników (tak/nie), termin wypłaty wynagrodzeń (do 10. nast. mies. / do końca mies.), liczba kas fiskalnych (0..n), zbiór przysługujących proporcji odliczenia paliwa, oraz identyfikator klienta (NIP) do dopasowania pliku KPiR.

### Wynik i architektura
- R10. Wynik audytu to czytelny raport per klient/miesiąc: lista kontroli ze statusem (OK / ostrzeżenie / błąd) + szczegóły (np. które faktury brakują, jaki okres DRA znaleziono).
- R11. **Silnik audytu jest oddzielony od UI** i wywoływalny headless (funkcja/CLI przyjmująca pliki + dane karty → zwracająca wynik). MVP udostępnia go przez Streamlit (upload pliku / wybór klienta); docelowo ten sam silnik uruchamia automatyzacja (watcher folderu na serwerze → audyt → powiadomienie do pracownika i managera).

## Kryteria sukcesu

- Na pliku przykładowym (SMAKOSZ, kwiecień 2026) narzędzie poprawnie: wykrywa LPU/LPE za marzec, wykrywa DRA za luty i **flaguje** je jako odchyłkę od reguły M-1, rozpoznaje wszystkie wpisy paliwowe z proporcjami 20 i 75, uzgadnia sumę miesiąca.
- Księgowa po zamknięciu miesiąca dostaje wynik kontroli w < 1 min od wgrania pliku, bez ręcznego przeglądania KPiR.
- Fałszywe alarmy na pilotażowej grupie klientów na poziomie akceptowalnym do wdrożenia masowego (do oceny w pilocie).

## Granice scope'u

- MVP: tryb ręczny, pojedynczy klient (upload w Streamlit). Automatyzacja folder-watcher + powiadomienia = etap 2 (ale architektura silnika gotowa na to od dnia 1).
- MVP: tylko adapter JPK_FA XML; Saldeo później.
- Tylko klienci na KPiR; pełne księgi poza zakresem.
- Narzędzie **nie poprawia** księgowań — tylko raportuje.

## Kluczowe decyzje

- **XLSX "wydruk szeroki" jako jedyny format wejściowy KPiR**: deterministyczne parsowanie, proporcja paliwa i identyfikatory (LPU/LPE/DRA/KSeF) dostępne wprost; PDF wymagałby kruchego parsowania.
- **Silnik oddzielony od UI**: docelowy tryb to automatyzacja serwerowa; Streamlit jest tylko pierwszą skorupą.
- **Karta klienta jako konfiguracja reguł**: spójne z architekturą "Frappe jako hub"; pola projektowane od kontroli wstecz.
- **DRA: reguła M-1**: stała, nie per klient.
- **Termin wypłaty: per klient** (pole na karcie), bo praktyka klientów się różni.
- **Adaptery źródeł faktur**: decyzja Enova vs Saldeo nie blokuje budowy silnika porównania.

## Założenia

- Konwencja opisów Enovy jest stabilna między klientami ("zakup paliwa NN", "LPU/LPE", "DRA/RRRR/MM"). Do potwierdzenia na plikach kilku różnych klientów.
- Klient z pojazdami o różnych proporcjach: kontrola sprawdza przynależność proporcji wpisu do **zbioru** dozwolonych, nie przypisanie wpisu do konkretnego pojazdu (to poza zasięgiem danych z KPiR).

## Otwarte pytania

### Do rozwiązania przed planowaniem
- (brak — wszystkie decyzje produktowe rozstrzygnięte)

### Odroczone do planowania
- [Dotyczy R6][Wymaga researchu] Dokładny wzorzec opisu/nr dowodu raportu z kasy fiskalnej — potrzebny przykład wpisu z KPiR klienta z kasą (oraz klienta z 2 kasami, żeby sprawdzić rozróżnialność kas).
- [Dotyczy R4][Techniczne] Klucz dopasowania faktur (nr dowodu vs nr KSeF vs NIP+kwota+data) i tolerancje (groszowe różnice, korekty, faktury ujemne) — do ustalenia na realnej parze KPiR + JPK_FA.
- [Dotyczy R9][Techniczne] Czy karta to nowy DocType, czy rozszerzenie istniejącego rekordu klienta we Frappe; sposób odczytu (REST API Frappe).
- [Dotyczy R10][Techniczne] Forma raportu w etapie 2 (e-mail z podsumowaniem? PDF? link do Streamlit?) i lista odbiorców (pracownik + manager z karty klienta?).
- [Dotyczy R2][Techniczne] Obsługa wpisów `!INCYDENTALNY`, storn (kwoty ujemne) i RMK/amortyzacji w kontrolach — żeby nie generowały fałszywych alarmów.

## Następne kroki
→ `/dev-plan` do planowania technicznego implementacji
