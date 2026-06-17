"""UI Streamlit audytora KPiR (R10) — upload pliku, karta klienta, raport.

Logika audytu jest w czystym silniku (`run_audit`); ten plik to tylko
adapter wejścia/wyjścia (R11 — parytet z CLI). Funkcje pomocnicze
(`zbuduj_karte`, `audytuj`) są testowalne bez uruchamiania Streamlit.
"""

from typing import BinaryIO

import streamlit as st

from audytor.models import Faktura, KartaKlienta, TerminWyplaty
from audytor.parser_kpir import ParserError, parse_kpir
from audytor.report import IKONY, raport_markdown
from audytor.rules.engine import AuditResult, Status, run_audit
from audytor.sources.base import scal_faktury
from audytor.sources.jpk_fa import JpkFaError, wczytaj_jpk_fa

OPIS_TERMINU = {
    "do 10. następnego miesiąca (lista za poprzedni miesiąc)": TerminWyplaty.DO_10_NASTEPNEGO,
    "do końca miesiąca (lista za bieżący miesiąc)": TerminWyplaty.DO_KONCA_MIESIACA,
}
RENDER_STATUSU = {
    Status.OK: st.success,
    Status.OSTRZEZENIE: st.warning,
    Status.BLAD: st.error,
    Status.POMINIETO: st.info,
}


def zbuduj_karte(
    nip: str,
    zatrudnia_pracownikow: bool,
    termin_wyplaty: TerminWyplaty,
    liczba_kas: int,
    proporcje_paliwa: set[int],
) -> KartaKlienta:
    """Buduje kartę z parametrów formularza (tryb ręczny — bez Frappe)."""
    return KartaKlienta(
        nip=nip,
        zatrudnia_pracownikow=zatrudnia_pracownikow,
        termin_wyplaty=termin_wyplaty,
        liczba_kas=liczba_kas,
        proporcje_paliwa=proporcje_paliwa,
    )


def audytuj(
    kpir_plik: BinaryIO,
    jpk_fa_pliki: list[BinaryIO] | None,
    karta: KartaKlienta,
) -> AuditResult:
    """Parsuje pliki i uruchamia silnik — wspólna ścieżka z CLI.

    `jpk_fa_pliki` to lista (zbiory sprzedaż + dokumenty); faktury są scalane
    bez duplikatów.
    """
    ksiega = parse_kpir(kpir_plik)
    faktury: list[Faktura] | None = (
        scal_faktury(wczytaj_jpk_fa(plik) for plik in jpk_fa_pliki) if jpk_fa_pliki else None
    )
    return run_audit(ksiega, faktury, karta)


def main() -> None:
    st.set_page_config(page_title="Audytor KPiR", page_icon="📒")
    st.title("📒 Audytor miesięczny KPiR")
    st.caption("Kontrola domknięcia miesiąca: faktury, lista płac, kasy, paliwo, DRA.")

    kpir_plik = st.file_uploader("Wydruk szeroki KPiR (XLSX z Enova)", type=["xlsx"])
    jpk_fa_pliki = st.file_uploader(
        "JPK_FA XML (opcjonalnie — kontrola faktur; możesz wgrać kilka: sprzedaż i dokumenty)",
        type=["xml"],
        accept_multiple_files=True,
    )

    st.subheader("Karta klienta")
    karta = _formularz_karty()

    if st.button("Uruchom audyt", type="primary", disabled=kpir_plik is None):
        _uruchom_i_pokaz(kpir_plik, jpk_fa_pliki, karta)


def _formularz_karty() -> KartaKlienta:
    nip = st.text_input("NIP klienta", help="Uzupełniany automatycznie z pliku, jeśli pusty")
    zatrudnia = st.checkbox("Zatrudnia pracowników")
    termin_wyplaty = _wybierz_termin_wyplaty() if zatrudnia else TerminWyplaty.DO_10_NASTEPNEGO
    liczba_kas = st.number_input("Liczba kas fiskalnych", min_value=0, step=1, value=0)
    proporcje_tekst = st.text_input("Dozwolone proporcje paliwa (po przecinku)", value="20,75")
    return zbuduj_karte(
        nip=nip.strip(),
        zatrudnia_pracownikow=zatrudnia,
        termin_wyplaty=termin_wyplaty,
        liczba_kas=int(liczba_kas),
        proporcje_paliwa=_parsuj_proporcje(proporcje_tekst),
    )


def _wybierz_termin_wyplaty() -> TerminWyplaty:
    """Pole widoczne tylko gdy klient zatrudnia pracowników."""
    return OPIS_TERMINU[st.selectbox("Termin wypłaty wynagrodzeń", list(OPIS_TERMINU))]


def _parsuj_proporcje(tekst: str) -> set[int]:
    return {int(x.strip()) for x in tekst.split(",") if x.strip().isdigit()}


def _uruchom_i_pokaz(kpir_plik, jpk_fa_pliki, karta: KartaKlienta) -> None:
    try:
        wynik = audytuj(kpir_plik, jpk_fa_pliki, karta)
    except ParserError as exc:
        st.error(f"Nie udało się odczytać pliku KPiR: {exc}")
        return
    except JpkFaError as exc:
        st.error(f"Nie udało się odczytać pliku JPK_FA: {exc}")
        return

    _pokaz_wynik(wynik)


def _pokaz_wynik(wynik: AuditResult) -> None:
    st.divider()
    st.header(f"{wynik.nazwa_klienta}")
    st.write(f"**NIP:** {wynik.nip} • **Okres:** {wynik.rok}/{wynik.miesiac:02d}")
    st.write(f"**Status zbiorczy:** {IKONY[wynik.status_zbiorczy]} {wynik.status_zbiorczy.value}")

    for kontrola in wynik.wyniki:
        naglowek = f"{IKONY[kontrola.status]} {kontrola.nazwa} — {kontrola.status.value}"
        RENDER_STATUSU[kontrola.status](naglowek)
        with st.expander("Szczegóły", expanded=kontrola.status in (Status.BLAD, Status.OSTRZEZENIE)):
            for szczegol in kontrola.szczegoly:
                st.write(f"- {szczegol}")

    st.download_button(
        "Pobierz raport (Markdown)",
        data=raport_markdown(wynik),
        file_name=f"audyt_{wynik.nip}_{wynik.rok}_{wynik.miesiac:02d}.md",
        mime="text/markdown",
    )


if __name__ == "__main__":
    main()
