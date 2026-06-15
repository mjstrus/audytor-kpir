"""Model wyniku audytu i orkiestracja 5 kontroli (`run_audit`).

Czysty silnik — bez importów Streamlit/HTTP (R11). Wejście: sparsowana
księga, opcjonalna lista faktur, karta klienta. Wyjście: `AuditResult`.
"""

from dataclasses import dataclass, field
from enum import Enum

from audytor.models import Faktura, KartaKlienta, KsiegaMiesiac, WpisKPiR


class Status(str, Enum):
    """Status pojedynczej kontroli (jawność zamiast cichego 'OK')."""

    OK = "OK"
    OSTRZEZENIE = "OSTRZEŻENIE"
    BLAD = "BŁĄD"
    POMINIETO = "POMINIĘTO"


# Ważność statusów rosnąco — do wyznaczenia statusu zbiorczego audytu.
WAGA_STATUSU = {Status.POMINIETO: 0, Status.OK: 1, Status.OSTRZEZENIE: 2, Status.BLAD: 3}


@dataclass(frozen=True)
class WynikKontroli:
    """Wynik jednej kontroli: status + czytelne szczegóły + powiązane wpisy."""

    nazwa: str
    status: Status
    szczegoly: list[str] = field(default_factory=list)
    pozycje: list[WpisKPiR] = field(default_factory=list)


@dataclass(frozen=True)
class AuditResult:
    """Pełny wynik audytu klienta za miesiąc (R10)."""

    nazwa_klienta: str
    nip: str
    rok: int
    miesiac: int
    wyniki: list[WynikKontroli]

    @property
    def status_zbiorczy(self) -> Status:
        """Najgorszy status spośród kontroli (POMINIĘTO nie psuje wyniku)."""
        istotne = [w.status for w in self.wyniki if w.status is not Status.POMINIETO]
        if not istotne:
            return Status.POMINIETO
        return max(istotne, key=lambda s: WAGA_STATUSU[s])


def run_audit(
    ksiega: KsiegaMiesiac,
    faktury: list[Faktura] | None,
    karta: KartaKlienta,
) -> AuditResult:
    """Uruchamia 5 kontroli i składa wynik audytu (R4–R8)."""
    # Import lokalny, żeby uniknąć cyklu engine <-> checks.
    from audytor.rules import checks

    wyniki = [
        checks.kontrola_kompletnosci_faktur(ksiega, faktury),
        checks.kontrola_listy_plac(ksiega, karta),
        checks.kontrola_kas(ksiega, karta),
        checks.kontrola_paliwa(ksiega, karta),
        checks.kontrola_dra(ksiega),
    ]
    return AuditResult(
        nazwa_klienta=ksiega.nazwa_podatnika,
        nip=ksiega.nip_podatnika,
        rok=ksiega.rok,
        miesiac=ksiega.miesiac,
        wyniki=wyniki,
    )
