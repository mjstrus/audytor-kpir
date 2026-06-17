"""Testy 5 kontroli silnika audytu — dane syntetyczne + integracja SMAKOSZ."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from audytor.models import (
    Faktura,
    KartaKlienta,
    KsiegaMiesiac,
    TerminWyplaty,
    WpisKPiR,
)
from audytor.parser_kpir import parse_kpir
from audytor.rules.checks import (
    kontrola_dra,
    kontrola_kas,
    kontrola_kompletnosci_faktur,
    kontrola_listy_plac,
    kontrola_paliwa,
)
from audytor.rules.engine import Status, run_audit

FIXTURE_KPIR = Path(__file__).parent / "fixtures" / "kpir_smakosz_2026_04.xlsx"


def _wpis(lp=1, opis="", nr_dowodu=None, identyfikator=None, data=date(2026, 4, 1), incydentalny=False):
    return WpisKPiR(
        lp=lp, data=data, identyfikator=identyfikator, opis=opis,
        kontrahent=None, nr_ksef=None, nr_dowodu=nr_dowodu, kwoty={}, incydentalny=incydentalny,
    )


def _ksiega(wpisy, rok=2026, miesiac=4):
    return KsiegaMiesiac(
        nazwa_podatnika="TEST", nip_podatnika="1", rok=rok, miesiac=miesiac,
        wpisy=wpisy, suma_miesiaca={}, narastajaco={},
    )


def _karta(zatrudnia=False, termin=TerminWyplaty.DO_10_NASTEPNEGO, kasy=0, proporcje=frozenset()):
    return KartaKlienta(
        nip="1", zatrudnia_pracownikow=zatrudnia, termin_wyplaty=termin,
        liczba_kas=kasy, proporcje_paliwa=set(proporcje),
    )


class TestPaliwo:
    def test_brak_wpisow_paliwowych_pomijane(self):
        wynik = kontrola_paliwa(_ksiega([_wpis(opis="zakup towaru")]), _karta(proporcje={20}))
        assert wynik.status is Status.POMINIETO

    def test_wszystkie_proporcje_dozwolone_ok(self):
        ksiega = _ksiega([_wpis(opis="zakup paliwa 20"), _wpis(opis="zakup paliwa 75")])
        wynik = kontrola_paliwa(ksiega, _karta(proporcje={20, 75}))
        assert wynik.status is Status.OK

    def test_niedozwolona_proporcja_blad(self):
        ksiega = _ksiega([_wpis(lp=5, opis="zakup paliwa 75")])
        wynik = kontrola_paliwa(ksiega, _karta(proporcje={20}))
        assert wynik.status is Status.BLAD
        assert wynik.pozycje[0].lp == 5
        assert "75" in wynik.szczegoly[0]


class TestDra:
    def test_dra_za_m_minus_1_ok(self):
        ksiega = _ksiega([_wpis(opis="DRA", nr_dowodu="DRA/2026/03/01")], miesiac=4)
        assert kontrola_dra(ksiega).status is Status.OK

    def test_dra_inny_okres_ostrzezenie(self):
        ksiega = _ksiega([_wpis(opis="DRA", nr_dowodu="DRA/2026/02/01")], miesiac=4)
        assert kontrola_dra(ksiega).status is Status.OSTRZEZENIE

    def test_brak_dra_blad(self):
        assert kontrola_dra(_ksiega([_wpis(opis="zakup towaru")])).status is Status.BLAD

    def test_styczen_oczekuje_grudnia_poprzedniego_roku(self):
        ksiega = _ksiega([_wpis(opis="DRA", nr_dowodu="DRA/2025/12/01")], rok=2026, miesiac=1)
        assert kontrola_dra(ksiega).status is Status.OK


class TestListyPlac:
    def test_bez_pracownikow_pomijane(self):
        wynik = kontrola_listy_plac(_ksiega([]), _karta(zatrudnia=False))
        assert wynik.status is Status.POMINIETO

    def test_pracownicy_bez_listy_blad(self):
        wynik = kontrola_listy_plac(_ksiega([_wpis(opis="zakup towaru")]), _karta(zatrudnia=True))
        assert wynik.status is Status.BLAD

    def test_lista_za_oczekiwany_okres_ok(self):
        ksiega = _ksiega([_wpis(opis="LPU", nr_dowodu="LPU/F/2026/03/1")], miesiac=4)
        wynik = kontrola_listy_plac(ksiega, _karta(zatrudnia=True, termin=TerminWyplaty.DO_10_NASTEPNEGO))
        assert wynik.status is Status.OK

    def test_lista_za_inny_okres_ostrzezenie(self):
        ksiega = _ksiega([_wpis(opis="LPU", nr_dowodu="LPU/F/2026/01/1")], miesiac=4)
        wynik = kontrola_listy_plac(ksiega, _karta(zatrudnia=True, termin=TerminWyplaty.DO_10_NASTEPNEGO))
        assert wynik.status is Status.OSTRZEZENIE

    def test_termin_do_konca_oczekuje_biezacego_miesiaca(self):
        ksiega = _ksiega([_wpis(opis="LPU", nr_dowodu="LPU/F/2026/04/1")], miesiac=4)
        wynik = kontrola_listy_plac(ksiega, _karta(zatrudnia=True, termin=TerminWyplaty.DO_KONCA_MIESIACA))
        assert wynik.status is Status.OK


class TestKasy:
    def test_brak_kas_pomijane(self):
        assert kontrola_kas(_ksiega([]), _karta(kasy=0)).status is Status.POMINIETO

    def test_raport_jedna_kasa_z_numerem_ok(self):
        ksiega = _ksiega([_wpis(nr_dowodu="Raport fiskalny 1/04/2026")], miesiac=4)
        assert kontrola_kas(ksiega, _karta(kasy=1)).status is Status.OK

    def test_skrot_rap_fisk_rozpoznany(self):
        ksiega = _ksiega([_wpis(nr_dowodu="Rap. fisk. 1/04/2026")], miesiac=4)
        assert kontrola_kas(ksiega, _karta(kasy=1)).status is Status.OK

    def test_wielkosc_liter_i_spacje_bez_znaczenia(self):
        for zapis in ("RAPORT FISKALNY 1/04/2026", "raport   fiskalny 1/04/2026", "RAP FISK 1/04/2026"):
            ksiega = _ksiega([_wpis(nr_dowodu=zapis)], miesiac=4)
            assert kontrola_kas(ksiega, _karta(kasy=1)).status is Status.OK, zapis

    def test_zapis_bez_numeru_to_kasa_pierwsza(self):
        # zgodność wsteczna: "Raport fiskalny MM/RRRR" = kasa nr 1
        ksiega = _ksiega([_wpis(nr_dowodu="Raport fiskalny 04/2026")], miesiac=4)
        assert kontrola_kas(ksiega, _karta(kasy=1)).status is Status.OK

    def test_dwie_kasy_komplet_ok(self):
        ksiega = _ksiega(
            [_wpis(nr_dowodu="Raport fiskalny 1/04/2026"), _wpis(nr_dowodu="Raport fiskalny 2/04/2026")],
            miesiac=4,
        )
        assert kontrola_kas(ksiega, _karta(kasy=2)).status is Status.OK

    def test_brak_drugiej_kasy_blad(self):
        ksiega = _ksiega([_wpis(nr_dowodu="Raport fiskalny 1/04/2026")], miesiac=4)
        wynik = kontrola_kas(ksiega, _karta(kasy=2))
        assert wynik.status is Status.BLAD
        assert "nr: 2" in wynik.szczegoly[0]

    def test_duplikat_numeru_nie_pokrywa_brakujacej_kasy(self):
        # dwa raporty kasy nr 1, brak kasy nr 2 → BŁĄD
        ksiega = _ksiega(
            [_wpis(nr_dowodu="Raport fiskalny 1/04/2026"), _wpis(nr_dowodu="Raport fiskalny 1/04/2026")],
            miesiac=4,
        )
        assert kontrola_kas(ksiega, _karta(kasy=2)).status is Status.BLAD

    def test_raport_za_zly_okres_blad(self):
        ksiega = _ksiega([_wpis(nr_dowodu="Raport fiskalny 1/03/2026")], miesiac=4)
        wynik = kontrola_kas(ksiega, _karta(kasy=1))
        assert wynik.status is Status.BLAD
        assert any("inny okres" in s for s in wynik.szczegoly)


class TestKompletnoscFaktur:
    def test_brak_jpk_pomijane(self):
        assert kontrola_kompletnosci_faktur(_ksiega([]), None).status is Status.POMINIETO

    def test_faktura_dopasowana_po_numerze_ok(self):
        ksiega = _ksiega([_wpis(nr_dowodu="FV 1/26")])
        faktury = [Faktura(numer="FV 1/26", data=date(2026, 4, 1), nip_kontrahenta="9", kwota_brutto=Decimal("10"))]
        assert kontrola_kompletnosci_faktur(ksiega, faktury).status is Status.OK

    def test_dopasowanie_mimo_sufiksu_rejestru(self):
        # KPiR dokleja do nr dowodu sufiks rejestru, np. "(ZR/2026/0092)";
        # numer z JPK ("(S)FS-1282/26/CGW") musi się i tak dopasować.
        ksiega = _ksiega([_wpis(nr_dowodu="(S)FS-1282/26/CGW (ZR/2026/0092)")])
        faktury = [
            Faktura(numer="(S)FS-1282/26/CGW", data=date(2026, 5, 4), nip_kontrahenta="9", kwota_brutto=Decimal("10"))
        ]
        assert kontrola_kompletnosci_faktur(ksiega, faktury).status is Status.OK

    def test_faktura_nieobecna_blad(self):
        ksiega = _ksiega([_wpis(nr_dowodu="INNY/1")])
        faktury = [Faktura(numer="FV 99/26", data=date(2026, 4, 5), nip_kontrahenta="9", kwota_brutto=Decimal("10"))]
        wynik = kontrola_kompletnosci_faktur(ksiega, faktury)
        assert wynik.status is Status.BLAD
        assert "FV 99/26" in wynik.szczegoly[0]

    def test_dopasowanie_heurystyczne_ostrzezenie(self):
        ksiega = _ksiega([_wpis(nr_dowodu="INNY/1", identyfikator="9", data=date(2026, 4, 5))])
        faktury = [Faktura(numer="FV 99/26", data=date(2026, 4, 5), nip_kontrahenta="9", kwota_brutto=Decimal("10"))]
        assert kontrola_kompletnosci_faktur(ksiega, faktury).status is Status.OSTRZEZENIE

    def test_wpis_incydentalny_nie_daje_dopasowania(self):
        ksiega = _ksiega([_wpis(nr_dowodu="FV 1/26", incydentalny=True)])
        faktury = [Faktura(numer="FV 1/26", data=date(2026, 4, 1), nip_kontrahenta="9", kwota_brutto=Decimal("10"))]
        assert kontrola_kompletnosci_faktur(ksiega, faktury).status is Status.BLAD

    def test_obcy_nip_zrodla_daje_ostrzezenie(self):
        # plik JPK_FA wystawiony na inny NIP niż podatnik z KPiR
        ksiega = _ksiega([_wpis(nr_dowodu="FV 1/26")])  # nip podatnika = "1"
        faktury = [Faktura(numer="FV 1/26", data=date(2026, 4, 1), nip_kontrahenta="9", kwota_brutto=Decimal("10"))]
        wynik = kontrola_kompletnosci_faktur(ksiega, faktury, nip_zrodel={"9999999999"})
        assert wynik.status is Status.OSTRZEZENIE
        assert "prawdopodobnie zły plik" in wynik.szczegoly[0]

    def test_zgodny_nip_zrodla_bez_ostrzezenia(self):
        ksiega = _ksiega([_wpis(nr_dowodu="FV 1/26")])  # nip podatnika = "1"
        faktury = [Faktura(numer="FV 1/26", data=date(2026, 4, 1), nip_kontrahenta="9", kwota_brutto=Decimal("10"))]
        wynik = kontrola_kompletnosci_faktur(ksiega, faktury, nip_zrodel={"1"})
        assert wynik.status is Status.OK


@pytest.mark.skipif(
    not FIXTURE_KPIR.exists(),
    reason="Brak realnego pliku KPiR (dane klienta, poza repo) — umieść go w tests/fixtures/",
)
class TestIntegracjaSmakosz:
    @pytest.fixture(scope="class")
    def ksiega(self):
        return parse_kpir(FIXTURE_KPIR)

    @pytest.fixture
    def karta(self):
        return _karta(zatrudnia=True, termin=TerminWyplaty.DO_10_NASTEPNEGO, kasy=0, proporcje={20, 75})

    def test_audyt_end_to_end(self, ksiega, karta):
        wynik = run_audit(ksiega, faktury=None, karta=karta)
        statusy = {w.nazwa: w.status for w in wynik.wyniki}

        assert statusy["Proporcje paliwa"] is Status.OK
        assert statusy["DRA (składki ZUS)"] is Status.OSTRZEZENIE  # DRA za 2026/02, oczekiwano 2026/03
        assert statusy["Lista płac"] is Status.OK  # LPU/LPE za 2026/03
        assert statusy["Raporty z kas fiskalnych"] is Status.POMINIETO  # 0 kas
        assert statusy["Kompletność faktur"] is Status.POMINIETO  # brak JPK_FA

    def test_status_zbiorczy_to_ostrzezenie(self, ksiega, karta):
        wynik = run_audit(ksiega, faktury=None, karta=karta)
        assert wynik.status_zbiorczy is Status.OSTRZEZENIE
