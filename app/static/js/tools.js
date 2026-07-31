/**
 * Tool Center UI — installed tools, marketplace, history, execute.
 */
(function () {
    'use strict';

    function csrf() {
        var el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    }
    function $(id) { return document.getElementById(id); }

    function api(path, options) {
        options = options || {};
        var headers = Object.assign({ Accept: 'application/json', 'X-CSRF-Token': csrf() }, options.headers || {});
        if (options.json) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.json);
            delete options.json;
        }
        return fetch('/api/tools' + path, Object.assign({}, options, { headers: headers }))
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) throw new Error((data && data.error) || (data && data.result && data.result.error) || 'Request failed');
                    return data;
                });
            });
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    }

    var state = { tools: [], categories: [], marketplace: [], history: [] };

    function showTab(tab) {
        document.querySelectorAll('.tools-tab-btn').forEach(function (b) {
            b.classList.toggle('active', b.getAttribute('data-tab') === tab);
        });
        ['installed', 'marketplace', 'history'].forEach(function (t) {
            var el = $('tools-panel-' + t);
            if (el) el.classList.toggle('d-none', t !== tab);
        });
    }

    function renderCategories() {
        var sel = $('tools-category-filter');
        if (!sel) return;
        sel.innerHTML = '<option value="">All categories</option>' +
            state.categories.map(function (c) {
                return '<option value="' + c.key + '">' + escapeHtml(c.name) + '</option>';
            }).join('');
    }

    function filteredTools() {
        var q = (($('tools-search') || {}).value || '').toLowerCase();
        var cat = ($('tools-category-filter') || {}).value || '';
        return state.tools.filter(function (t) {
            if (cat && t.category_key !== cat) return false;
            if (!q) return true;
            return (t.name || '').toLowerCase().indexOf(q) !== -1
                || (t.description || '').toLowerCase().indexOf(q) !== -1
                || (t.key || '').toLowerCase().indexOf(q) !== -1;
        });
    }

    function renderTools() {
        var grid = $('tools-grid');
        var runSel = $('tools-run-select');
        if (!grid) return;
        var tools = filteredTools();
        grid.innerHTML = tools.map(function (t) {
            return '<div class="tools-card">' +
                '<div class="tools-card-icon"><i class="bi ' + escapeHtml(t.icon || 'bi-wrench') + '"></i></div>' +
                '<div class="tools-card-body">' +
                '<div class="tools-card-title">' + escapeHtml(t.name) +
                (t.is_enabled ? '' : ' <span class="badge bg-secondary">off</span>') +
                '</div>' +
                '<div class="tools-card-desc">' + escapeHtml(t.description || '') + '</div>' +
                '<div class="tools-card-meta">' + escapeHtml(t.category_key || '') +
                ' · v' + escapeHtml(t.version || '1.0.0') +
                (t.is_builtin ? ' · builtin' : ' · marketplace') +
                '</div></div></div>';
        }).join('') || '<div class="text-secondary small">No tools match.</div>';

        if (runSel) {
            runSel.innerHTML = state.tools.filter(function (t) { return t.is_enabled; }).map(function (t) {
                return '<option value="' + t.key + '">' + escapeHtml(t.name) + '</option>';
            }).join('');
        }
    }

    function renderMarketplace() {
        var el = $('tools-marketplace');
        if (!el) return;
        el.innerHTML = state.marketplace.map(function (m) {
            return '<div class="tools-card">' +
                '<div class="tools-card-icon"><i class="bi bi-plugin"></i></div>' +
                '<div class="tools-card-body">' +
                '<div class="tools-card-title">' + escapeHtml(m.name) +
                (m.installed ? ' <span class="badge bg-success bg-opacity-25 text-success">installed</span>' : '') +
                '</div>' +
                '<div class="tools-card-desc">' + escapeHtml(m.description || '') + '</div>' +
                '<div class="tools-card-meta">' + escapeHtml(m.publisher || '') +
                ' · ' + escapeHtml(m.availability || 'coming_soon') + '</div>' +
                (m.installed ? '' :
                    '<button type="button" class="btn btn-primary-custom btn-sm mt-2 tools-install-btn" data-key="' +
                    m.key + '">Install</button>') +
                '</div></div>';
        }).join('');

        el.querySelectorAll('.tools-install-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                api('/install', { method: 'POST', json: { key: btn.getAttribute('data-key') } })
                    .then(function () { loadAll(); alert('Installed as placeholder (OAuth pending).'); })
                    .catch(function (e) { alert(e.message); });
            });
        });
    }

    function renderHistory() {
        var el = $('tools-history');
        if (!el) return;
        if (!state.history.length) {
            el.innerHTML = '<div class="text-secondary small">No tool runs yet.</div>';
            return;
        }
        el.innerHTML = state.history.map(function (r) {
            return '<div class="tools-hist-item">' +
                '<div class="d-flex justify-content-between">' +
                '<strong class="text-white small">' + escapeHtml(r.tool_key) + '</strong>' +
                '<span class="badge bg-secondary bg-opacity-25">' + escapeHtml(r.status) + '</span>' +
                '</div>' +
                '<div class="text-secondary small mt-1">' +
                (r.duration_ms || 0) + 'ms · retries ' + (r.retry_count || 0) +
                (r.agent_key ? ' · agent ' + escapeHtml(r.agent_key) : '') +
                '</div></div>';
        }).join('');
    }

    function runTool() {
        var key = ($('tools-run-select') || {}).value;
        var arg = (($('tools-run-arg') || {}).value || '').trim();
        var useAgent = ($('tools-use-agent') || {}).checked;
        var err = $('tools-run-error');
        var out = $('tools-run-output');
        if (err) { err.classList.add('d-none'); err.textContent = ''; }
        if (!key) return;

        var body;
        if (useAgent) {
            body = {
                use_agent: true,
                goal: arg || 'Research competitors using available tools',
                agent_key: 'research',
                tool_keys: [key, 'knowledge_search'],
            };
        } else {
            var arguments = {};
            if (key === 'calculator') arguments.expression = arg || '2+2';
            else if (key === 'web_browser' || key === 'http_request') arguments.url = arg || 'https://example.com';
            else if (key === 'file_reader') arguments.path = arg || '/demo.txt';
            else if (key === 'datetime') arguments.format = arg || '%Y-%m-%d %H:%M:%S';
            else arguments.query = arg || 'oplyra marketing';
            body = { tool_key: key, arguments: arguments };
        }

        if (out) out.textContent = 'Executing…';
        api('/run', { method: 'POST', json: body })
            .then(function (data) {
                if (out) out.textContent = JSON.stringify(data, null, 2);
                loadHistory();
            })
            .catch(function (e) {
                if (err) { err.textContent = e.message; err.classList.remove('d-none'); }
                if (out) out.textContent = 'Failed: ' + e.message;
            });
    }

    function loadHistory() {
        return api('/history?limit=40').then(function (data) {
            state.history = data.runs || [];
            renderHistory();
        });
    }

    function loadAll() {
        return Promise.all([
            api('/'),
            api('/categories'),
            api('/marketplace'),
            loadHistory(),
        ]).then(function (results) {
            state.tools = results[0].tools || [];
            state.categories = results[1].categories || [];
            state.marketplace = results[2].items || [];
            renderCategories();
            renderTools();
            renderMarketplace();
        });
    }

    function init() {
        if (!$('panel-tools')) return;
        document.querySelectorAll('.tools-tab-btn').forEach(function (btn) {
            btn.addEventListener('click', function () { showTab(btn.getAttribute('data-tab')); });
        });
        if ($('tools-search')) $('tools-search').addEventListener('input', renderTools);
        if ($('tools-category-filter')) $('tools-category-filter').addEventListener('change', renderTools);
        if ($('tools-run-btn')) $('tools-run-btn').addEventListener('click', runTool);
        loadAll().catch(function (e) {
            var err = $('tools-run-error');
            if (err) { err.textContent = e.message; err.classList.remove('d-none'); }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
