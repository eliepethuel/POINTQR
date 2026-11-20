"""Public holidays of Côte d'Ivoire (EF-15). Companies can add, edit or mark days as worked.

Islamic holidays follow the lunar calendar and are fixed each year by decree: the dates below are
the expected ones and must be checked against the official announcement.
"""

from datetime import date, timedelta

FIXED: list[tuple[int, int, str]] = [
    (1, 1, "Jour de l'An"),
    (5, 1, "Fête du Travail"),
    (8, 7, "Fête de l'Indépendance"),
    (8, 15, "Assomption"),
    (11, 1, "Toussaint"),
    (11, 15, "Journée nationale de la Paix"),
    (12, 25, "Noël"),
]

#: Expected dates (decree confirms them each year).
ISLAMIC: dict[int, list[tuple[date, str]]] = {
    2026: [
        (date(2026, 3, 17), "Lendemain de la Nuit du Destin"),
        (date(2026, 3, 20), "Aïd el-Fitr (fin du Ramadan)"),
        (date(2026, 5, 27), "Aïd el-Kébir (Tabaski)"),
        (date(2026, 8, 26), "Maouloud (naissance du Prophète)"),
    ],
    2027: [
        (date(2027, 3, 6), "Lendemain de la Nuit du Destin"),
        (date(2027, 3, 10), "Aïd el-Fitr (fin du Ramadan)"),
        (date(2027, 5, 17), "Aïd el-Kébir (Tabaski)"),
        (date(2027, 8, 16), "Maouloud (naissance du Prophète)"),
    ],
}


def easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm (Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def cote_divoire_holidays(year: int) -> list[tuple[date, str]]:
    easter = easter_sunday(year)
    days = [(date(year, m, d), label) for m, d, label in FIXED]
    days += [
        (easter + timedelta(days=1), "Lundi de Pâques"),
        (easter + timedelta(days=39), "Ascension"),
        (easter + timedelta(days=50), "Lundi de Pentecôte"),
    ]
    days += ISLAMIC.get(year, [])
    return sorted(days)
