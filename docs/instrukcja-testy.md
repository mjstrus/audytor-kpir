# Audytor KPiR — instrukcja testowania dla pracowników

Krótki przewodnik, jak przetestować audytora na własnym kliencie. Cel testu:
sprawdzić, czy narzędzie poprawnie wykrywa braki domknięcia miesiąca i czy nie
generuje fałszywych alarmów.

## Co przygotować

1. **Wydruk szeroki KPiR** klienta za zamykany miesiąc:
   - W Enova 365 otwórz KPiR klienta → wybierz wydruk **„KPiR — wydruk szeroki"**.
   - Zapisz jako **XLSX** (nie PDF!).
2. *(opcjonalnie)* **JPK_FA** klienta za **ten sam miesiąc** — żeby przetestować
   kontrolę kompletności faktur. Plik XML z Enovy lub Saldeo.
3. **Parametry klienta** (z wiedzy o kliencie albo z jego karty):
   - czy zatrudnia pracowników (tak/nie),
   - termin wypłaty wynagrodzeń (do 10. następnego miesiąca / do końca miesiąca),
   - liczba kas fiskalnych,
   - dozwolone proporcje odliczenia paliwa (np. 20, 75).

## Jak uruchomić audyt (aplikacja webowa)

1. Otwórz adres aplikacji (Streamlit Cloud — link od administratora).
2. **Wgraj plik KPiR** (XLSX). Jeśli masz — wgraj też **JPK_FA** (XML).
3. Uzupełnij **kartę klienta** (4 parametry powyżej).
4. Kliknij **Uruchom audyt**.
5. Odczytaj wynik — 5 kontroli ze statusem:

   | Status | Znaczenie |
   |--------|-----------|
   | ✅ OK | Kontrola przeszła. |
   | 🟡 OSTRZEŻENIE | Coś odbiega od reguły — sprawdź ręcznie (np. DRA za inny miesiąc). |
   | ❌ BŁĄD | Brak czegoś wymaganego (np. brak listy płac mimo pracowników). |
   | ⚪ POMINIĘTO | Kontrola nie dotyczy klienta lub brak danych (np. nie wgrano JPK_FA). |

6. Możesz pobrać raport (przycisk **Pobierz raport**).

## Co sprawdzić w teście (na co zwrócić uwagę)

- Czy **suma** się zgadza — jeśli plik jest niespójny, narzędzie odmówi audytu
  z komunikatem (to celowe: lepiej żaden wynik niż błędny).
- Czy **proporcje paliwa** zostały poprawnie rozpoznane i czy alarm pojawia się
  tylko przy proporcji spoza dozwolonych.
- Czy **lista płac** i **DRA** są oceniane wg właściwego miesiąca
  (lista wg terminu wypłaty; DRA zawsze za miesiąc poprzedni).
- **Fałszywe alarmy** — jeśli narzędzie zgłasza coś, co jest w rzeczywistości
  poprawne, zanotuj: NIP klienta, miesiąc, której kontroli dotyczy i czego
  oczekiwałeś. To kluczowa informacja do kalibracji.

## Zgłaszanie uwag

Dla każdego nieprawidłowego wyniku podaj: **klient (NIP), miesiąc, kontrola,
co pokazało narzędzie, co powinno być**. Najlepiej z plikiem KPiR (i JPK_FA),
na którym wystąpił problem.

---

> ⚠️ **Uwaga o danych:** pliki KPiR i JPK_FA zawierają dane osobowe klientów.
> Nie wrzucaj ich do publicznych repozytoriów ani na czaty. Przekazuj kanałem
> uzgodnionym z administratorem.
