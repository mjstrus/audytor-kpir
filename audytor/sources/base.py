"""Protokół adaptera źródła faktur — wspólny kontrakt dla wszystkich źródeł."""

from pathlib import Path
from typing import BinaryIO, Protocol

from audytor.models import Faktura


class ZrodloFaktur(Protocol):
    """Każdy adapter (JPK_FA, Saldeo, ...) zwraca znormalizowaną listę faktur."""

    def wczytaj(self, plik: str | Path | BinaryIO) -> list[Faktura]:
        ...


def normalizuj_numer(numer: str) -> str:
    """Klucz porównania numeru faktury: trim + redukcja wielokrotnych spacji.

    W KPiR numery bywają ze spacjami (np. 'C401F00018 /202604') — normalizacja
    daje stabilny klucz dopasowania niezależny od formatowania źródła.
    """
    return " ".join(numer.split())
