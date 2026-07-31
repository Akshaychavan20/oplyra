/**
 * Oplyra — Light / Dark theme controller
 * Persists preference in localStorage (`theme-mode`: light | dark | system)
 * Default when unset: light. Resolves effective theme onto <html data-theme="light|dark">
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'theme-mode';
    var DEFAULT_THEME = 'light';
    var ACCENT_STORAGE_KEY = 'theme-palette';
    var VALID = { light: true, dark: true, system: true };
    var ACCENT_MAP = {
        indigo: 'blue',
        blue: 'blue',
        purple: 'purple',
        sunset: 'orange',
        orange: 'orange',
        emerald: 'green',
        green: 'green'
    };

    function getSystemTheme() {
        try {
            return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
        } catch (e) {
            return 'dark';
        }
    }

    function getPreference() {
        var stored = localStorage.getItem(STORAGE_KEY);
        if (stored && VALID[stored]) return stored;
        return DEFAULT_THEME;
    }

    function resolveTheme(preference) {
        var pref = preference || getPreference();
        return pref === 'system' ? getSystemTheme() : pref;
    }

    function updateToggleUI(effective) {
        var btn = document.getElementById('theme-toggle-btn');
        if (!btn) return;
        var isLight = effective === 'light';
        btn.setAttribute('aria-label', isLight ? 'Switch to dark mode' : 'Switch to light mode');
        btn.setAttribute('aria-pressed', isLight ? 'true' : 'false');
        btn.setAttribute('title', isLight ? 'Switch to dark mode' : 'Switch to light mode');
        btn.classList.toggle('is-light', isLight);
        btn.classList.toggle('is-dark', !isLight);
    }

    function syncSettingsSelect(preference) {
        var select = document.getElementById('settings-theme-mode');
        if (select && select.value !== preference) {
            select.value = preference;
        }
    }

    function resolveAccent(palette) {
        var key = palette || localStorage.getItem(ACCENT_STORAGE_KEY) || 'indigo';
        return ACCENT_MAP[key] || 'blue';
    }

    function applyAccent(palette) {
        document.documentElement.setAttribute('data-accent', resolveAccent(palette));
        document.documentElement.style.removeProperty('--primary');
        document.documentElement.style.removeProperty('--secondary');
    }

    function clearLegacyInlineThemeVars() {
        // Older Settings UI wrote these inline; remove so CSS tokens win
        var props = ['--bg-dark', '--card-bg', '--text-primary', '--text-secondary', '--border-color', '--primary', '--secondary'];
        for (var i = 0; i < props.length; i++) {
            document.documentElement.style.removeProperty(props[i]);
        }
    }

    function readCssToken(name) {
        var val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return val ? 'hsl(' + val + ')' : null;
    }

    function getChartTheme() {
        var isLight = resolveTheme(getPreference()) === 'light';
        return {
            isLight: isLight,
            fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
            tick: readCssToken('--chart-tick') || (isLight ? 'hsl(224, 12%, 48%)' : 'hsl(215, 13%, 45%)'),
            legend: readCssToken('--chart-legend') || (isLight ? 'hsl(224, 20%, 32%)' : 'hsl(215, 15%, 72%)'),
            grid: readCssToken('--chart-grid') || (isLight ? 'hsla(224, 15%, 20%, 0.08)' : 'hsla(148, 163, 184, 0.08)'),
            tooltipBg: readCssToken('--chart-tooltip-bg') || (isLight ? 'hsla(0, 0%, 100%, 0.98)' : 'hsla(224, 25%, 4%, 0.92)'),
            tooltipTitle: readCssToken('--chart-tooltip-title') || (isLight ? 'hsl(224, 25%, 12%)' : 'hsl(0, 0%, 100%)'),
            tooltipBody: readCssToken('--chart-tooltip-body') || (isLight ? 'hsl(224, 20%, 32%)' : 'hsl(215, 20%, 84%)'),
            pointBorder: readCssToken('--chart-point-border') || (isLight ? 'hsl(210, 40%, 98%)' : 'hsl(224, 25%, 4%)')
        };
    }

    function applyTheme(preference, options) {
        var opts = options || {};
        var pref = preference && VALID[preference] ? preference : getPreference();
        var effective = resolveTheme(pref);

        clearLegacyInlineThemeVars();
        applyAccent();
        document.documentElement.setAttribute('data-theme', effective);
        document.documentElement.style.colorScheme = effective;

        if (!opts.skipPersist) {
            localStorage.setItem(STORAGE_KEY, pref);
        }

        updateToggleUI(effective);
        if (!opts.skipSettingsSync) {
            syncSettingsSelect(pref);
        }

        // Enable smooth transitions after first paint (avoids FOUC flicker)
        requestAnimationFrame(function () {
            document.documentElement.classList.add('theme-ready');
        });

        try {
            window.dispatchEvent(new CustomEvent('oplyra:themechange', {
                detail: { preference: pref, theme: effective }
            }));
        } catch (e) { /* older browsers */ }

        return effective;
    }

    function toggleTheme() {
        var current = resolveTheme(getPreference());
        var next = current === 'light' ? 'dark' : 'light';
        return applyTheme(next);
    }

    // Expose API early so inline scripts / settings can call it
    window.OplyraTheme = {
        getPreference: getPreference,
        resolve: resolveTheme,
        apply: applyTheme,
        toggle: toggleTheme,
        getSystemTheme: getSystemTheme,
        applyAccent: applyAccent,
        resolveAccent: resolveAccent,
        getChartTheme: getChartTheme,
        ACCENT_MAP: ACCENT_MAP,
        DEFAULT_THEME: DEFAULT_THEME
    };

    // Apply immediately if FOUC script already ran; re-sync UI when DOM ready
    applyTheme(getPreference(), { skipPersist: true });

    function onReady() {
        updateToggleUI(resolveTheme(getPreference()));
        syncSettingsSelect(getPreference());

        var btn = document.getElementById('theme-toggle-btn');
        if (btn) {
            btn.addEventListener('click', function () {
                toggleTheme();
            });
        }

        var select = document.getElementById('settings-theme-mode');
        if (select) {
            select.addEventListener('change', function () {
                applyTheme(select.value);
            });
        }

        // Follow OS changes when preference is "system"
        try {
            var mq = window.matchMedia('(prefers-color-scheme: light)');
            var onChange = function () {
                if (getPreference() === 'system') {
                    applyTheme('system', { skipPersist: true });
                }
            };
            if (mq.addEventListener) mq.addEventListener('change', onChange);
            else if (mq.addListener) mq.addListener(onChange);
        } catch (e) { /* ignore */ }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }
})();
