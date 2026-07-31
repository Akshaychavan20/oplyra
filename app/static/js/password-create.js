/**
 * Password creation component — real-time rules, strength, confirm match.
 * Init: PasswordCreate.init({ form, password, confirm, submit, ... })
 */
(function (global) {
    'use strict';

    var SPECIAL_RE = /[!@#$%^&*()_+\-=[\]{}|;:'",.<>?/]/;
    var RULES = [
        { id: 'length', label: 'At least 8 characters', test: function (v) { return v.length >= 8; } },
        { id: 'uppercase', label: 'One uppercase letter', test: function (v) { return /[A-Z]/.test(v); } },
        { id: 'lowercase', label: 'One lowercase letter', test: function (v) { return /[a-z]/.test(v); } },
        { id: 'number', label: 'One number', test: function (v) { return /[0-9]/.test(v); } },
        { id: 'special', label: 'One special character', test: function (v) { return SPECIAL_RE.test(v); } }
    ];

    function stripEdgeSpaces(value) {
        return String(value || '').replace(/^\s+|\s+$/g, '');
    }

    function stripLeadingSpaces(value) {
        return String(value || '').replace(/^\s+/, '');
    }

    function evaluateRules(password) {
        var results = {};
        var allMet = true;
        for (var i = 0; i < RULES.length; i++) {
            var met = RULES[i].test(password);
            results[RULES[i].id] = met;
            if (!met) allMet = false;
        }
        return { results: results, allMet: allMet };
    }

    /**
     * Strength from length, variety, and complexity (0–4 bands).
     */
    function computeStrength(password) {
        if (!password) {
            return { level: 'weak', label: 'Weak', percent: 0, score: 0 };
        }

        var score = 0;
        var len = password.length;
        var hasUpper = /[A-Z]/.test(password);
        var hasLower = /[a-z]/.test(password);
        var hasDigit = /[0-9]/.test(password);
        var hasSpecial = SPECIAL_RE.test(password);
        var variety = (hasUpper ? 1 : 0) + (hasLower ? 1 : 0) + (hasDigit ? 1 : 0) + (hasSpecial ? 1 : 0);

        if (len >= 8) score += 1;
        if (len >= 12) score += 1;
        if (len >= 16) score += 1;
        if (variety >= 3) score += 1;
        if (variety === 4) score += 1;
        if (hasSpecial && hasDigit && hasUpper && hasLower && len >= 10) score += 1;

        // Penalize very short / low variety
        if (len < 8) score = Math.min(score, 1);
        if (variety < 2) score = Math.min(score, 1);

        var level;
        var label;
        var percent;

        if (score >= 5) {
            level = 'very-strong';
            label = 'Very Strong';
            percent = 100;
        } else if (score >= 4) {
            level = 'strong';
            label = 'Strong';
            percent = 75;
        } else if (score >= 2) {
            level = 'medium';
            label = 'Medium';
            percent = 50;
        } else {
            level = 'weak';
            label = 'Weak';
            percent = 25;
        }

        return { level: level, label: label, percent: percent, score: score };
    }

    function setToggleState(btn, input, visible) {
        var icon = btn.querySelector('i');
        input.type = visible ? 'text' : 'password';
        btn.setAttribute('aria-pressed', visible ? 'true' : 'false');
        btn.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
        if (icon) {
            icon.className = visible ? 'bi bi-eye-slash' : 'bi bi-eye';
        }
    }

    function wireToggle(btn, input) {
        if (!btn || !input) return;
        btn.addEventListener('click', function () {
            setToggleState(btn, input, input.type === 'password');
        });
        // Keyboard: Enter/Space already activate buttons; ensure focusable
        if (!btn.hasAttribute('tabindex')) {
            btn.setAttribute('tabindex', '0');
        }
    }

    function updateRequirementUI(root, results, touched) {
        RULES.forEach(function (rule) {
            var item = root.querySelector('[data-pwd-req="' + rule.id + '"]');
            if (!item) return;
            var met = !!results[rule.id];
            var icon = item.querySelector('.pwd-req__icon i');
            var text = item.querySelector('[data-pwd-req-label]');
            item.classList.toggle('is-met', met);
            item.classList.toggle('is-unmet', !met);
            item.classList.toggle('is-touched', !!touched);
            item.setAttribute(
                'aria-label',
                rule.label + (met ? ': satisfied' : ': not satisfied')
            );
            if (icon) {
                icon.className = met ? 'bi bi-check' : 'bi bi-circle';
            }
            if (text) {
                text.setAttribute('aria-hidden', 'true');
            }
        });
    }

    function updateStrengthUI(root, strength, hasValue) {
        var panel = root.querySelector('[data-pwd-strength]');
        var track = root.querySelector('[data-pwd-strength-track]');
        var bar = root.querySelector('[data-pwd-strength-bar]');
        var label = root.querySelector('[data-pwd-strength-label]');
        if (!panel || !bar || !label) return;

        panel.classList.toggle('is-visible', hasValue);
        panel.setAttribute('aria-hidden', hasValue ? 'false' : 'true');

        label.textContent = strength.label;
        label.setAttribute('data-level', strength.level);
        bar.style.width = strength.percent + '%';
        bar.setAttribute('data-level', strength.level);
        if (track) {
            track.setAttribute('aria-valuenow', String(strength.percent));
            track.setAttribute('aria-valuetext', strength.label);
        }
    }

    function updateMatchUI(root, password, confirm, confirmTouched) {
        var indicator = root.querySelector('[data-pwd-match]');
        var confirmInput = root.querySelector('[data-pwd-confirm]');
        if (!indicator || !confirmInput) return { matches: false, empty: true };

        if (!confirm) {
            indicator.classList.remove('is-visible', 'is-match', 'is-mismatch');
            indicator.textContent = '';
            confirmInput.classList.remove('invalid-state', 'valid-state');
            confirmInput.setAttribute('aria-invalid', 'false');
            return { matches: false, empty: true };
        }

        var matches = password === confirm;
        indicator.classList.add('is-visible');
        indicator.classList.toggle('is-match', matches);
        indicator.classList.toggle('is-mismatch', !matches);

        if (matches) {
            indicator.innerHTML = '<i class="bi bi-check-circle-fill" aria-hidden="true"></i><span>Passwords match</span>';
            confirmInput.classList.remove('invalid-state');
            confirmInput.classList.add('valid-state');
            confirmInput.setAttribute('aria-invalid', 'false');
        } else {
            indicator.innerHTML = '<i class="bi bi-x-circle-fill" aria-hidden="true"></i><span>Passwords do not match</span>';
            if (confirmTouched) {
                confirmInput.classList.add('invalid-state');
                confirmInput.classList.remove('valid-state');
            }
            confirmInput.setAttribute('aria-invalid', 'true');
        }

        return { matches: matches, empty: false };
    }

    function init(options) {
        options = options || {};
        var root = typeof options.root === 'string'
            ? document.querySelector(options.root)
            : (options.root || document.querySelector('[data-pwd-create]'));
        if (!root) return null;

        var form = options.form
            || (root.closest('form'))
            || document.querySelector(options.formSelector || '#register-form, #reset-form');
        var passwordInput = root.querySelector('[data-pwd-input]') || document.getElementById(options.passwordId || 'password');
        var confirmInput = root.querySelector('[data-pwd-confirm]') || document.getElementById(options.confirmId || 'confirm_password');
        var submitBtn = options.submit
            || (form && form.querySelector('[type="submit"]'))
            || document.getElementById(options.submitId || 'submit-btn');
        var feedback = root.querySelector('[data-pwd-feedback]');

        if (!passwordInput || !confirmInput) return null;

        var togglePw = root.querySelector('[data-pwd-toggle="password"]');
        var toggleConfirm = root.querySelector('[data-pwd-toggle="confirm"]');
        wireToggle(togglePw, passwordInput);
        wireToggle(toggleConfirm, confirmInput);

        var state = {
            touched: false,
            confirmTouched: false,
            allMet: false,
            matches: false
        };

        function sanitizeInput(input, trimEnds) {
            var start = input.selectionStart;
            var end = input.selectionEnd;
            var before = input.value;
            var after = trimEnds ? stripEdgeSpaces(before) : stripLeadingSpaces(before);
            if (before === after) return after;
            input.value = after;
            // Preserve caret when only leading spaces were removed
            if (!trimEnds && typeof start === 'number') {
                var removed = before.length - after.length;
                var nextStart = Math.max(0, start - removed);
                var nextEnd = Math.max(0, end - removed);
                try {
                    input.setSelectionRange(nextStart, nextEnd);
                } catch (e) { /* ignore */ }
            }
            return after;
        }

        function refresh() {
            var password = passwordInput.value;
            var confirm = confirmInput.value;
            var evaluated = evaluateRules(password);
            var strength = computeStrength(password);

            state.allMet = evaluated.allMet;
            state.touched = state.touched || password.length > 0;

            updateRequirementUI(root, evaluated.results, state.touched);
            updateStrengthUI(root, strength, password.length > 0);

            var match = updateMatchUI(root, password, confirm, state.confirmTouched);
            state.matches = match.matches;

            var valid = state.allMet && state.matches && password.length > 0;

            if (feedback) {
                if (state.allMet && password.length > 0) {
                    feedback.classList.remove('show');
                    passwordInput.classList.remove('invalid-state');
                    passwordInput.classList.add('valid-state');
                    passwordInput.setAttribute('aria-invalid', 'false');
                } else if (!password.length) {
                    feedback.classList.remove('show');
                    passwordInput.classList.remove('invalid-state', 'valid-state');
                    passwordInput.setAttribute('aria-invalid', 'false');
                } else {
                    // Keep border neutral while typing; checklist is the live cue
                    passwordInput.classList.remove('valid-state');
                    passwordInput.setAttribute('aria-invalid', 'false');
                    if (!options.showFeedbackWhileTyping) {
                        feedback.classList.remove('show');
                        passwordInput.classList.remove('invalid-state');
                    }
                }
            }

            if (submitBtn) {
                submitBtn.classList.add('pwd-submit-gated');
                // Gate only when this component owns submit; other fields may still be required
                if (options.gateSubmit !== false) {
                    var extraOk = typeof options.canSubmit === 'function' ? !!options.canSubmit() : true;
                    submitBtn.disabled = !(valid && extraOk);
                    submitBtn.setAttribute('aria-disabled', submitBtn.disabled ? 'true' : 'false');
                }
            }

            root.dispatchEvent(new CustomEvent('pwd:change', {
                detail: {
                    allMet: state.allMet,
                    matches: state.matches,
                    valid: valid,
                    strength: strength,
                    password: password
                },
                bubbles: true
            }));

            return valid;
        }

        passwordInput.addEventListener('input', function () {
            sanitizeInput(passwordInput, false);
            refresh();
        });

        passwordInput.addEventListener('blur', function () {
            sanitizeInput(passwordInput, true);
            state.touched = true;
            refresh();
            if (feedback && passwordInput.value && !state.allMet) {
                feedback.textContent = 'Please meet all password requirements.';
                feedback.classList.add('show');
                passwordInput.classList.add('invalid-state');
                passwordInput.setAttribute('aria-invalid', 'true');
            }
        });

        passwordInput.addEventListener('paste', function () {
            setTimeout(function () {
                sanitizeInput(passwordInput, true);
                refresh();
            }, 0);
        });

        confirmInput.addEventListener('input', function () {
            sanitizeInput(confirmInput, false);
            state.confirmTouched = true;
            refresh();
        });

        confirmInput.addEventListener('blur', function () {
            sanitizeInput(confirmInput, true);
            state.confirmTouched = true;
            refresh();
        });

        confirmInput.addEventListener('paste', function () {
            setTimeout(function () {
                sanitizeInput(confirmInput, true);
                refresh();
            }, 0);
        });

        if (form) {
            form.addEventListener('submit', function (e) {
                sanitizeInput(passwordInput, true);
                sanitizeInput(confirmInput, true);
                state.touched = true;
                state.confirmTouched = true;
                var valid = refresh();
                if (!valid) {
                    e.preventDefault();
                    e.stopPropagation();
                    if (feedback && !state.allMet) {
                        feedback.classList.add('show');
                        passwordInput.focus();
                    } else if (!state.matches) {
                        confirmInput.focus();
                    }
                }
            });
        }

        // Initial state: keep submit disabled until valid
        refresh();

        return {
            refresh: refresh,
            isValid: function () {
                return state.allMet && state.matches && passwordInput.value.length > 0;
            },
            evaluate: function (value) {
                return evaluateRules(value || passwordInput.value);
            },
            strength: function (value) {
                return computeStrength(value || passwordInput.value);
            }
        };
    }

    global.PasswordCreate = {
        init: init,
        rules: RULES,
        evaluateRules: evaluateRules,
        computeStrength: computeStrength,
        SPECIAL_RE: SPECIAL_RE
    };
})(typeof window !== 'undefined' ? window : this);
