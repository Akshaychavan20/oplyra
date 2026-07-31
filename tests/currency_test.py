"""Unit tests for extensible campaign currency formatting."""
import unittest

from app.utils.currency import (
    format_money,
    format_number,
    normalize_currency,
    format_money_totals,
    DEFAULT_CURRENCY,
)


class CurrencyFormattingTest(unittest.TestCase):
    def test_default_is_inr(self):
        self.assertEqual(DEFAULT_CURRENCY, 'INR')
        self.assertEqual(normalize_currency(None), 'INR')
        self.assertEqual(normalize_currency('usd'), 'USD')
        self.assertEqual(normalize_currency('xyz'), 'INR')

    def test_inr_indian_numbering(self):
        self.assertEqual(format_number(100000, 'INR'), '1,00,000.00')
        self.assertEqual(format_money(100000, 'INR'), '₹1,00,000.00')
        self.assertEqual(format_money(1234567.89, 'INR'), '₹12,34,567.89')

    def test_usd_intl_numbering(self):
        self.assertEqual(format_number(100000, 'USD'), '100,000.00')
        self.assertEqual(format_money(100000, 'USD'), '$100,000.00')

    def test_mixed_totals(self):
        items = [
            {'budget': 100000, 'currency': 'INR'},
            {'budget': 500, 'currency': 'USD'},
            {'budget': 50000, 'currency': 'INR'},
        ]
        self.assertEqual(
            format_money_totals(items),
            '₹1,50,000.00 · $500.00',
        )


if __name__ == '__main__':
    unittest.main()
