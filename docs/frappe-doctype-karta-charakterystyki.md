# DocType „Karta Charakterystyki" — specyfikacja do wyklikania we Frappe

Dokument opisuje pola nowego DocType, który będzie źródłem parametrów
sterujących kontrolami audytora KPiR. **Tworzy się go w UI Frappe — bez
pisania kodu.** Dopóki Frappe nie jest podłączone, audytor działa w trybie
ręcznego wprowadzania tych samych parametrów (fallback w UI / plik JSON w CLI).

> Pola nazywane są **generycznie** (nie „pod audytora"), bo karta ma z czasem
> stać się źródłem prawdy także dla innych narzędzi (HR/payroll, fakturowanie).

## Jak utworzyć (skrót)

1. Zaloguj się do Frappe jako administrator.
2. Wyszukaj **„DocType List"** → **New**.
3. Nazwa: `Karta Charakterystyki`. Moduł: dowolny (np. CRM).
4. Dodaj pola wg tabeli poniżej (przycisk **Add Row** w sekcji *Fields*).
5. Zapisz. Następnie **New → Karta Charakterystyki** zakłada rekord klienta.

## Pola

| Etykieta (Label)            | Fieldname (techniczna)  | Typ (Fieldtype) | Wymagane | Uwagi |
|-----------------------------|-------------------------|-----------------|----------|-------|
| NIP                         | `nip`                   | Data            | tak      | Identyfikator klienta; klucz dopasowania do pliku KPiR. Unikalny. |
| Zatrudnia pracowników       | `zatrudnia_pracownikow` | Check           | nie      | 1 = tak. Steruje kontrolą listy płac (R5). |
| Termin wypłaty wynagrodzeń  | `termin_wyplaty`        | Select          | nie      | Opcje (dokładnie te wartości): `do_10_nastepnego`, `do_konca_miesiaca`. |
| Liczba kas fiskalnych       | `liczba_kas`            | Int             | nie      | 0..n. Steruje kontrolą raportów z kas (R6). |
| Proporcje paliwa (dozwolone)| `proporcje_paliwa`      | Small Text      | nie      | Lista dozwolonych proporcji odliczenia VAT, po przecinku, np. `20,75`. Steruje kontrolą paliwa (R7). |

### Wartości pola `termin_wyplaty`

| Wartość (zapisywana)   | Znaczenie                                            |
|------------------------|------------------------------------------------------|
| `do_10_nastepnego`     | Wypłata do 10. dnia następnego miesiąca → w miesiącu M oczekiwana lista płac za **M-1**. |
| `do_konca_miesiaca`    | Wypłata do końca miesiąca → w miesiącu M oczekiwana lista płac za **M**. |

## Sposób odczytu przez audytora

Read-only GET przez REST:

```
GET {base_url}/api/resource/Karta Charakterystyki
    ?filters=[["nip","=","<NIP>"]]
    &fields=["nip","zatrudnia_pracownikow","termin_wyplaty","liczba_kas","proporcje_paliwa"]
Authorization: token <api_key>:<api_secret>
```

- Klucze API (`api_key`, `api_secret`) generuje się w profilu użytkownika
  Frappe (API Access) i podaje audytorowi przez `st.secrets` (Streamlit) lub
  zmienne środowiskowe (CLI).
- Brak rekordu dla NIP → audytor zwraca `None` i przechodzi w tryb ręczny.
- Niedostępność Frappe (timeout / 5xx) → audytor zgłasza `FrappeUnavailable`
  i również oferuje tryb ręczny — kompletność CRM nie blokuje audytu.

## Mapowanie na model `KartaKlienta`

| Pole DocType            | Pole `KartaKlienta`      | Typ w kodzie     |
|-------------------------|--------------------------|------------------|
| `nip`                   | `nip`                    | `str`            |
| `zatrudnia_pracownikow` | `zatrudnia_pracownikow`  | `bool`           |
| `termin_wyplaty`        | `termin_wyplaty`         | `TerminWyplaty`  |
| `liczba_kas`            | `liczba_kas`             | `int`            |
| `proporcje_paliwa`      | `proporcje_paliwa`       | `set[int]`       |
