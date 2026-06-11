"""Modele danych silnika audytu KPiR."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Numery kolumn kwotowych KPiR wg wydruku szerokiego Enova (etykiety (09)-(18))
KOLUMNY_KWOT = tuple(range(9, 19))

ZERO = Decimal("0")


@dataclass(frozen=True)
class WpisKPiR:
    """Pojedynczy wpis (rekord) z księgi — sklejony z 3 wierszy wydruku."""

    lp: int
    data: date
    identyfikator: str | None  # NIP lub inny identyfikator podatkowy kontrahenta
    opis: str
    kontrahent: str | None
    nr_ksef: str | None
    nr_dowodu: str | None
    kwoty: dict[int, Decimal] = field(default_factory=dict)  # kolumna (9-18) -> kwota
    incydentalny: bool = False

    def kwota(self, kolumna: int) -> Decimal:
        return self.kwoty.get(kolumna, ZERO)


@dataclass(frozen=True)
class KsiegaMiesiac:
    """Sparsowana księga za jeden miesiąc wraz z sumami kontrolnymi z wydruku."""

    nazwa_podatnika: str
    nip_podatnika: str
    rok: int
    miesiac: int
    wpisy: list[WpisKPiR]
    suma_miesiaca: dict[int, Decimal]  # kolumna -> "Suma miesiąca" z podsumowania
    narastajaco: dict[int, Decimal]  # kolumna -> "Razem od początku roku"
