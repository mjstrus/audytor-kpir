"""Adapter JPK_FA(4) XML → znormalizowana lista faktur (R3).

Parsowanie namespace-agnostic (po lokalnej nazwie tagu), żeby tolerować
różne wersje schemy. Pola wg schematu FA(4): P_2A (nr faktury), P_1 (data
wystawienia), P_5B (NIP nabywcy = kontrahent z perspektywy wystawcy JPK),
P_15 (kwota brutto).
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import BinaryIO
from xml.etree import ElementTree

from audytor.models import Faktura

POLE_NUMER = "P_2A"
POLE_DATA = "P_1"
POLE_NIP_NABYWCY = "P_5B"
POLE_KWOTA_BRUTTO = "P_15"
TAG_FAKTURA = "Faktura"


class JpkFaError(Exception):
    """Błąd parsowania pliku JPK_FA."""


def wczytaj_jpk_fa(plik: str | Path | BinaryIO) -> list[Faktura]:
    """Wczytuje faktury z pliku JPK_FA(4) XML do listy `Faktura`."""
    try:
        drzewo = ElementTree.parse(plik)
    except ElementTree.ParseError as exc:
        raise JpkFaError(f"Nieprawidłowy XML JPK_FA: {exc}") from exc

    faktury = [_zbuduj_fakture(elem) for elem in _znajdz_wszystkie(drzewo.getroot(), TAG_FAKTURA)]
    if not faktury:
        raise JpkFaError("Plik JPK_FA nie zawiera żadnej faktury")
    return faktury


def _zbuduj_fakture(elem: ElementTree.Element) -> Faktura:
    numer = _pole_obowiazkowe(elem, POLE_NUMER)
    return Faktura(
        numer=numer,
        data=_data(elem, numer),
        nip_kontrahenta=_pole(elem, POLE_NIP_NABYWCY),
        kwota_brutto=_kwota(elem, numer),
    )


def _data(elem: ElementTree.Element, numer: str) -> date:
    surowa = _pole_obowiazkowe(elem, POLE_DATA, numer)
    try:
        return date.fromisoformat(surowa)
    except ValueError as exc:
        raise JpkFaError(f"Nieprawidłowa data '{surowa}' (faktura {numer})") from exc


def _kwota(elem: ElementTree.Element, numer: str) -> Decimal:
    surowa = _pole_obowiazkowe(elem, POLE_KWOTA_BRUTTO, numer)
    try:
        return Decimal(surowa)
    except InvalidOperation as exc:
        raise JpkFaError(f"Nieprawidłowa kwota brutto '{surowa}' (faktura {numer})") from exc


def _pole(elem: ElementTree.Element, nazwa: str) -> str | None:
    dziecko = _znajdz(elem, nazwa)
    if dziecko is None or dziecko.text is None:
        return None
    tekst = dziecko.text.strip()
    return tekst or None


def _pole_obowiazkowe(elem: ElementTree.Element, nazwa: str, numer: str | None = None) -> str:
    wartosc = _pole(elem, nazwa)
    if wartosc is None:
        kontekst = f" (faktura {numer})" if numer else ""
        raise JpkFaError(f"Brak obowiązkowego pola {nazwa}{kontekst}")
    return wartosc


def _lokalna_nazwa(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _znajdz(rodzic: ElementTree.Element, nazwa: str) -> ElementTree.Element | None:
    for dziecko in rodzic:
        if _lokalna_nazwa(dziecko.tag) == nazwa:
            return dziecko
    return None


def _znajdz_wszystkie(rodzic: ElementTree.Element, nazwa: str) -> list[ElementTree.Element]:
    return [d for d in rodzic if _lokalna_nazwa(d.tag) == nazwa]
