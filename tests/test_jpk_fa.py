"""Testy adaptera JPK_FA na realnej próbce (ABACUS, marzec 2026)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from audytor.models import Faktura
from audytor.sources.base import normalizuj_numer
from audytor.sources.jpk_fa import JpkFaError, wczytaj_jpk_fa

FIXTURE = Path(__file__).parent / "fixtures" / "jpk_fa_sample.xml"


@pytest.fixture(scope="module")
def faktury():
    return wczytaj_jpk_fa(FIXTURE)


class TestWczytywanieJpkFa:
    def test_liczba_faktur(self, faktury):
        assert len(faktury) == 3

    def test_pierwsza_faktura_kompletna(self, faktury):
        faktura = faktury[0]
        assert isinstance(faktura, Faktura)
        assert faktura.numer == "1/03/2026"
        assert faktura.data == date(2026, 3, 2)
        assert faktura.nip_kontrahenta == "7162826892"
        assert faktura.kwota_brutto == Decimal("123.00")

    def test_suma_brutto_zgodna_z_kontrolka(self, faktury):
        # FakturaCtrl/WartoscFaktur = 1335.83
        assert sum(f.kwota_brutto for f in faktury) == Decimal("1335.83")

    def test_wszystkie_kwoty_to_decimal(self, faktury):
        kwoty = {f.numer: f.kwota_brutto for f in faktury}
        assert kwoty["2/03/2026"] == Decimal("968.06")
        assert kwoty["3/03/2026"] == Decimal("244.77")


class TestBledyParsowania:
    def test_pusty_plik_bez_faktur(self, tmp_path):
        pusty = tmp_path / "pusty.xml"
        pusty.write_text(
            '<JPK xmlns="http://jpk.mf.gov.pl/wzor/2022/02/17/02171/"></JPK>',
            encoding="utf-8",
        )
        with pytest.raises(JpkFaError, match="nie zawiera żadnej faktury"):
            wczytaj_jpk_fa(pusty)

    def test_brak_obowiazkowego_pola(self, tmp_path):
        bez_kwoty = tmp_path / "bez_kwoty.xml"
        bez_kwoty.write_text(
            '<JPK xmlns="http://jpk.mf.gov.pl/wzor/2022/02/17/02171/">'
            "<Faktura><P_1>2026-03-02</P_1><P_2A>5/03/2026</P_2A></Faktura></JPK>",
            encoding="utf-8",
        )
        with pytest.raises(JpkFaError, match="P_15.*5/03/2026"):
            wczytaj_jpk_fa(bez_kwoty)

    def test_zepsuty_xml(self, tmp_path):
        zepsuty = tmp_path / "zepsuty.xml"
        zepsuty.write_text("<JPK><Faktura>", encoding="utf-8")
        with pytest.raises(JpkFaError, match="Nieprawidłowy XML"):
            wczytaj_jpk_fa(zepsuty)


class TestNormalizacjaNumeru:
    def test_redukcja_spacji(self):
        assert normalizuj_numer("FV 1/26 ") == normalizuj_numer("FV 1/26")

    def test_wielokrotne_spacje(self):
        assert normalizuj_numer("C401F00018  /202604") == "C401F00018 /202604"
