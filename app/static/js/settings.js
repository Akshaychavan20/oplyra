/**
 * Oplyra — Settings hub (navigation, preferences, theme sync)
 */
(function () {
    'use strict';

    var SECTION_TITLES = {
        profile: { title: 'Profile', desc: 'Manage your personal information and account identity.' },
        security: { title: 'Account & Security', desc: 'Password, sessions, and authentication settings.' },
        appearance: { title: 'Appearance', desc: 'Customize theme, accent colors, and display preferences.' },
        ai: { title: 'AI Preferences', desc: 'Configure AI provider keys and generation defaults.' },
        notifications: { title: 'Notifications', desc: 'Control how and when you receive alerts.' },
        workspace: { title: 'Workspace', desc: 'Usage limits and workspace configuration.' },
        locale: { title: 'Language & Region', desc: 'Language, timezone, and regional preferences.' },
        integrations: { title: 'Integrations', desc: 'Connect external apps and data sources.' },
        billing: { title: 'Billing & Subscription', desc: 'Manage your plan and payment details.' },
        privacy: { title: 'Privacy & Data', desc: 'Data controls and account deletion.' },
        advanced: { title: 'Advanced', desc: 'Developer and power-user settings.' }
    };

    var NOTIF_KEYS = [
        'settings-notif-email',
        'settings-notif-browser',
        'settings-notif-ai',
        'settings-notif-tasks',
        'settings-notif-reports',
        'settings-notif-updates'
    ];

    function getEl(id) {
        return document.getElementById(id);
    }

    function activateSection(sectionId) {
        document.querySelectorAll('.settings-section').forEach(function (el) {
            el.classList.toggle('active', el.id === 'settings-section-' + sectionId);
        });
        document.querySelectorAll('.settings-nav-item').forEach(function (btn) {
            var isActive = btn.getAttribute('data-settings-section') === sectionId;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-current', isActive ? 'page' : 'false');
        });
        var meta = SECTION_TITLES[sectionId] || SECTION_TITLES.profile;
        var titleEl = getEl('settings-section-heading');
        var descEl = getEl('settings-section-description');
        if (titleEl) titleEl.textContent = meta.title;
        if (descEl) descEl.textContent = meta.desc;
    }

    window.activateSettingsSection = activateSection;

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.documentElement;
        var modeSelect = getEl('settings-theme-mode');
        var tierSelect = getEl('settings-account-tier');
        var colorBtns = document.querySelectorAll('.accent-color-btn');
        var themeCards = document.querySelectorAll('.settings-theme-card');
        var accentOptions = document.querySelectorAll('.settings-accent-option');
        var saveBtn = getEl('settings-save-btn');
        var resetBtn = getEl('settings-reset-btn');
        var usernameInput = getEl('settings-username');
        var emailInput = getEl('settings-email');
        var selectedAccent = 'indigo';

        // Purge any legacy browser-stored provider keys (Phase 1 security)
        try { localStorage.removeItem('oplyra-user-gemini-key'); } catch (e) { /* ignore */ }

        function syncThemeCards(themeValue) {
            themeCards.forEach(function (card) {
                card.classList.toggle('active', card.getAttribute('data-theme') === themeValue);
                card.setAttribute('aria-checked', card.getAttribute('data-theme') === themeValue ? 'true' : 'false');
            });
        }

        function syncAccentOptions(accentValue) {
            accentOptions.forEach(function (opt) {
                var palette = opt.getAttribute('data-palette');
                opt.classList.toggle('active', palette === accentValue);
            });
            colorBtns.forEach(function (btn) {
                btn.classList.toggle('active', btn.getAttribute('data-palette') === accentValue);
            });
        }

        function loadNotificationPrefs() {
            NOTIF_KEYS.forEach(function (id) {
                var el = getEl(id);
                if (!el) return;
                var stored = localStorage.getItem('oplyra-' + id);
                if (stored !== null) {
                    el.checked = stored === 'true';
                }
            });
        }

        function saveNotificationPrefs() {
            NOTIF_KEYS.forEach(function (id) {
                var el = getEl(id);
                if (el) localStorage.setItem('oplyra-' + id, el.checked ? 'true' : 'false');
            });
        }

        function applySettings() {
            var savedAccent = localStorage.getItem('theme-palette') || 'indigo';
            var savedTheme = localStorage.getItem('theme-mode') || 'light';
            var savedTier = localStorage.getItem('user-tier') || 'pro';

            selectedAccent = savedAccent;

            if (modeSelect) {
                modeSelect.value = savedTheme;
                syncThemeCards(savedTheme);
            }
            if (tierSelect) tierSelect.value = savedTier;

            syncAccentOptions(savedAccent);

            if (window.OplyraTheme && window.OplyraTheme.applyAccent) {
                window.OplyraTheme.applyAccent(savedAccent);
            } else {
                var accentMap = { indigo: 'blue', purple: 'purple', sunset: 'orange', emerald: 'green' };
                root.setAttribute('data-accent', accentMap[savedAccent] || 'blue');
            }

            if (window.OplyraTheme) {
                window.OplyraTheme.apply(savedTheme, { skipSettingsSync: true });
            } else {
                var effective = savedTheme === 'system'
                    ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
                    : savedTheme;
                root.setAttribute('data-theme', effective);
            }

            var planBadgeText = savedTier === 'pro' ? 'Pro Member' : (savedTier === 'free' ? 'Free Creator' : 'Enterprise');
            var badge1 = getEl('user-role-badge');
            var badge2 = getEl('profile-card-plan');
            var badge3 = getEl('kpi-plan-label');
            var settingsPlanBadge = getEl('settings-profile-plan-badge');

            if (badge1) badge1.textContent = planBadgeText;
            if (settingsPlanBadge) {
                settingsPlanBadge.textContent = planBadgeText;
                settingsPlanBadge.className = 'settings-profile-badge';
                if (savedTier === 'free') {
                    settingsPlanBadge.style.background = 'hsl(var(--text-muted) / 0.15)';
                    settingsPlanBadge.style.color = 'hsl(var(--text-muted))';
                } else if (savedTier === 'enterprise') {
                    settingsPlanBadge.style.background = 'hsl(var(--secondary) / 0.15)';
                    settingsPlanBadge.style.color = 'hsl(var(--secondary))';
                } else {
                    settingsPlanBadge.style.background = '';
                    settingsPlanBadge.style.color = '';
                }
            }
            if (badge2) {
                badge2.textContent = planBadgeText.toUpperCase();
                if (savedTier === 'free') {
                    badge2.style.backgroundColor = 'hsl(var(--text-muted) / 0.15)';
                    badge2.style.color = 'hsl(var(--text-muted))';
                } else if (savedTier === 'enterprise') {
                    badge2.style.backgroundColor = 'hsl(var(--secondary) / 0.15)';
                    badge2.style.color = 'hsl(var(--secondary))';
                } else {
                    badge2.style.backgroundColor = 'hsl(var(--primary) / 0.15)';
                    badge2.style.color = 'hsl(var(--primary))';
                }
            }
            if (badge3) {
                badge3.textContent = planBadgeText + ' Account';
                badge3.className = savedTier === 'free' ? 'stat-number text-secondary'
                    : savedTier === 'enterprise' ? 'stat-number text-teal'
                    : 'stat-number text-success';
            }

            loadNotificationPrefs();
        }

        /* Settings navigation */
        document.querySelectorAll('.settings-nav-item').forEach(function (btn) {
            btn.addEventListener('click', function () {
                activateSection(btn.getAttribute('data-settings-section'));
            });
        });

        /* Theme cards */
        themeCards.forEach(function (card) {
            card.addEventListener('click', function () {
                var theme = card.getAttribute('data-theme');
                if (modeSelect) modeSelect.value = theme;
                syncThemeCards(theme);
                if (window.OplyraTheme) window.OplyraTheme.apply(theme);
            });
            card.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    card.click();
                }
            });
        });

        /* Accent selection */
        function selectAccent(palette, btnEl) {
            selectedAccent = palette;
            syncAccentOptions(palette);
            if (window.OplyraTheme && window.OplyraTheme.applyAccent) {
                window.OplyraTheme.applyAccent(palette);
            }
        }

        accentOptions.forEach(function (opt) {
            opt.addEventListener('click', function () {
                selectAccent(opt.getAttribute('data-palette'));
            });
        });

        colorBtns.forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.stopPropagation();
                selectAccent(btn.getAttribute('data-palette'), btn);
            });
        });

        if (saveBtn) {
            saveBtn.addEventListener('click', function () {
                localStorage.setItem('theme-palette', selectedAccent);
                if (window.OplyraTheme && window.OplyraTheme.applyAccent) {
                    window.OplyraTheme.applyAccent(selectedAccent);
                }
                if (modeSelect) {
                    localStorage.setItem('theme-mode', modeSelect.value);
                    if (window.OplyraTheme) window.OplyraTheme.apply(modeSelect.value);
                }
                if (tierSelect) localStorage.setItem('user-tier', tierSelect.value);

                saveNotificationPrefs();

                var profileName = getEl('profile-card-username');
                var settingsName = getEl('settings-profile-name');
                if (profileName && usernameInput) profileName.textContent = usernameInput.value;
                if (settingsName && usernameInput) settingsName.textContent = usernameInput.value;

                applySettings();
                if (window.showToast) window.showToast('Settings saved successfully.', 'success');
                else alert('Settings saved successfully.');
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', function () {
                localStorage.removeItem('theme-palette');
                localStorage.removeItem('theme-mode');
                localStorage.removeItem('user-tier');
                NOTIF_KEYS.forEach(function (id) { localStorage.removeItem('oplyra-' + id); });
                if (window.OplyraTheme) window.OplyraTheme.apply('light');
                applySettings();
                if (window.showToast) window.showToast('Preferences reset to defaults.', 'info');
                else alert('Preferences reset to defaults.');
            });
        }

        /* Multi-provider AI preferences (server-backed) */
        (function initAiPreferences() {
            var creativity = getEl('ai-creativity');
            var creativityVal = getEl('ai-creativity-value');
            var savePrefsBtn = getEl('btn-save-ai-prefs');
            var feedback = getEl('ai-prefs-feedback');
            var csrf = document.querySelector('meta[name="csrf-token"]');
            var csrfToken = csrf ? csrf.getAttribute('content') : '';

            if (creativity && creativityVal) {
                creativity.addEventListener('input', function () {
                    creativityVal.textContent = creativity.value;
                });
            }

            function applyPrefs(settings) {
                if (!settings) return;
                var radios = document.querySelectorAll('input[name="ai-preferred-provider"]');
                radios.forEach(function (r) {
                    r.checked = r.value === (settings.preferred_provider || 'auto');
                });
                if (creativity && settings.creativity != null) {
                    creativity.value = settings.creativity;
                    if (creativityVal) creativityVal.textContent = settings.creativity;
                }
                var lengthEl = getEl('ai-response-length');
                if (lengthEl && settings.response_length) lengthEl.value = settings.response_length;
                var langEl = getEl('ai-language');
                if (langEl && settings.language) langEl.value = settings.language;
                var streamEl = getEl('ai-streaming-enabled');
                if (streamEl && settings.streaming_enabled != null) streamEl.checked = !!settings.streaming_enabled;
            }

            fetch('/api/ai/settings', { headers: { 'Accept': 'application/json' } })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (data && data.success) applyPrefs(data.settings);
                })
                .catch(function () { /* panel still usable offline */ });

            if (savePrefsBtn) {
                savePrefsBtn.addEventListener('click', function () {
                    var selected = document.querySelector('input[name="ai-preferred-provider"]:checked');
                    var payload = {
                        preferred_provider: selected ? selected.value : 'auto',
                        creativity: creativity ? parseFloat(creativity.value) : 0.7,
                        response_length: (getEl('ai-response-length') || {}).value || 'medium',
                        language: (getEl('ai-language') || {}).value || 'en',
                        streaming_enabled: !!(getEl('ai-streaming-enabled') || {}).checked
                    };
                    savePrefsBtn.disabled = true;
                    if (feedback) feedback.textContent = 'Saving…';
                    fetch('/api/ai/settings', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRF-Token': csrfToken
                        },
                        body: JSON.stringify(payload)
                    })
                        .then(function (r) { return r.json(); })
                        .then(function (data) {
                            if (feedback) feedback.textContent = data.success ? 'Saved.' : (data.error || 'Failed.');
                            if (data.success && window.showToast) window.showToast('AI preferences saved.', 'success');
                        })
                        .catch(function () {
                            if (feedback) feedback.textContent = 'Could not save preferences.';
                        })
                        .finally(function () { savePrefsBtn.disabled = false; });
                });
            }
        })();

        /* Deep-link: #settings or #api-keys with section */
        var hash = window.location.hash || '';
        if (hash.indexOf('#api-keys') === 0 || hash.indexOf('#settings') === 0) {
            var section = 'profile';
            if (hash.indexOf('#api-keys') === 0) section = 'ai';
            else if (hash.indexOf('-') > 0) {
                var parts = hash.split('-');
                if (parts.length > 1 && SECTION_TITLES[parts[parts.length - 1]]) {
                    section = parts[parts.length - 1];
                }
            }
            activateSection(section);
        }

        applySettings();
        window.applySettings = applySettings;
    });

    /* Billing handlers — used by Stripe checkout modal */
    window.setCheckoutTier = function (tier) {
        window.checkoutTier = tier;
        var priceLabel = document.getElementById('stripe-price-indicator');
        if (priceLabel) {
            priceLabel.textContent = tier === 'enterprise' ? '$99.00 / month' : '$19.00 / month';
        }
    };

    window.handleStripeMockCheckout = function (e) {
        e.preventDefault();
        var submitBtn = document.getElementById('stripe-checkout-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Authorizing Stripe...';
        }
        setTimeout(function () {
            var tier = window.checkoutTier || 'pro';
            localStorage.setItem('user-tier', tier);
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Upgrade Plan Now';
            }
            var modalEl = document.getElementById('stripeCheckoutModal');
            var modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
            if (window.applySettings) window.applySettings();
            if (window.showToast) window.showToast('Subscription updated successfully.', 'success');
            else alert('Payment authorized! You are now on the ' + (tier === 'enterprise' ? 'Enterprise' : 'Pro') + ' plan.');
        }, 1500);
    };

    window.upgradeSubscriptionTier = function (tier) {
        if (tier === 'free') {
            localStorage.setItem('user-tier', 'free');
            if (window.applySettings) window.applySettings();
            if (window.showToast) window.showToast('Downgraded to Free plan.', 'info');
            else alert('Subscription changed to Free Creator Plan.');
        }
    };

    window.addEventListener('hashchange', function () {
        var hash = window.location.hash || '';
        if (hash === '#api-keys') activateSection('ai');
    });
})();
