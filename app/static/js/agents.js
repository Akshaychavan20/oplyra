/**
 * AI Agents Framework UI — select agent / auto / workflow, show step progress.
 * Uses /api/agents/* (above AI Gateway). CSRF via meta tag.
 */
(function () {
    'use strict';

    function csrfToken() {
        var el = document.querySelector('meta[name="csrf-token"]');
        return el ? el.getAttribute('content') : '';
    }

    function $(id) {
        return document.getElementById(id);
    }

    var state = {
        mode: 'auto',
        agents: [],
        workflows: [],
        selectedAgent: null,
        running: false,
    };

    function api(path, options) {
        options = options || {};
        var headers = Object.assign({
            'Accept': 'application/json',
            'X-CSRF-Token': csrfToken(),
        }, options.headers || {});
        if (options.body && typeof options.body === 'object') {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.body);
        }
        return fetch('/api/agents' + path, Object.assign({}, options, { headers: headers }))
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) {
                        throw new Error((data && data.error) || ('Request failed (' + res.status + ')'));
                    }
                    return data;
                });
            });
    }

    function setMode(mode) {
        state.mode = mode;
        document.querySelectorAll('.agents-mode-btn').forEach(function (btn) {
            btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
        });
        var sel = $('agents-select-wrap');
        var wf = $('agents-workflow-wrap');
        if (sel) sel.classList.toggle('d-none', mode !== 'single');
        if (wf) wf.classList.toggle('d-none', mode !== 'workflow');
    }

    function renderAgentSelect() {
        var select = $('agents-select');
        if (!select) return;
        select.innerHTML = state.agents.map(function (a) {
            return '<option value="' + a.key + '">' + a.name + '</option>';
        }).join('');
        if (state.selectedAgent) select.value = state.selectedAgent;
    }

    function renderWorkflowSelect() {
        var select = $('agents-workflow-select');
        if (!select) return;
        select.innerHTML = state.workflows.map(function (w) {
            return '<option value="' + w.key + '">' + w.name + '</option>';
        }).join('');
    }

    function renderGrid() {
        var grid = $('agents-grid');
        if (!grid) return;
        grid.innerHTML = state.agents.map(function (a) {
            var resp = (a.responsibilities || []).slice(0, 3).join(' · ');
            return (
                '<button type="button" class="agents-card" data-agent-key="' + a.key + '">' +
                '<div class="agents-card-icon"><i class="bi ' + (a.icon || 'bi-robot') + '"></i></div>' +
                '<div class="agents-card-body">' +
                '<div class="agents-card-title">' + a.name + '</div>' +
                '<div class="agents-card-desc">' + (a.description || '') + '</div>' +
                (resp ? '<div class="agents-card-meta">' + resp + '</div>' : '') +
                '</div></button>'
            );
        }).join('');

        grid.querySelectorAll('.agents-card').forEach(function (card) {
            card.addEventListener('click', function () {
                state.selectedAgent = card.getAttribute('data-agent-key');
                setMode('single');
                renderAgentSelect();
                var sel = $('agents-select');
                if (sel) sel.value = state.selectedAgent;
            });
        });
    }

    function statusLabel(status) {
        if (status === 'completed') return '✓';
        if (status === 'running') return '…';
        if (status === 'failed') return '!';
        return '○';
    }

    function statusClass(status) {
        if (status === 'completed') return 'is-done';
        if (status === 'running') return 'is-running';
        if (status === 'failed') return 'is-failed';
        return 'is-waiting';
    }

    function renderProgress(run) {
        var el = $('agents-progress');
        if (!el) return;
        var steps = (run && run.steps) || [];
        if (!steps.length) {
            el.innerHTML = '<div class="agents-progress-empty text-secondary small">Waiting for steps…</div>';
            return;
        }
        var nameByKey = {};
        state.agents.forEach(function (a) { nameByKey[a.key] = a.name; });
        el.innerHTML = '<ol class="agents-stepper">' + steps.map(function (s) {
            var name = nameByKey[s.agent_key] || s.agent_key;
            var label = statusLabel(s.status);
            var cls = statusClass(s.status);
            var detail = s.status === 'running' ? 'Running…'
                : s.status === 'waiting' ? 'Waiting…'
                : s.status === 'completed' ? 'Done'
                : (s.error || 'Failed');
            return (
                '<li class="agents-step ' + cls + '">' +
                '<span class="agents-step-mark">' + label + '</span>' +
                '<span class="agents-step-name">' + name + '</span>' +
                '<span class="agents-step-status">' + detail + '</span>' +
                '</li>'
            );
        }).join('') + '</ol>';
    }

    function renderOutput(run) {
        var out = $('agents-output');
        var tok = $('agents-tokens');
        if (out) {
            out.textContent = (run && run.final_output) || (run && run.error_message) || 'No output.';
        }
        // Tokens / cost / latency stay admin-only — never surface here
        if (tok) {
            tok.textContent = '';
            tok.classList.add('d-none');
        }
        renderStudioMeta(run);
    }

    function renderStudioMeta(run) {
        var statusEl = $('studio-status');
        var modelEl = $('studio-model');
        var knowledgeEl = $('studio-knowledge');
        var toolsEl = $('studio-tools');
        var timeEl = $('studio-time');
        var qualityEl = $('studio-quality');

        if (!run) {
            if (statusEl) statusEl.textContent = 'Ready';
            return;
        }

        var status = run.status || 'unknown';
        if (statusEl) {
            statusEl.textContent = status === 'completed' ? 'Success'
                : status === 'failed' ? 'Failed'
                : status === 'running' ? 'Running'
                : status.charAt(0).toUpperCase() + status.slice(1);
        }

        var modelLabel = run.model_used || run.provider || (run.agent_key ? ('Specialist · ' + run.agent_key) : null)
            || (run.mode === 'auto' ? 'Smart workflow' : (run.mode || 'AI Studio'));
        if (modelEl) {
            modelEl.textContent = 'Model · ' + modelLabel;
            modelEl.classList.remove('d-none');
        }

        var steps = run.steps || [];
        var knowledgeUsed = !!(run.knowledge_used || run.rag_used || (run.context && run.context.knowledge));
        if (knowledgeEl) {
            knowledgeEl.textContent = knowledgeUsed ? 'Knowledge used' : 'Knowledge · none';
            knowledgeEl.classList.remove('d-none');
        }

        var toolNames = [];
        steps.forEach(function (s) {
            if (s.tool_key) toolNames.push(s.tool_key);
            if (s.tools_used && s.tools_used.length) {
                s.tools_used.forEach(function (t) { toolNames.push(t); });
            }
        });
        if (toolsEl) {
            toolsEl.textContent = toolNames.length
                ? ('Tools · ' + toolNames.slice(0, 3).join(', '))
                : 'Tools · none';
            toolsEl.classList.remove('d-none');
        }

        var ms = null;
        if (run.started_at && run.completed_at) {
            try {
                ms = new Date(run.completed_at) - new Date(run.started_at);
            } catch (e) { ms = null; }
        } else if (typeof run.duration_ms === 'number') {
            ms = run.duration_ms;
        }
        if (timeEl && ms != null && !isNaN(ms) && ms >= 0) {
            var secs = Math.max(1, Math.round(ms / 1000));
            timeEl.textContent = 'Time · ' + secs + 's';
            timeEl.classList.remove('d-none');
        }

        if (qualityEl) {
            var q = status === 'completed' ? 'Quality · Good'
                : status === 'failed' ? 'Quality · Needs review'
                : 'Quality · —';
            qualityEl.textContent = q;
            qualityEl.classList.remove('d-none');
        }
    }

    function renderHistory(runs) {
        var el = $('agents-history');
        if (!el) return;
        if (!runs || !runs.length) {
            el.innerHTML = '<div class="text-secondary small">No agent runs yet.</div>';
            return;
        }
        el.innerHTML = runs.map(function (r) {
            var steps = (r.steps || []).map(function (s) {
                return '<span class="agents-hist-chip ' + statusClass(s.status) + '">' +
                    (s.agent_key || '?') + '</span>';
            }).join('');
            var goal = (r.input && r.input.goal) ? r.input.goal : (r.mode || '');
            return (
                '<button type="button" class="agents-hist-item" data-run-id="' + r.id + '">' +
                '<div class="d-flex justify-content-between gap-2">' +
                '<span class="agents-hist-goal">' + escapeHtml(String(goal).slice(0, 90)) + '</span>' +
                '<span class="badge bg-secondary bg-opacity-25 text-secondary">' + r.status + '</span>' +
                '</div>' +
                '<div class="agents-hist-steps mt-1">' + steps + '</div>' +
                '</button>'
            );
        }).join('');

        el.querySelectorAll('.agents-hist-item').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-run-id');
                api('/runs/' + id).then(function (data) {
                    renderProgress(data.run);
                    renderOutput(data.run);
                }).catch(function () { /* ignore */ });
            });
        });
    }

    function escapeHtml(str) {
        return str.replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    }

    function showError(msg) {
        var el = $('agents-run-error');
        if (!el) return;
        if (!msg) {
            el.classList.add('d-none');
            el.textContent = '';
            return;
        }
        el.textContent = msg;
        el.classList.remove('d-none');
    }

    function runAgents() {
        if (state.running) return;
        var goal = ($('agents-goal') || {}).value || '';
        goal = goal.trim();
        if (!goal) {
            showError('Please enter a goal / brief.');
            return;
        }
        showError('');

        var body = {
            goal: goal,
            brand_voice: (($('agents-brand-voice') || {}).value || '').trim() || undefined,
        };

        try {
            var pid = new URLSearchParams(window.location.search).get('project_id');
            if (pid) body.project_id = parseInt(pid, 10);
        } catch (e) { /* ignore */ }

        if (state.mode === 'single') {
            body.agent_key = ($('agents-select') || {}).value;
            if (!body.agent_key) {
                showError('Select an agent.');
                return;
            }
        } else if (state.mode === 'workflow') {
            body.workflow_key = ($('agents-workflow-select') || {}).value;
            if (!body.workflow_key) {
                showError('Select a workflow.');
                return;
            }
        } else {
            body.mode = 'auto';
        }

        state.running = true;
        var btn = $('agents-run-btn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Running…';
        }

        // Optimistic progress from expected chain
        var expectedKeys = [];
        if (state.mode === 'single') {
            expectedKeys = [body.agent_key];
        } else if (state.mode === 'workflow') {
            var wf = state.workflows.find(function (w) { return w.key === body.workflow_key; });
            expectedKeys = (wf && wf.steps) || [];
        } else {
            expectedKeys = ['research', 'seo', 'content', 'campaign'];
        }
        renderProgress({
            steps: expectedKeys.map(function (k, i) {
                return { agent_key: k, status: i === 0 ? 'running' : 'waiting' };
            }),
        });
        var out = $('agents-output');
        if (out) out.textContent = 'Working on your workflow…';

        api('/run', { method: 'POST', body: body })
            .then(function (data) {
                renderProgress(data.run);
                renderOutput(data.run);
                loadHistory();
            })
            .catch(function (err) {
                showError(err.message || 'Run failed');
                var el = $('agents-progress');
                if (el) {
                    el.innerHTML = '<div class="text-danger small">' + escapeHtml(err.message || 'Failed') + '</div>';
                }
            })
            .finally(function () {
                state.running = false;
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Run AI Workflow';
                }
            });
    }

    function loadHistory() {
        api('/history?limit=12').then(function (data) {
            renderHistory(data.runs || []);
        }).catch(function () { /* ignore */ });
    }

    function init() {
        if (!$('panel-agents')) return;

        document.querySelectorAll('.agents-mode-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                setMode(btn.getAttribute('data-mode'));
            });
        });

        var runBtn = $('agents-run-btn');
        if (runBtn) runBtn.addEventListener('click', runAgents);

        var autoBtn = $('agents-auto-btn');
        if (autoBtn) {
            autoBtn.addEventListener('click', function () {
                setMode('auto');
                runAgents();
            });
        }

        var refresh = $('agents-refresh-history');
        if (refresh) refresh.addEventListener('click', loadHistory);

        Promise.all([
            api('/'),
            api('/workflows'),
        ]).then(function (results) {
            state.agents = results[0].agents || [];
            state.workflows = results[1].workflows || [];
            if (state.agents.length) state.selectedAgent = state.agents[0].key;
            renderAgentSelect();
            renderWorkflowSelect();
            renderGrid();
            setMode(state.mode || 'auto');
            loadHistory();
        }).catch(function (err) {
            showError(err.message || 'Failed to load agents');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.OplyraAgents = {
        refresh: loadHistory,
        setMode: setMode,
    };
})();
