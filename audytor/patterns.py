"""Wzorce identyfikacji wpisów KPiR (konwencje opisów/dowodów Enova 365).

Konwencje mogą różnić się niuansami między klientami — wszystkie regexy
trzymamy w tym jednym module.
"""

import re

# "zakup paliwa 20" / "zakup paliwa 75" — proporcja odliczenia wprost w opisie
PALIWO_RE = re.compile(r"zakup paliwa\s+(\d{1,3})", re.IGNORECASE)

# Lista płac: opis "LPU"/"LPE", okres w nr dowodu "LPU/F/2026/03/1"
LISTA_PLAC_OPIS_RE = re.compile(r"^(LPU|LPE)\b")
LISTA_PLAC_DOWOD_RE = re.compile(r"^(LPU|LPE)/[A-Z]+/(\d{4})/(\d{2})")

# DRA: nr dowodu "DRA/2026/02/01"
DRA_DOWOD_RE = re.compile(r"^DRA/(\d{4})/(\d{2})")

# Rozliczenia międzyokresowe i amortyzacja (wyłączane z dopasowania faktur)
RMK_DOWOD_RE = re.compile(r"^RMK/(\d{4})/(\d{2})")
AMORTYZACJA_OPIS_RE = re.compile(r"^amortyzacja", re.IGNORECASE)

# Raport okresowy z kasy fiskalnej — PLACEHOLDER do kalibracji na próbce
# klienta z kasą (odroczone w planie; brak wpisów kasowych w próbce SMAKOSZ).
RAPORT_KASY_RE = re.compile(r"raport\s+(okresowy|miesięczny|fiskalny)", re.IGNORECASE)

# Znacznik wpisu incydentalnego (pojawia się w kolumnie kontrahenta)
INCYDENTALNY_MARKER = "!INCYDENTALNY"


def proporcja_paliwa(opis: str) -> int | None:
    """Zwraca proporcję odliczenia z opisu wpisu paliwowego albo None."""
    match = PALIWO_RE.search(opis)
    return int(match.group(1)) if match else None


def okres_listy_plac(nr_dowodu: str) -> tuple[str, int, int] | None:
    """Zwraca (typ LPU/LPE, rok, miesiąc) z nr dowodu listy płac albo None."""
    match = LISTA_PLAC_DOWOD_RE.match(nr_dowodu)
    if not match:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def okres_dra(nr_dowodu: str) -> tuple[int, int] | None:
    """Zwraca (rok, miesiąc) z nr dowodu DRA albo None."""
    match = DRA_DOWOD_RE.match(nr_dowodu)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
