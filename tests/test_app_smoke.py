"""Smoke testy UI: import aplikacji + testowalne funkcje pomocnicze.

Renderowanie Streamlit nie jest testowane jednostkowo — sprawdzamy, że
logika (parytet z silnikiem) działa bez uruchamiania serwera Streamlit.
"""

from pathlib import Path

import pytest

import app
from audytor.models import KartaKlienta, TerminWyplaty
from audytor.parser_kpir import ParserError
from audytor.rules.engine import Status

FIXTURE_KPIR = Path(__file__).parent / "fixtures" / "kpir_smakosz_2026_04.xlsx"


def test_import_aplikacji():
    assert hasattr(app, "main")
    assert callable(app.audytuj)


def test_zbuduj_karte_z_formularza():
    karta = app.zbuduj_karte(
        nip="7162519569",
        zatrudnia_pracownikow=True,
        termin_wyplaty=TerminWyplaty.DO_10_NASTEPNEGO,
        liczba_kas=0,
        proporcje_paliwa={20, 75},
    )
    assert isinstance(karta, KartaKlienta)
    assert karta.proporcje_paliwa == {20, 75}


def test_parsuj_proporcje_ignoruje_smieci():
    assert app._parsuj_proporcje("20, 75, abc, ") == {20, 75}


@pytest.mark.skipif(
    not FIXTURE_KPIR.exists(),
    reason="Brak realnego pliku KPiR (dane klienta, poza repo) — umieść go w tests/fixtures/",
)
def test_audytuj_happy_path_smakosz():
    karta = app.zbuduj_karte("7162519569", True, TerminWyplaty.DO_10_NASTEPNEGO, 0, {20, 75})
    with FIXTURE_KPIR.open("rb") as plik:
        wynik = app.audytuj(plik, None, karta)

    statusy = {w.nazwa: w.status for w in wynik.wyniki}
    assert statusy["Proporcje paliwa"] is Status.OK
    assert statusy["DRA (składki ZUS)"] is Status.OSTRZEZENIE
    assert wynik.status_zbiorczy is Status.OSTRZEZENIE


def test_audytuj_zly_plik_rzuca_parser_error(tmp_path):
    import openpyxl

    zly = tmp_path / "zly.xlsx"
    openpyxl.Workbook().save(zly)  # pusty arkusz bez nagłówka KPiR
    karta = app.zbuduj_karte("1", False, TerminWyplaty.DO_KONCA_MIESIACA, 0, set())

    with zly.open("rb") as plik, pytest.raises(ParserError):
        app.audytuj(plik, None, karta)
