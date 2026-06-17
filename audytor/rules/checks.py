"""5 kontroli domknięcia miesiąca — każda czysta: wejście → `WynikKontroli`.

R4 kompletność faktur, R5 lista płac, R6 raporty z kas, R7 proporcje paliwa,
R8 DRA. Brak danych / kontrola nie dotyczy klienta → POMINIĘTO (nie OK).
"""

import re

from audytor.models import Faktura, KartaKlienta, KsiegaMiesiac, TerminWyplaty, WpisKPiR
from audytor.patterns import (
    AMORTYZACJA_OPIS_RE,
    RMK_DOWOD_RE,
    okres_dra,
    okres_listy_plac,
    proporcja_paliwa,
    raport_kasy,
)
from audytor.rules.engine import Status, WynikKontroli
from audytor.sources.base import normalizuj_numer

# KPiR doklejają do nr dowodu wewnętrzny sufiks rejestru, np. "(ZR/2026/0092)"
# albo "(SPT/2026/0081)" — usuwamy końcową grupę w nawiasach przed porównaniem
# (uwaga: zachowujemy ewentualny prefiks typu "(S)" na początku numeru).
_SUFIKS_REJESTRU_RE = re.compile(r"\s*\([^()]*\)\s*$")

NAZWA_FAKTURY = "Kompletność faktur"
NAZWA_PLAC = "Lista płac"
NAZWA_KAS = "Raporty z kas fiskalnych"
NAZWA_PALIWO = "Proporcje paliwa"
NAZWA_DRA = "DRA (składki ZUS)"


def poprzedni_okres(rok: int, miesiac: int) -> tuple[int, int]:
    """Zwraca (rok, miesiąc) dla M-1."""
    return (rok - 1, 12) if miesiac == 1 else (rok, miesiac - 1)


# --- R7: Proporcje paliwa -------------------------------------------------

def kontrola_paliwa(ksiega: KsiegaMiesiac, karta: KartaKlienta) -> WynikKontroli:
    wpisy_paliwa = [(w, proporcja_paliwa(w.opis)) for w in ksiega.wpisy if proporcja_paliwa(w.opis)]
    if not wpisy_paliwa:
        return WynikKontroli(NAZWA_PALIWO, Status.POMINIETO, ["Brak wpisów paliwowych w miesiącu"])

    niezgodne = [(w, p) for w, p in wpisy_paliwa if p not in karta.proporcje_paliwa]
    if not niezgodne:
        dozwolone = ", ".join(map(str, sorted(karta.proporcje_paliwa)))
        return WynikKontroli(
            NAZWA_PALIWO, Status.OK, [f"Wszystkie {len(wpisy_paliwa)} wpisy w dozwolonych proporcjach ({dozwolone})"]
        )

    dozwolone = ", ".join(map(str, sorted(karta.proporcje_paliwa))) or "(brak)"
    szczegoly = [
        f"Lp. {w.lp} ({w.data:%d.%m.%Y}): proporcja {p}, dozwolone: {dozwolone}" for w, p in niezgodne
    ]
    return WynikKontroli(NAZWA_PALIWO, Status.BLAD, szczegoly, [w for w, _ in niezgodne])


# --- R8: DRA --------------------------------------------------------------

def kontrola_dra(ksiega: KsiegaMiesiac) -> WynikKontroli:
    oczekiwany = poprzedni_okres(ksiega.rok, ksiega.miesiac)
    znalezione = [
        (w, okres_dra(w.nr_dowodu)) for w in ksiega.wpisy if w.nr_dowodu and okres_dra(w.nr_dowodu)
    ]
    if not znalezione:
        return WynikKontroli(NAZWA_DRA, Status.BLAD, [f"Brak wpisu DRA (oczekiwany okres {_okres(oczekiwany)})"])

    if any(okres == oczekiwany for _, okres in znalezione):
        return WynikKontroli(NAZWA_DRA, Status.OK, [f"DRA za {_okres(oczekiwany)} obecna"])

    wpis, okres = znalezione[0]
    return WynikKontroli(
        NAZWA_DRA,
        Status.OSTRZEZENIE,
        [f"DRA za {_okres(okres)}, oczekiwano {_okres(oczekiwany)} (reguła M-1)"],
        [wpis],
    )


# --- R5: Lista płac -------------------------------------------------------

def kontrola_listy_plac(ksiega: KsiegaMiesiac, karta: KartaKlienta) -> WynikKontroli:
    if not karta.zatrudnia_pracownikow:
        return WynikKontroli(NAZWA_PLAC, Status.POMINIETO, ["Klient nie zatrudnia pracowników"])

    oczekiwany = _oczekiwany_okres_plac(ksiega, karta.termin_wyplaty)
    znalezione = [
        (w, okres_listy_plac(w.nr_dowodu)) for w in ksiega.wpisy if w.nr_dowodu and okres_listy_plac(w.nr_dowodu)
    ]
    if not znalezione:
        return WynikKontroli(NAZWA_PLAC, Status.BLAD, [f"Brak listy płac (oczekiwany okres {_okres(oczekiwany)})"])

    if any((rok, mies) == oczekiwany for _, (_typ, rok, mies) in znalezione):
        return WynikKontroli(NAZWA_PLAC, Status.OK, [f"Lista płac za {_okres(oczekiwany)} obecna"])

    _typ, rok, mies = znalezione[0][1]
    return WynikKontroli(
        NAZWA_PLAC,
        Status.OSTRZEZENIE,
        [f"Lista płac za {_okres((rok, mies))}, oczekiwano {_okres(oczekiwany)}"],
        [w for w, _ in znalezione],
    )


def _oczekiwany_okres_plac(ksiega: KsiegaMiesiac, termin: TerminWyplaty) -> tuple[int, int]:
    if termin is TerminWyplaty.DO_10_NASTEPNEGO:
        return poprzedni_okres(ksiega.rok, ksiega.miesiac)
    return (ksiega.rok, ksiega.miesiac)


# --- R6: Raporty z kas fiskalnych ----------------------------------------

def kontrola_kas(ksiega: KsiegaMiesiac, karta: KartaKlienta) -> WynikKontroli:
    if karta.liczba_kas == 0:
        return WynikKontroli(NAZWA_KAS, Status.POMINIETO, ["Klient nie ma kas fiskalnych"])

    oczekiwany = (ksiega.rok, ksiega.miesiac)
    raporty = [(w, dane) for w in ksiega.wpisy if (dane := _raport_kasy_wpis(w))]
    kasy_za_okres = {numer for _, (numer, rok, mies) in raporty if (rok, mies) == oczekiwany}
    oczekiwane_kasy = set(range(1, karta.liczba_kas + 1))
    brakujace = oczekiwane_kasy - kasy_za_okres

    if not brakujace:
        kasy = ", ".join(map(str, sorted(kasy_za_okres))) or "—"
        return WynikKontroli(
            NAZWA_KAS,
            Status.OK,
            [f"Raporty kas ({kasy}) za {_okres(oczekiwany)} obecne"],
            [w for w, _ in raporty],
        )

    szczegoly = [
        f"Brak raportu kasy nr: {', '.join(map(str, sorted(brakujace)))} za {_okres(oczekiwany)}"
    ]
    inne = {(rok, mies) for _, (_numer, rok, mies) in raporty if (rok, mies) != oczekiwany}
    if inne:
        szczegoly.append("Raporty za inny okres: " + ", ".join(sorted(_okres(o) for o in inne)))
    return WynikKontroli(NAZWA_KAS, Status.BLAD, szczegoly, [w for w, _ in raporty])


def _raport_kasy_wpis(wpis: WpisKPiR) -> tuple[int, int, int] | None:
    for tekst in (wpis.opis, wpis.nr_dowodu):
        if tekst and (dane := raport_kasy(tekst)):
            return dane
    return None


# --- R4: Kompletność faktur ----------------------------------------------

def kontrola_kompletnosci_faktur(ksiega: KsiegaMiesiac, faktury: list[Faktura] | None) -> WynikKontroli:
    if faktury is None:
        return WynikKontroli(NAZWA_FAKTURY, Status.POMINIETO, ["Nie wgrano pliku JPK_FA"])

    wpisy = [w for w in ksiega.wpisy if not _wykluczony_z_dopasowania(w)]
    klucze_numerow = _klucze_numerow(wpisy)

    brakujace, prawdopodobne = [], []
    for faktura in faktury:
        if _klucz_numeru(faktura.numer) in klucze_numerow:
            continue
        if _dopasowanie_heurystyczne(faktura, wpisy):
            prawdopodobne.append(faktura)
        else:
            brakujace.append(faktura)

    return _zbuduj_wynik_faktur(len(faktury), brakujace, prawdopodobne)


def _zbuduj_wynik_faktur(razem: int, brakujace: list[Faktura], prawdopodobne: list[Faktura]) -> WynikKontroli:
    if brakujace:
        szczegoly = [f"Brak w KPiR: faktura {f.numer} z {f.data:%d.%m.%Y} ({f.kwota_brutto} zł)" for f in brakujace]
        if prawdopodobne:
            szczegoly.append(f"Dopasowanie tylko heurystyczne dla {len(prawdopodobne)} faktur")
        return WynikKontroli(NAZWA_FAKTURY, Status.BLAD, szczegoly)

    if prawdopodobne:
        szczegoly = [f"Dopasowanie heurystyczne (NIP+data) faktury {f.numer}" for f in prawdopodobne]
        return WynikKontroli(NAZWA_FAKTURY, Status.OSTRZEZENIE, szczegoly)

    return WynikKontroli(NAZWA_FAKTURY, Status.OK, [f"Wszystkie {razem} faktury mają pokrycie w KPiR"])


def _wykluczony_z_dopasowania(wpis: WpisKPiR) -> bool:
    if wpis.incydentalny or AMORTYZACJA_OPIS_RE.match(wpis.opis):
        return True
    return bool(wpis.nr_dowodu and RMK_DOWOD_RE.match(wpis.nr_dowodu))


def _klucze_numerow(wpisy: list[WpisKPiR]) -> set[str]:
    klucze = set()
    for wpis in wpisy:
        for surowy in (wpis.nr_dowodu, wpis.nr_ksef):
            if surowy:
                klucze.add(_klucz_numeru(surowy))
    return klucze


def _klucz_numeru(numer: str) -> str:
    """Klucz dopasowania: numer bez końcowego sufiksu rejestru, znormalizowany."""
    return normalizuj_numer(_SUFIKS_REJESTRU_RE.sub("", numer))


def _dopasowanie_heurystyczne(faktura: Faktura, wpisy: list[WpisKPiR]) -> bool:
    return any(
        faktura.nip_kontrahenta and w.identyfikator == faktura.nip_kontrahenta and w.data == faktura.data
        for w in wpisy
    )


# --- pomocnicze -----------------------------------------------------------

def _okres(okres: tuple[int, int]) -> str:
    return f"{okres[0]}/{okres[1]:02d}"
