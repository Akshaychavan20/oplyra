/**
 * Extensible campaign budget currency helpers.
 * Mirror of app/utils/currency.py — keep numbering rules in sync.
 *
 * To add a currency: append to CURRENCIES and SELECTABLE (if shown in UI).
 */
(function (global) {
    'use strict';

    var CURRENCIES = {
        INR: {
            code: 'INR',
            name: 'Indian Rupee',
            symbol: '₹',
            numbering: 'indian',
            decimals: 2
        },
        USD: {
            code: 'USD',
            name: 'US Dollar',
            symbol: '$',
            numbering: 'intl',
            decimals: 2
        },
        EUR: {
            code: 'EUR',
            name: 'Euro',
            symbol: '€',
            numbering: 'intl',
            decimals: 2
        },
        GBP: {
            code: 'GBP',
            name: 'British Pound',
            symbol: '£',
            numbering: 'intl',
            decimals: 2
        },
        AED: {
            code: 'AED',
            name: 'UAE Dirham',
            symbol: 'د.إ',
            numbering: 'intl',
            decimals: 2
        }
    };

    var DEFAULT_CURRENCY = 'INR';
    var SELECTABLE = ['INR', 'USD'];

    function normalize(code) {
        if (!code) return DEFAULT_CURRENCY;
        var key = String(code).trim().toUpperCase();
        return CURRENCIES[key] ? key : DEFAULT_CURRENCY;
    }

    function getCurrency(code) {
        return CURRENCIES[normalize(code)];
    }

    function formatIntlInteger(intStr) {
        if (intStr.length <= 3) return intStr;
        var parts = [];
        while (intStr.length > 0) {
            parts.unshift(intStr.slice(-3));
            intStr = intStr.slice(0, -3);
        }
        return parts.join(',');
    }

    function formatIndianInteger(intStr) {
        if (intStr.length <= 3) return intStr;
        var last3 = intStr.slice(-3);
        var rest = intStr.slice(0, -3);
        var groups = [];
        while (rest.length > 0) {
            groups.unshift(rest.slice(-2));
            rest = rest.slice(0, -2);
        }
        return groups.join(',') + ',' + last3;
    }

    function toNumber(amount) {
        var n = typeof amount === 'number' ? amount : parseFloat(amount);
        return isFinite(n) ? n : 0;
    }

    function formatNumber(amount, currency) {
        var meta = getCurrency(currency);
        var decimals = meta.decimals != null ? meta.decimals : 2;
        var value = toNumber(amount);
        var negative = value < 0;
        value = Math.abs(value);
        var fixed = value.toFixed(decimals);
        var parts = fixed.split('.');
        var intPart = parts[0];
        var fracPart = parts[1];
        var grouped = meta.numbering === 'indian'
            ? formatIndianInteger(intPart)
            : formatIntlInteger(intPart);
        var out = decimals > 0 ? grouped + '.' + fracPart : grouped;
        return negative ? '-' + out : out;
    }

    function formatMoney(amount, currency) {
        var meta = getCurrency(currency);
        return meta.symbol + formatNumber(amount, meta.code);
    }

    function selectableCurrencies() {
        return SELECTABLE.map(function (code) {
            return CURRENCIES[code];
        }).filter(Boolean);
    }

    /**
     * Bind a budget amount input + currency select + optional preview/symbol nodes.
     * options: { amountInput, currencySelect, symbolEl, previewEl, labelEl, defaultCurrency }
     */
    function bindBudgetField(options) {
        options = options || {};
        var amountInput = typeof options.amountInput === 'string'
            ? document.querySelector(options.amountInput)
            : options.amountInput;
        var currencySelect = typeof options.currencySelect === 'string'
            ? document.querySelector(options.currencySelect)
            : options.currencySelect;
        var symbolEl = typeof options.symbolEl === 'string'
            ? document.querySelector(options.symbolEl)
            : options.symbolEl;
        var previewEl = typeof options.previewEl === 'string'
            ? document.querySelector(options.previewEl)
            : options.previewEl;
        var labelEl = typeof options.labelEl === 'string'
            ? document.querySelector(options.labelEl)
            : options.labelEl;

        if (!amountInput || !currencySelect) return null;

        function currentCode() {
            return normalize(currencySelect.value || options.defaultCurrency || DEFAULT_CURRENCY);
        }

        function refresh() {
            var code = currentCode();
            var meta = getCurrency(code);
            var amount = toNumber(amountInput.value);

            if (symbolEl) symbolEl.textContent = meta.symbol;
            if (labelEl) {
                labelEl.textContent = 'Target Monthly Spend (' + meta.symbol + ')';
            }
            if (previewEl) {
                if (!amountInput.value || !isFinite(parseFloat(amountInput.value))) {
                    previewEl.textContent = 'Preview: ' + meta.symbol + '0.00';
                    previewEl.setAttribute('data-empty', 'true');
                } else {
                    previewEl.textContent = 'Preview: ' + formatMoney(amount, code);
                    previewEl.setAttribute('data-empty', 'false');
                }
            }
            amountInput.setAttribute('aria-label', 'Budget amount in ' + meta.name);
            currencySelect.setAttribute('aria-label', 'Budget currency');
        }

        currencySelect.addEventListener('change', refresh);
        amountInput.addEventListener('input', refresh);
        refresh();

        return {
            refresh: refresh,
            getCurrency: currentCode,
            getAmount: function () { return toNumber(amountInput.value); },
            formatCurrent: function () {
                return formatMoney(toNumber(amountInput.value), currentCode());
            }
        };
    }

    global.CampaignCurrency = {
        CURRENCIES: CURRENCIES,
        DEFAULT_CURRENCY: DEFAULT_CURRENCY,
        SELECTABLE: SELECTABLE,
        normalize: normalize,
        getCurrency: getCurrency,
        getSymbol: function (code) { return getCurrency(code).symbol; },
        formatNumber: formatNumber,
        formatMoney: formatMoney,
        selectableCurrencies: selectableCurrencies,
        bindBudgetField: bindBudgetField
    };
})(typeof window !== 'undefined' ? window : this);
