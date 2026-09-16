"""Known individual currency catalog for FX cross-rate pairs.

Unlike metals_catalog.py (an opaque code -> Yahoo symbol lookup, because
"xau" -> "GC=F" has no mechanical relationship), currency pairs map to
Yahoo tickers deterministically: "eurusd" -> "EURUSD=X" is just
uppercasing the 6-letter pair code. So this catalog whitelists individual
ISO 4217 *currency* codes (not pairs) — a pair is valid iff both halves
are in this catalog and they differ. See app/services/currency_service.py
for how a valid pair becomes a Yahoo ticker, passed to
app/sources/acoes_yahoo.py with suffix="".

Curated for the project's Brazilian dev/small-business audience (see
project/CONTEXT.md): G10-ish majors, BRL, top trade partner (CNY), and
Mercosul/LatAm neighbors. Deliberately excludes ultra-low-value currencies
(e.g. VND) where Yahoo's own reported precision rounds the rate to 0.0.
"""

SUPPORTED_CURRENCIES: dict[str, str] = {
    "usd": "US Dollar",
    "eur": "Euro",
    "gbp": "British Pound",
    "jpy": "Japanese Yen",
    "chf": "Swiss Franc",
    "cad": "Canadian Dollar",
    "aud": "Australian Dollar",
    "nzd": "New Zealand Dollar",
    "cny": "Chinese Yuan",
    "brl": "Brazilian Real",
    "ars": "Argentine Peso",
    "uyu": "Uruguayan Peso",
    "pyg": "Paraguayan Guarani",
    "clp": "Chilean Peso",
    "cop": "Colombian Peso",
    "pen": "Peruvian Sol",
    "mxn": "Mexican Peso",
}


def resolve_pair(pair_code: str) -> tuple[str, str] | None:
    """Split/validate a 6-letter pair code like "eurusd" into
    `(base, quote)` — `None` if malformed, either half is unknown, or
    base == quote."""
    pair_code = pair_code.lower()
    if len(pair_code) != 6:
        return None
    base, quote = pair_code[:3], pair_code[3:]
    if base not in SUPPORTED_CURRENCIES or quote not in SUPPORTED_CURRENCIES:
        return None
    if base == quote:
        return None
    return base, quote
