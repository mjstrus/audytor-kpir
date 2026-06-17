"""Protokół adaptera źródła faktur — wspólny kontrakt dla wszystkich źródeł."""

from pathlib import Path
from typing import BinaryIO, Iterable, Protocol

from audytor.models import Faktura


class ZrodloFaktur(Protocol):
    """Każdy adapter (JPK_FA, Saldeo, ...) zwraca znormalizowaną listę faktur."""

    def wczytaj(self, plik: str | Path | BinaryIO) -> list[Faktura]:
        ...


def scal_faktury(listy: Iterable[list[Faktura]]) -> list[Faktura]:
    """Scala faktury z wielu plików (np. zbiory 'sprzedaż' i 'dokumenty') bez duplikatów.

    Ta sama faktura może być w obu zbiorach — deduplikacja po (numer, NIP
    kontrahenta, kwota brutto). Kolejność pierwszego wystąpienia zachowana.
    """
    widziane: set[tuple] = set()
    wynik: list[Faktura] = []
    for lista in listy:
        for faktura in lista:
            klucz = (normalizuj_numer(faktura.numer), faktura.nip_kontrahenta, faktura.kwota_brutto)
            if klucz not in widziane:
                widziane.add(klucz)
                wynik.append(faktura)
    return wynik


def normalizuj_numer(numer: str) -> str:
    """Klucz porównania numeru faktury: trim + redukcja wielokrotnych spacji.

    W KPiR numery bywają ze spacjami (np. 'C401F00018 /202604') — normalizacja
    daje stabilny klucz dopasowania niezależny od formatowania źródła.
    """
    return " ".join(numer.split())
