/**
 * Oplyra client-side XSS helpers — escape + sanitize HTML before innerHTML.
 */
(function (global) {
    'use strict';

    function escapeHtml(value) {
        if (value == null) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function sanitizeHtml(html) {
        if (!html) return '';
        var cleaned = String(html);
        cleaned = cleaned.replace(/<\s*(script|iframe|object|embed|link|meta|base)[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, '');
        cleaned = cleaned.replace(/<\s*(script|iframe|object|embed|link|meta|base)[^>]*>/gi, '');
        cleaned = cleaned.replace(/\s+on[a-z]+\s*=\s*(['"])[\s\S]*?\1/gi, '');
        cleaned = cleaned.replace(/\s+on[a-z]+\s*=\s*[^\s>]+/gi, '');
        cleaned = cleaned.replace(/\b(href|src)\s*=\s*(['"])\s*javascript:[^'"]*\2/gi, '');
        return cleaned;
    }

    function safeMarkedParse(markdown) {
        var raw = markdown == null ? '' : String(markdown);
        if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
            return sanitizeHtml(marked.parse(raw));
        }
        return escapeHtml(raw).replace(/\n/g, '<br>');
    }

    global.OplyraSecurity = {
        escapeHtml: escapeHtml,
        sanitizeHtml: sanitizeHtml,
        safeMarkedParse: safeMarkedParse
    };
})(window);
