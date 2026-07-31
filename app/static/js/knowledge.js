/**
 * Knowledge Center UI — upload, collections, semantic search, documents.
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
        return fetch('/api/knowledge' + path, Object.assign({}, options, { headers: headers }))
            .then(function (res) {
                return res.json().then(function (data) {
                    if (!res.ok) throw new Error((data && data.error) || 'Request failed');
                    return data;
                });
            });
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    }

    function formatBytes(n) {
        n = Number(n) || 0;
        if (n < 1024) return n + ' B';
        if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
        return (n / 1048576).toFixed(1) + ' MB';
    }

    var state = { collections: [], documents: [], selectedCollection: null };

    function showError(msg) {
        var el = $('knowledge-upload-error');
        if (!el) return;
        if (!msg) { el.classList.add('d-none'); el.textContent = ''; return; }
        el.textContent = msg;
        el.classList.remove('d-none');
    }

    function setProgress(on) {
        var el = $('knowledge-progress');
        if (!el) return;
        el.classList.toggle('d-none', !on);
    }

    function renderStats(stats) {
        if (!stats) return;
        if ($('ks-docs')) $('ks-docs').textContent = stats.documents || 0;
        if ($('ks-chunks')) $('ks-chunks').textContent = stats.chunks || 0;
        if ($('ks-embeds')) $('ks-embeds').textContent = stats.embeddings || 0;
        if ($('ks-searches')) $('ks-searches').textContent = stats.searches || 0;
        if ($('knowledge-storage-label')) {
            $('knowledge-storage-label').textContent = formatBytes(stats.storage_bytes) + ' stored';
        }
    }

    function renderCollections() {
        var el = $('knowledge-collections');
        var sel = $('knowledge-collection-select');
        if (!el) return;
        el.innerHTML = state.collections.map(function (c) {
            return '<button type="button" class="knowledge-collection-item' +
                (state.selectedCollection === c.id ? ' active' : '') +
                '" data-id="' + c.id + '">' +
                '<span>' + escapeHtml(c.name) + '</span>' +
                '<span class="badge bg-secondary bg-opacity-25">' + (c.document_count || 0) + '</span>' +
                '</button>';
        }).join('') || '<div class="text-secondary small">No collections yet.</div>';

        if (sel) {
            sel.innerHTML = '<option value="">Default (Workspace)</option>' +
                state.collections.map(function (c) {
                    return '<option value="' + c.id + '">' + escapeHtml(c.name) + '</option>';
                }).join('');
        }

        el.querySelectorAll('.knowledge-collection-item').forEach(function (btn) {
            btn.addEventListener('click', function () {
                state.selectedCollection = parseInt(btn.getAttribute('data-id'), 10);
                renderCollections();
                loadHome();
            });
        });
    }

    function renderDocuments(docs) {
        var el = $('knowledge-documents');
        if (!el) return;
        if (!docs || !docs.length) {
            el.innerHTML = '<div class="text-secondary small">No documents indexed yet. Upload a brand guide or paste a playbook.</div>';
            return;
        }
        el.innerHTML = docs.map(function (d) {
            return '<button type="button" class="knowledge-doc-item" data-id="' + d.id + '">' +
                '<div class="d-flex justify-content-between gap-2">' +
                '<span class="knowledge-doc-title">' + escapeHtml(d.title) + '</span>' +
                '<span class="badge bg-secondary bg-opacity-25 text-secondary">' + escapeHtml(d.doc_type) + '</span>' +
                '</div>' +
                '<div class="text-secondary small mt-1">' +
                (d.chunk_count || 0) + ' chunks · v' + (d.current_version || 1) + ' · ' + escapeHtml(d.status) +
                '</div></button>';
        }).join('');

        el.querySelectorAll('.knowledge-doc-item').forEach(function (btn) {
            btn.addEventListener('click', function () {
                openDocument(parseInt(btn.getAttribute('data-id'), 10));
            });
        });
    }

    function renderSearchResults(results) {
        var el = $('knowledge-search-results');
        if (!el) return;
        if (!results || !results.length) {
            el.innerHTML = '<div class="text-secondary small">No matches.</div>';
            return;
        }
        el.innerHTML = results.map(function (r) {
            var snippet = escapeHtml((r.content || '').slice(0, 280));
            return '<div class="knowledge-hit">' +
                '<div class="d-flex justify-content-between">' +
                '<strong class="text-white small">' + escapeHtml(r.document_title) + '</strong>' +
                '<span class="text-secondary small">' + (r.score * 100).toFixed(0) + '%</span>' +
                '</div>' +
                '<div class="knowledge-hit-snippet">' + snippet + '</div></div>';
        }).join('');
    }

    function openDocument(id) {
        api('/document/' + id).then(function (data) {
            var d = data.document;
            var card = $('knowledge-detail-card');
            if (!card) return;
            card.classList.remove('d-none');
            $('knowledge-detail-title').textContent = d.title;
            $('knowledge-detail-meta').textContent =
                d.doc_type + ' · ' + (d.chunk_count || 0) + ' chunks · version ' + d.current_version;
            $('knowledge-detail-content').textContent = d.content_preview || '';
            var vers = $('knowledge-detail-versions');
            vers.innerHTML = (d.versions || []).map(function (v) {
                return '<button type="button" class="btn btn-secondary-custom btn-sm me-1 mb-1 knowledge-restore-btn" data-v="' +
                    v.version_number + '" data-id="' + d.id + '">Restore v' + v.version_number + '</button>';
            }).join('');
            vers.querySelectorAll('.knowledge-restore-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    api('/document/' + btn.getAttribute('data-id') + '/restore/' + btn.getAttribute('data-v'), {
                        method: 'POST',
                        json: {},
                    }).then(function () {
                        loadHome();
                        openDocument(id);
                    }).catch(function (e) { alert(e.message); });
                });
            });
        });
    }

    function loadHome() {
        api('/').then(function (data) {
            state.collections = data.collections || [];
            state.documents = data.documents || [];
            renderStats(data.stats);
            renderCollections();
            renderDocuments(state.documents);
        }).catch(function (e) {
            showError(e.message);
        });
    }

    function ingest() {
        showError('');
        setProgress(true);
        var collectionId = ($('knowledge-collection-select') || {}).value;
        var collection_ids = collectionId ? [parseInt(collectionId, 10)] : [];
        var fileInput = $('knowledge-file-input');
        var url = (($('knowledge-url') || {}).value || '').trim();
        var title = (($('knowledge-note-title') || {}).value || '').trim();
        var text = (($('knowledge-note-text') || {}).value || '').trim();

        var done = function () {
            setProgress(false);
            if ($('knowledge-note-text')) $('knowledge-note-text').value = '';
            if ($('knowledge-url')) $('knowledge-url').value = '';
            if (fileInput) fileInput.value = '';
            loadHome();
        };

        if (fileInput && fileInput.files && fileInput.files.length) {
            var chain = Promise.resolve();
            Array.prototype.forEach.call(fileInput.files, function (file) {
                chain = chain.then(function () {
                    var fd = new FormData();
                    fd.append('file', file);
                    if (title) fd.append('title', title);
                    collection_ids.forEach(function (id) { fd.append('collection_ids', id); });
                    return fetch('/api/knowledge/upload', {
                        method: 'POST',
                        headers: { 'X-CSRF-Token': csrf() },
                        body: fd,
                    }).then(function (res) {
                        return res.json().then(function (data) {
                            if (!res.ok) throw new Error(data.error || 'Upload failed');
                            return data;
                        });
                    });
                });
            });
            chain.then(done).catch(function (e) { setProgress(false); showError(e.message); });
            return;
        }

        if (url) {
            api('/upload', {
                method: 'POST',
                json: {
                    url: url,
                    title: title || url,
                    collection_ids: collection_ids,
                    sitemap: url.toLowerCase().indexOf('sitemap') !== -1,
                },
            }).then(done).catch(function (e) { setProgress(false); showError(e.message); });
            return;
        }

        if (text) {
            api('/upload', {
                method: 'POST',
                json: {
                    title: title || 'Manual note',
                    text: text,
                    doc_type: 'note',
                    collection_ids: collection_ids,
                },
            }).then(done).catch(function (e) { setProgress(false); showError(e.message); });
            return;
        }

        setProgress(false);
        showError('Add a file, URL, or note text.');
    }

    function runSearch() {
        var q = (($('knowledge-search-input') || {}).value || '').trim();
        if (!q) return;
        var type = ($('knowledge-search-type') || {}).value || 'hybrid';
        api('/search', {
            method: 'POST',
            json: { query: q, search_type: type, top_k: 8 },
        }).then(function (data) {
            renderSearchResults(data.results || []);
        }).catch(function (e) {
            renderSearchResults([]);
            showError(e.message);
        });
    }

    function initDropzone() {
        var zone = $('knowledge-dropzone');
        var input = $('knowledge-file-input');
        if (!zone || !input) return;
        zone.addEventListener('click', function () { input.click(); });
        zone.addEventListener('dragover', function (e) {
            e.preventDefault();
            zone.classList.add('is-dragover');
        });
        zone.addEventListener('dragleave', function () { zone.classList.remove('is-dragover'); });
        zone.addEventListener('drop', function (e) {
            e.preventDefault();
            zone.classList.remove('is-dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                zone.querySelector('div').textContent = e.dataTransfer.files.length + ' file(s) ready';
            }
        });
        input.addEventListener('change', function () {
            if (input.files.length) {
                zone.querySelector('div').textContent = input.files.length + ' file(s) selected';
            }
        });
    }

    function init() {
        if (!$('panel-knowledge')) return;
        initDropzone();
        if ($('knowledge-ingest-btn')) $('knowledge-ingest-btn').addEventListener('click', ingest);
        if ($('knowledge-search-btn')) $('knowledge-search-btn').addEventListener('click', runSearch);
        if ($('knowledge-search-input')) {
            $('knowledge-search-input').addEventListener('keydown', function (e) {
                if (e.key === 'Enter') runSearch();
            });
        }
        if ($('knowledge-detail-close')) {
            $('knowledge-detail-close').addEventListener('click', function () {
                $('knowledge-detail-card').classList.add('d-none');
            });
        }
        if ($('knowledge-reindex-btn')) {
            $('knowledge-reindex-btn').addEventListener('click', function () {
                setProgress(true);
                api('/reindex', { method: 'POST', json: {} })
                    .then(function () { setProgress(false); loadHome(); })
                    .catch(function (e) { setProgress(false); showError(e.message); });
            });
        }
        if ($('knowledge-new-collection-btn')) {
            $('knowledge-new-collection-btn').addEventListener('click', function () {
                var name = prompt('Collection name');
                if (!name) return;
                api('/collections', {
                    method: 'POST',
                    json: { name: name, collection_type: 'workspace' },
                }).then(loadHome).catch(function (e) { alert(e.message); });
            });
        }
        loadHome();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
