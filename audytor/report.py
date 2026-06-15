"""Renderowanie wyniku audytu do czytelnego raportu (R10).

Wspólne dla CLI (Unit 6) i UI Streamlit (Unit 5) — jeden format, jedno miejsce.
"""

from audytor.rules.engine import AuditResult, Status

IKONY = {
    Status.OK: "✅",
    Status.OSTRZEZENIE: "🟡",
    Status.BLAD: "❌",
    Status.POMINIETO: "⚪",
}


def raport_markdown(wynik: AuditResult) -> str:
    """Buduje raport audytu w Markdown."""
    linie = [
        f"# Audyt KPiR — {wynik.nazwa_klienta}",
        "",
        f"- **NIP:** {wynik.nip}",
        f"- **Okres:** {wynik.rok}/{wynik.miesiac:02d}",
        f"- **Status zbiorczy:** {IKONY[wynik.status_zbiorczy]} {wynik.status_zbiorczy.value}",
        "",
        "## Kontrole",
        "",
    ]
    for kontrola in wynik.wyniki:
        linie.append(f"### {IKONY[kontrola.status]} {kontrola.nazwa} — {kontrola.status.value}")
        linie.extend(f"- {szczegol}" for szczegol in kontrola.szczegoly)
        linie.append("")
    return "\n".join(linie).rstrip() + "\n"
