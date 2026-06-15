"""Testy klienta Frappe na mockowanym HTTP (bez żywego połączenia)."""

import json

import pytest
import requests

from audytor.frappe_client import (
    FrappeError,
    FrappeUnavailable,
    pobierz_karte,
)
from audytor.models import KartaKlienta, TerminWyplaty

BASE_URL = "https://frappe.example.com"
KLUCZE = {"api_key": "k", "api_secret": "s"}


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _zamontuj(monkeypatch, response=None, wyjatek=None):
    def fake_get(url, params=None, headers=None, timeout=None):
        if wyjatek is not None:
            raise wyjatek
        return response

    monkeypatch.setattr(requests, "get", fake_get)


class TestPobieranieKarty:
    def test_karta_istnieje_mapuje_pola(self, monkeypatch):
        payload = {
            "data": [
                {
                    "nip": "7162519569",
                    "zatrudnia_pracownikow": 1,
                    "termin_wyplaty": "do_10_nastepnego",
                    "liczba_kas": 2,
                    "proporcje_paliwa": "20,75",
                }
            ]
        }
        _zamontuj(monkeypatch, _FakeResponse(payload))

        karta = pobierz_karte("7162519569", BASE_URL, **KLUCZE)

        assert isinstance(karta, KartaKlienta)
        assert karta.nip == "7162519569"
        assert karta.zatrudnia_pracownikow is True
        assert karta.termin_wyplaty is TerminWyplaty.DO_10_NASTEPNEGO
        assert karta.liczba_kas == 2
        assert karta.proporcje_paliwa == {20, 75}

    def test_proporcje_jako_lista(self, monkeypatch):
        payload = {
            "data": [
                {
                    "nip": "1",
                    "zatrudnia_pracownikow": 0,
                    "termin_wyplaty": "do_konca_miesiaca",
                    "liczba_kas": 0,
                    "proporcje_paliwa": [20, 100],
                }
            ]
        }
        _zamontuj(monkeypatch, _FakeResponse(payload))

        karta = pobierz_karte("1", BASE_URL, **KLUCZE)

        assert karta.proporcje_paliwa == {20, 100}
        assert karta.zatrudnia_pracownikow is False

    def test_brak_karty_zwraca_none(self, monkeypatch):
        _zamontuj(monkeypatch, _FakeResponse({"data": []}))

        assert pobierz_karte("0000000000", BASE_URL, **KLUCZE) is None


class TestBledy:
    def test_http_500_to_frappe_unavailable(self, monkeypatch):
        _zamontuj(monkeypatch, _FakeResponse({}, status=500))

        with pytest.raises(FrappeUnavailable):
            pobierz_karte("1", BASE_URL, **KLUCZE)

    def test_timeout_to_frappe_unavailable(self, monkeypatch):
        _zamontuj(monkeypatch, wyjatek=requests.Timeout("timed out"))

        with pytest.raises(FrappeUnavailable):
            pobierz_karte("1", BASE_URL, **KLUCZE)

    def test_zepsuty_rekord_to_frappe_error(self, monkeypatch):
        payload = {"data": [{"nip": "1", "termin_wyplaty": "nieznany_termin"}]}
        _zamontuj(monkeypatch, _FakeResponse(payload))

        with pytest.raises(FrappeError):
            pobierz_karte("1", BASE_URL, **KLUCZE)
