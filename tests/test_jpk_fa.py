"""Testy adaptera JPK_FA na realnej próbce (ABACUS, marzec 2026)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from audytor.models import Faktura
from audytor.sources.base import normalizuj_numer, scal_faktury
from audytor.sources.jpk_fa import JpkFaError, wczytaj_jpk_fa

FIXTURE = Path(__file__).parent / "fixtures" / "jpk_fa_sample.xml"

wymaga_fixture = pytest.mark.skipif(
    not FIXTURE.exists(),
    reason="Brak realnego pliku JPK_FA (dane klienta, poza repo) — umieść go w tests/fixtures/",
)


@pytest.fixture(scope="module")
def faktury():
    return wczytaj_jpk_fa(FIXTURE)


@wymaga_fixture
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


def _jpk_z_faktura(nip_wlasciciela: str, nip_sprzedawcy: str, nip_nabywcy: str) -> str:
    return (
        '<JPK xmlns="http://jpk.mf.gov.pl/wzor/2022/02/17/02171/">'
        f"<Podmiot1><IdentyfikatorPodmiotu><NIP>{nip_wlasciciela}</NIP>"
        "</IdentyfikatorPodmiotu></Podmiot1>"
        "<Faktura><P_1>2026-05-04</P_1><P_2A>FX/1</P_2A>"
        f"<P_4B>{nip_sprzedawcy}</P_4B><P_5B>{nip_nabywcy}</P_5B>"
        "<P_15>100.00</P_15></Faktura></JPK>"
    )


class TestOrientacjaKontrahenta:
    def test_rejestr_zakupu_kontrahent_to_sprzedawca(self, tmp_path):
        # Właściciel = nabywca (P_5B) → kontrahent to sprzedawca (P_4B).
        plik = tmp_path / "zakup.xml"
        plik.write_text(_jpk_z_faktura("1111111111", "2222222222", "1111111111"), encoding="utf-8")
        faktury = wczytaj_jpk_fa(plik)
        assert faktury[0].nip_kontrahenta == "2222222222"

    def test_rejestr_sprzedazy_kontrahent_to_nabywca(self, tmp_path):
        # Właściciel = sprzedawca (P_4B) → kontrahent to nabywca (P_5B).
        plik = tmp_path / "sprzedaz.xml"
        plik.write_text(_jpk_z_faktura("1111111111", "1111111111", "3333333333"), encoding="utf-8")
        faktury = wczytaj_jpk_fa(plik)
        assert faktury[0].nip_kontrahenta == "3333333333"


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


class TestScalanieFaktur:
    def _faktura(self, numer, nip="9", kwota="100"):
        return Faktura(numer=numer, data=date(2026, 5, 1), nip_kontrahenta=nip, kwota_brutto=Decimal(kwota))

    def test_dedup_powtorki_z_dwoch_zbiorow(self):
        wspolna = self._faktura("FV/1")
        sprzedaz = [wspolna, self._faktura("FV/2")]
        dokumenty = [wspolna, self._faktura("FV/3")]  # FV/1 powtórzona, FV/3 tylko tu
        scalone = scal_faktury([sprzedaz, dokumenty])
        assert [f.numer for f in scalone] == ["FV/1", "FV/2", "FV/3"]

    def test_ten_sam_numer_inny_kontrahent_nie_jest_duplikatem(self):
        a = self._faktura("FV/1", nip="111")
        b = self._faktura("FV/1", nip="222")
        assert len(scal_faktury([[a], [b]])) == 2

    def test_numer_ze_spacjami_traktowany_jak_ten_sam(self):
        a = self._faktura("FV 1/26")
        b = self._faktura("FV  1/26")  # nadmiarowa spacja
        assert len(scal_faktury([[a], [b]])) == 1


class TestNormalizacjaNumeru:
    def test_redukcja_spacji(self):
        assert normalizuj_numer("FV 1/26 ") == normalizuj_numer("FV 1/26")

    def test_wielokrotne_spacje(self):
        assert normalizuj_numer("C401F00018  /202604") == "C401F00018 /202604"
