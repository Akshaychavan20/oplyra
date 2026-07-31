"""
Extensible multi-currency helpers for campaign budgets.

Add a new currency by appending an entry to CURRENCIES (and optionally
SELECTABLE_CURRENCY_CODES for wizard/edit selectors). Formatting and
validation pick up the new code automatically.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

Number = Union[int, float, Decimal, str, None]

# ---------------------------------------------------------------------------
# Registry — add currencies here; no other code changes required for formatting.
# ---------------------------------------------------------------------------
CURRENCIES: Dict[str, Dict[str, Any]] = {
    'INR': {
        'code': 'INR',
        'name': 'Indian Rupee',
        'symbol': '₹',
        'numbering': 'indian',  # lakh/crore grouping
        'decimals': 2,
    },
    'USD': {
        'code': 'USD',
        'name': 'US Dollar',
        'symbol': '$',
        'numbering': 'intl',
        'decimals': 2,
    },
    # Ready for future enablement in SELECTABLE_CURRENCY_CODES:
    'EUR': {
        'code': 'EUR',
        'name': 'Euro',
        'symbol': '€',
        'numbering': 'intl',
        'decimals': 2,
    },
    'GBP': {
        'code': 'GBP',
        'name': 'British Pound',
        'symbol': '£',
        'numbering': 'intl',
        'decimals': 2,
    },
    'AED': {
        'code': 'AED',
        'name': 'UAE Dirham',
        'symbol': 'د.إ',
        'numbering': 'intl',
        'decimals': 2,
    },
}

DEFAULT_CURRENCY = 'INR'

# Codes offered in Budget selectors (wizard / edit). Extend this list to expose
# currencies already defined in CURRENCIES.
SELECTABLE_CURRENCY_CODES: List[str] = ['INR', 'USD']


def normalize_currency(code: Optional[str]) -> str:
    """Return a known currency code; fall back to DEFAULT_CURRENCY."""
    if not code:
        return DEFAULT_CURRENCY
    key = str(code).strip().upper()
    if key in CURRENCIES:
        return key
    return DEFAULT_CURRENCY


def get_currency(code: Optional[str]) -> Dict[str, Any]:
    return CURRENCIES[normalize_currency(code)]


def get_symbol(code: Optional[str]) -> str:
    return get_currency(code)['symbol']


def selectable_currencies() -> List[Dict[str, Any]]:
    """Currency options for UI selectors (order preserved)."""
    return [CURRENCIES[c] for c in SELECTABLE_CURRENCY_CODES if c in CURRENCIES]


def _to_decimal(amount: Number) -> Decimal:
    if amount is None:
        return Decimal('0')
    if isinstance(amount, Decimal):
        return amount
    try:
        return Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _format_intl_integer(int_str: str) -> str:
    """Western grouping: 100000 → 100,000."""
    if len(int_str) <= 3:
        return int_str
    parts = []
    while int_str:
        parts.append(int_str[-3:])
        int_str = int_str[:-3]
    return ','.join(reversed(parts))


def _format_indian_integer(int_str: str) -> str:
    """Indian grouping: 100000 → 1,00,000."""
    if len(int_str) <= 3:
        return int_str
    last3 = int_str[-3:]
    rest = int_str[:-3]
    groups = []
    while rest:
        groups.append(rest[-2:])
        rest = rest[:-2]
    return ','.join(reversed(groups)) + ',' + last3


def format_number(amount: Number, currency: Optional[str] = None) -> str:
    """Format a numeric amount with the currency's numbering style (no symbol)."""
    meta = get_currency(currency)
    decimals = int(meta.get('decimals', 2))
    value = _to_decimal(amount)
    quant = Decimal('1').scaleb(-decimals)  # 0.01 for decimals=2
    value = value.quantize(quant, rounding=ROUND_HALF_UP)

    negative = value < 0
    value = abs(value)
    raw = f'{value:.{decimals}f}'
    int_part, frac_part = raw.split('.')

    if meta.get('numbering') == 'indian':
        grouped = _format_indian_integer(int_part)
    else:
        grouped = _format_intl_integer(int_part)

    formatted = f'{grouped}.{frac_part}' if decimals > 0 else grouped
    return f'-{formatted}' if negative else formatted


def format_money(amount: Number, currency: Optional[str] = None) -> str:
    """Format amount with currency symbol, e.g. ₹1,00,000.00 or $100,000.00."""
    meta = get_currency(currency)
    return f"{meta['symbol']}{format_number(amount, meta['code'])}"


def format_money_totals(
    items: Iterable[Mapping[str, Any]],
    amount_key: str = 'budget',
    currency_key: str = 'currency',
) -> str:
    """
    Sum amounts grouped by currency and join formatted totals.
    Useful when a page mixes INR and USD campaigns.
    """
    totals: Dict[str, Decimal] = {}
    for item in items:
        if isinstance(item, Mapping):
            code = normalize_currency(item.get(currency_key))
            amt = _to_decimal(item.get(amount_key))
        else:
            code = normalize_currency(getattr(item, currency_key, None))
            amt = _to_decimal(getattr(item, amount_key, 0))
        totals[code] = totals.get(code, Decimal('0')) + amt

    if not totals:
        return format_money(0, DEFAULT_CURRENCY)

    # Prefer selectable order, then any remaining codes alphabetically
    order = list(SELECTABLE_CURRENCY_CODES) + sorted(
        c for c in totals if c not in SELECTABLE_CURRENCY_CODES
    )
    parts = [format_money(totals[c], c) for c in order if c in totals]
    return ' · '.join(parts)


def currency_registry_public() -> Dict[str, Any]:
    """JSON-serializable registry for front-end bootstrapping."""
    return {
        'default': DEFAULT_CURRENCY,
        'selectable': SELECTABLE_CURRENCY_CODES,
        'currencies': {
            code: {
                'code': meta['code'],
                'name': meta['name'],
                'symbol': meta['symbol'],
                'numbering': meta['numbering'],
                'decimals': meta.get('decimals', 2),
            }
            for code, meta in CURRENCIES.items()
        },
    }
