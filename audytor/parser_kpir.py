"""Parser KPiR z Enova 365 — format XLSX "wydruk szeroki".

Struktura pliku: nagłówek (nazwa, NIP, okres) + rekordy po 3 wiersze
(główny: Lp./data/identyfikator/opis/kwoty; drugi: nr KSeF + kontrahent;
trzeci: nr dowodu + adres) + blok podsumowania ("Suma miesiąca",
"Razem od początku roku"). Kolumny kwotowe mapowane dynamicznie po
etykietach (09)-(18) z wiersza nagłówka.
"""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO

import openpyxl

from audytor.models import KOLUMNY_KWOT, WpisKPiR, KsiegaMiesiac
from audytor.patterns import INCYDENTALNY_MARKER

KOL_LP = 0  # indeksy kolumn XLSX (0-based)
KOL_DATA_KSEF_DOWOD = 2
KOL_IDENT_KONTRAHENT = 3
KOL_OPIS = 4

DATA_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")
ETYKIETA_KOLUMNY_RE = re.compile(r"^\((\d{2})\)$")
OKRES_RE = re.compile(r"Za\s+(\S+)\s+(\d{4})")
SUMA_MIESIACA_LABEL = "Suma miesiąca:"
NARASTAJACO_LABEL = "Razem od początku roku:"

MIESIACE = {
    "styczeń": 1, "luty": 2, "marzec": 3, "kwiecień": 4,
    "maj": 5, "czerwiec": 6, "lipiec": 7, "sierpień": 8,
    "wrzesień": 9, "październik": 10, "listopad": 11, "grudzień": 12,
}


class ParserError(Exception):
    """Błąd krytyczny parsowania — dane niepewne, kontrole nie są raportowane."""


def parse_kpir(plik: str | Path | BinaryIO) -> KsiegaMiesiac:
    """Parsuje wydruk szeroki KPiR i waliduje sumy kontrolne (R1, R2)."""
    workbook = openpyxl.load_workbook(plik, read_only=True, data_only=True)
    rows = [list(row) for row in workbook.active.iter_rows(values_only=True)]
    workbook.close()

    naglowek = _czytaj_naglowek(rows)
    mapa_kolumn = _mapuj_kolumny_kwot(rows)
    wpisy = _czytaj_wpisy(rows, mapa_kolumn)
    suma_miesiaca = _czytaj_wiersz_sum(rows, SUMA_MIESIACA_LABEL, mapa_kolumn)
    narastajaco = _czytaj_wiersz_sum(rows, NARASTAJACO_LABEL, mapa_kolumn)

    _waliduj_sumy(wpisy, suma_miesiaca)

    return KsiegaMiesiac(
        nazwa_podatnika=naglowek[0],
        nip_podatnika=naglowek[1],
        rok=naglowek[2],
        miesiac=naglowek[3],
        wpisy=wpisy,
        suma_miesiaca=suma_miesiaca,
        narastajaco=narastajaco,
    )


def _czytaj_naglowek(rows: list[list]) -> tuple[str, str, int, int]:
    nazwa = _tekst(rows[0][KOL_LP]) if rows and rows[0] else None
    if not nazwa:
        raise ParserError("Brak nazwy podatnika w nagłówku — to nie jest wydruk szeroki KPiR")

    nip = None
    rok, miesiac = None, None
    for row in rows[:20]:
        for cell in row:
            tekst = _tekst(cell)
            if not tekst:
                continue
            if nip is None and tekst.startswith("NIP:"):
                nip = tekst.removeprefix("NIP:").strip()
            if rok is None:
                match = OKRES_RE.search(tekst)
                if match and match.group(1).lower() in MIESIACE:
                    miesiac = MIESIACE[match.group(1).lower()]
                    rok = int(match.group(2))
    if nip is None:
        raise ParserError("Nie znaleziono NIP podatnika w nagłówku")
    if rok is None:
        raise ParserError("Nie znaleziono okresu ('Za <miesiąc> <rok>') w nagłówku")
    return nazwa, nip, rok, miesiac


def _mapuj_kolumny_kwot(rows: list[list]) -> dict[int, int]:
    """Buduje mapę: numer kolumny KPiR (9-18) -> indeks kolumny XLSX.

    Szuka pierwszego wiersza nagłówka z etykietami (09)...(18).
    """
    for row in rows[:20]:
        mapa = {}
        for idx, cell in enumerate(row):
            match = ETYKIETA_KOLUMNY_RE.match(_tekst(cell) or "")
            if match:
                numer = int(match.group(1))
                if numer in KOLUMNY_KWOT:
                    mapa[numer] = idx
        if len(mapa) == len(KOLUMNY_KWOT):
            return mapa
    raise ParserError("Nie znaleziono nagłówka z etykietami kolumn (09)-(18)")


def _czytaj_wpisy(rows: list[list], mapa_kolumn: dict[int, int]) -> list[WpisKPiR]:
    wpisy = []
    i = 0
    while i < len(rows):
        if not _czy_poczatek_rekordu(rows[i]):
            i += 1
            continue
        wiersz_2 = rows[i + 1] if i + 1 < len(rows) and not _czy_poczatek_rekordu(rows[i + 1]) else []
        wiersz_3 = rows[i + 2] if wiersz_2 and i + 2 < len(rows) and not _czy_poczatek_rekordu(rows[i + 2]) else []
        wpisy.append(_zbuduj_wpis(rows[i], wiersz_2, wiersz_3, mapa_kolumn))
        i += 1 + (1 if wiersz_2 else 0) + (1 if wiersz_3 else 0)
    if not wpisy:
        raise ParserError("Nie znaleziono żadnych wpisów księgi")
    return wpisy


def _czy_poczatek_rekordu(row: list) -> bool:
    lp = _tekst(row[KOL_LP]) if len(row) > KOL_LP else None
    data = _tekst(row[KOL_DATA_KSEF_DOWOD]) if len(row) > KOL_DATA_KSEF_DOWOD else None
    return bool(lp and lp.isdigit() and data and DATA_RE.match(data))


def _zbuduj_wpis(glowny: list, wiersz_2: list, wiersz_3: list, mapa_kolumn: dict[int, int]) -> WpisKPiR:
    lp = int(_tekst(glowny[KOL_LP]))
    data_wpisu = datetime.strptime(_tekst(glowny[KOL_DATA_KSEF_DOWOD]), "%d.%m.%Y").date()

    kwoty = {}
    for numer, idx in mapa_kolumn.items():
        surowa = glowny[idx] if idx < len(glowny) else None
        kwota = _kwota(surowa, lp)
        if kwota is not None:
            kwoty[numer] = kwota

    kontrahent = _komorka(wiersz_2, KOL_IDENT_KONTRAHENT)
    incydentalny = INCYDENTALNY_MARKER in (kontrahent or "")
    if incydentalny:
        kontrahent = None

    return WpisKPiR(
        lp=lp,
        data=data_wpisu,
        identyfikator=_komorka(glowny, KOL_IDENT_KONTRAHENT),
        opis=_komorka(glowny, KOL_OPIS) or "",
        kontrahent=kontrahent,
        nr_ksef=_komorka(wiersz_2, KOL_DATA_KSEF_DOWOD),
        nr_dowodu=_komorka(wiersz_3, KOL_DATA_KSEF_DOWOD),
        kwoty=kwoty,
        incydentalny=incydentalny,
    )


def _czytaj_wiersz_sum(rows: list[list], etykieta: str, mapa_kolumn: dict[int, int]) -> dict[int, Decimal]:
    for row in rows:
        if _komorka(row, KOL_LP) == etykieta:
            sumy = {}
            for numer, idx in mapa_kolumn.items():
                kwota = _kwota(row[idx] if idx < len(row) else None, etykieta)
                sumy[numer] = kwota if kwota is not None else Decimal("0")
            return sumy
    raise ParserError(f"Nie znaleziono wiersza podsumowania '{etykieta}'")


def _waliduj_sumy(wpisy: list[WpisKPiR], suma_miesiaca: dict[int, Decimal]) -> None:
    """R2: suma zaksięgowanych pozycji musi równać się 'Sumie miesiąca' z wydruku."""
    rozjazdy = []
    for numer, oczekiwana in suma_miesiaca.items():
        policzona = sum((w.kwota(numer) for w in wpisy), Decimal("0"))
        if policzona != oczekiwana:
            rozjazdy.append(f"kolumna ({numer:02d}): wpisy {policzona} vs suma miesiąca {oczekiwana}")
    if rozjazdy:
        raise ParserError("Niezgodność sum kontrolnych: " + "; ".join(rozjazdy))


def _tekst(cell) -> str | None:
    if cell is None:
        return None
    tekst = str(cell).strip()
    return tekst or None


def _komorka(row: list, idx: int) -> str | None:
    return _tekst(row[idx]) if idx < len(row) else None


def _kwota(cell, kontekst) -> Decimal | None:
    if cell is None:
        return None
    if isinstance(cell, (int, float)):
        return Decimal(str(cell))
    tekst = str(cell).replace("\xa0", "").replace(" ", "").replace("PLN", "").replace(",", ".")
    if not tekst:
        return None
    try:
        return Decimal(tekst)
    except InvalidOperation as exc:
        raise ParserError(f"Nieprawidłowa kwota {cell!r} (wpis/wiersz: {kontekst})") from exc
