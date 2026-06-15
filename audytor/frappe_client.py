"""Klient read-only do odczytu Karty Charakterystyki z Frappe CRM (R9).

Brak karty dla NIP → `None` (UI przechodzi w tryb ręczny). Niedostępność
Frappe (timeout, błąd HTTP) → `FrappeUnavailable` — MVP nie może się
zawiesić na kapryśnym self-hosted Frappe; UI łapie to i oferuje tryb ręczny.
"""

import json

import requests

from audytor.models import KartaKlienta, TerminWyplaty

DOCTYPE = "Karta Charakterystyki"
DEFAULT_TIMEOUT = 10


class FrappeError(Exception):
    """Bazowy błąd domenowy klienta Frappe."""


class FrappeUnavailable(FrappeError):
    """Frappe nieosiągalne (sieć/timeout/HTTP 5xx) — przejdź w tryb ręczny."""


def pobierz_karte(
    nip: str,
    base_url: str,
    api_key: str,
    api_secret: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> KartaKlienta | None:
    """Pobiera kartę klienta po NIP. Zwraca `None`, gdy karty nie ma."""
    url = f"{base_url.rstrip('/')}/api/resource/{DOCTYPE}"
    params = {
        "filters": json.dumps([["nip", "=", nip]]),
        "fields": json.dumps(
            ["nip", "zatrudnia_pracownikow", "termin_wyplaty", "liczba_kas", "proporcje_paliwa"]
        ),
    }
    headers = {"Authorization": f"token {api_key}:{api_secret}"}

    try:
        odpowiedz = requests.get(url, params=params, headers=headers, timeout=timeout)
        odpowiedz.raise_for_status()
    except requests.RequestException as exc:
        raise FrappeUnavailable(f"Frappe nieosiągalne: {exc}") from exc

    rekordy = odpowiedz.json().get("data", [])
    if not rekordy:
        return None
    return _mapuj_karte(rekordy[0])


def _mapuj_karte(rekord: dict) -> KartaKlienta:
    try:
        return KartaKlienta(
            nip=str(rekord["nip"]),
            zatrudnia_pracownikow=bool(rekord["zatrudnia_pracownikow"]),
            termin_wyplaty=TerminWyplaty(rekord["termin_wyplaty"]),
            liczba_kas=int(rekord["liczba_kas"]),
            proporcje_paliwa=_parsuj_proporcje(rekord.get("proporcje_paliwa")),
        )
    except (KeyError, ValueError) as exc:
        raise FrappeError(f"Nieprawidłowy rekord Karty Charakterystyki: {exc}") from exc


def _parsuj_proporcje(wartosc) -> set[int]:
    """Proporcje paliwa z Frappe (lista, CSV lub JSON) → set[int]."""
    if wartosc is None or wartosc == "":
        return set()
    if isinstance(wartosc, (list, tuple)):
        return {int(x) for x in wartosc}
    return {int(x.strip()) for x in str(wartosc).split(",") if x.strip()}
