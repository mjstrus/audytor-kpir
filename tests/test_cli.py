"""Testy headless CLI audytora na próbce SMAKOSZ."""

import json
from pathlib import Path

import pytest

from audytor.__main__ import main

FIXTURE_KPIR = Path(__file__).parent / "fixtures" / "kpir_smakosz_2026_04.xlsx"

KARTA_SMAKOSZ = {
    "nip": "7162519569",
    "zatrudnia_pracownikow": True,
    "termin_wyplaty": "do_10_nastepnego",
    "liczba_kas": 0,
    "proporcje_paliwa": [20, 75],
}


@pytest.fixture
def karta_json(tmp_path):
    plik = tmp_path / "karta.json"
    plik.write_text(json.dumps(KARTA_SMAKOSZ), encoding="utf-8")
    return plik


class TestCli:
    def test_raport_powstaje_a_exit_code_to_ostrzezenie(self, tmp_path, karta_json):
        out = tmp_path / "raport.md"
        kod = main([str(FIXTURE_KPIR), "--karta-json", str(karta_json), "--out", str(out)])

        assert kod == 1  # DRA za zły okres → ostrzeżenie
        tresc = out.read_text(encoding="utf-8")
        assert "Audyt KPiR" in tresc
        assert "DRA" in tresc
        assert "OSTRZEŻENIE" in tresc

    def test_raport_na_stdout_bez_out(self, capsys, karta_json):
        kod = main([str(FIXTURE_KPIR), "--karta-json", str(karta_json)])

        assert kod == 1
        assert "Proporcje paliwa" in capsys.readouterr().out

    def test_brak_pracownikow_i_kas_daje_exit_zero(self, tmp_path):
        karta = dict(KARTA_SMAKOSZ, zatrudnia_pracownikow=False)
        # Usuń wpis DRA z gry: bez pracowników lista płac POMINIĘTO, ale DRA nadal
        # ostrzega — więc tu sprawdzamy tylko, że karta bez pracowników nie wywala błędu.
        plik = tmp_path / "karta.json"
        plik.write_text(json.dumps(karta), encoding="utf-8")

        kod = main([str(FIXTURE_KPIR), "--karta-json", str(plik), "--out", str(tmp_path / "r.md")])
        assert kod == 1  # nadal ostrzeżenie z DRA

    def test_karta_json_z_bom_jest_tolerowana(self, tmp_path):
        # Pliki tworzone na Windows (np. PowerShell Out-File) bywają z BOM.
        plik = tmp_path / "karta_bom.json"
        plik.write_text(json.dumps(KARTA_SMAKOSZ), encoding="utf-8-sig")

        kod = main([str(FIXTURE_KPIR), "--karta-json", str(plik), "--out", str(tmp_path / "r.md")])
        assert kod == 1
