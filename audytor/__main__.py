"""Headless CLI audytora (R11) — punkt wejścia przyszłego folder-watchera.

Użycie:
    python -m audytor <kpir.xlsx> --karta-json karta.json [--jpk-fa fa.xml] [--out raport.md]

Exit code: 0 = same OK/POMINIĘTO, 1 = ostrzeżenia, 2 = błędy
(watcher/cron łatwo rozróżni wynik).
"""

import argparse
import json
import sys
from pathlib import Path

from audytor.models import Faktura, KartaKlienta, KsiegaMiesiac, TerminWyplaty
from audytor.parser_kpir import parse_kpir
from audytor.report import raport_markdown
from audytor.rules.engine import AuditResult, Status, run_audit
from audytor.sources.base import scal_faktury
from audytor.sources.jpk_fa import wczytaj_jpk_fa

EXIT_CODE = {Status.OK: 0, Status.POMINIETO: 0, Status.OSTRZEZENIE: 1, Status.BLAD: 2}


def main(argv: list[str] | None = None) -> int:
    args = _parsuj_argumenty(argv)

    ksiega = parse_kpir(args.kpir)
    faktury = _wczytaj_faktury(args.jpk_fa)
    karta = _wczytaj_karte_json(args.karta_json)

    wynik = run_audit(ksiega, faktury, karta)
    _zapisz_raport(wynik, args.out)
    return EXIT_CODE[wynik.status_zbiorczy]


def _parsuj_argumenty(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="audytor", description="Audyt domknięcia miesiąca KPiR")
    parser.add_argument("kpir", type=Path, help="Plik KPiR (wydruk szeroki XLSX)")
    parser.add_argument("--karta-json", type=Path, required=True, help="Karta klienta w JSON")
    parser.add_argument(
        "--jpk-fa",
        type=Path,
        action="append",
        default=None,
        help="Plik JPK_FA XML (opcjonalny; można podać wielokrotnie: sprzedaż i dokumenty)",
    )
    parser.add_argument("--out", type=Path, default=None, help="Plik raportu .md (domyślnie stdout)")
    return parser.parse_args(argv)


def _wczytaj_faktury(sciezki: list[Path] | None) -> list[Faktura] | None:
    if not sciezki:
        return None
    return scal_faktury(wczytaj_jpk_fa(sciezka) for sciezka in sciezki)


def _wczytaj_karte_json(sciezka: Path) -> KartaKlienta:
    # utf-8-sig toleruje BOM (pliki tworzone np. przez PowerShell na Windows).
    dane = json.loads(sciezka.read_text(encoding="utf-8-sig"))
    return KartaKlienta(
        nip=str(dane["nip"]),
        zatrudnia_pracownikow=bool(dane["zatrudnia_pracownikow"]),
        termin_wyplaty=TerminWyplaty(dane["termin_wyplaty"]),
        liczba_kas=int(dane["liczba_kas"]),
        proporcje_paliwa={int(x) for x in dane.get("proporcje_paliwa", [])},
    )


def _zapisz_raport(wynik: AuditResult, out: Path | None) -> None:
    raport = raport_markdown(wynik)
    if out is None:
        # Bajty UTF-8 omijają kodek konsoli (np. cp1250 na Windows nie ma emoji).
        sys.stdout.buffer.write(raport.encode("utf-8"))
    else:
        out.write_text(raport, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
