"""Modele danych silnika audytu KPiR."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

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
class Faktura:
    """Znormalizowana faktura, niezależna od źródła (JPK_FA, Saldeo, ...)."""

    numer: str
    data: date
    nip_kontrahenta: str | None
    kwota_brutto: Decimal


class TerminWyplaty(str, Enum):
    """Kiedy klient wypłaca wynagrodzenia — steruje oczekiwanym okresem listy płac."""

    DO_10_NASTEPNEGO = "do_10_nastepnego"  # w M lista za M-1
    DO_KONCA_MIESIACA = "do_konca_miesiaca"  # w M lista za M


@dataclass(frozen=True)
class KartaKlienta:
    """Parametry charakterystyki klienta sterujące kontrolami (R9).

    Źródło: DocType we Frappe albo ręczne wprowadzenie w UI (fallback MVP).
    """

    nip: str
    zatrudnia_pracownikow: bool
    termin_wyplaty: TerminWyplaty
    liczba_kas: int
    proporcje_paliwa: set[int]


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
