(function () {
    'use strict';

    const cfg = window.OPLYRA_INTEGRATIONS || {};
    const connections = cfg.connections || [];

    function byId(id) {
        return document.getElementById(id);
    }

    function connectionById(id) {
        return connections.find(function (c) { return c.id === id; });
    }

    function populateImportables(connectionId) {
        const select = byId('import-external');
        const importBtn = byId('import-btn');
        if (!select) return;

        const conn = connectionById(Number(connectionId));
        select.innerHTML = '';
        if (!conn || !conn.importables || !conn.importables.length) {
            select.innerHTML = '<option value="">No campaigns — run Sync first</option>';
            if (importBtn) importBtn.disabled = true;
            return;
        }

        conn.importables.forEach(function (item) {
            const opt = document.createElement('option');
            opt.value = item.external_campaign_id;
            opt.textContent = item.imported
                ? item.external_campaign_name + ' (imported)'
                : item.external_campaign_name;
            opt.disabled = item.imported;
            select.appendChild(opt);
        });

        const firstAvailable = conn.importables.find(function (i) { return !i.imported; });
        if (importBtn) importBtn.disabled = !firstAvailable;
    }

    function updateConnectionInMemory(updated) {
        const idx = connections.findIndex(function (c) { return c.id === updated.id; });
        if (idx >= 0) {
            connections[idx] = updated;
        } else {
            connections.push(updated);
        }
    }

    document.querySelectorAll('.sync-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            const connectionId = btn.getAttribute('data-connection-id');
            const original = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Syncing…';

            fetch('/integrations/sync/' + connectionId, {
                method: 'POST',
                headers: {
                    'X-CSRF-Token': cfg.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(function (r) {
                    return r.json().then(function (data) {
                        if (!r.ok) throw new Error(data.error || 'Sync failed');
                        return data;
                    });
                })
                .then(function (data) {
                    if (!data.success) {
                        throw new Error(data.error || 'Sync failed');
                    }
                    updateConnectionInMemory(data.connection);
                    const lastEl = byId('last-sync-' + connectionId);
                    const statusEl = byId('sync-status-' + connectionId);
                    const errorEl = byId('sync-error-' + connectionId);
                    if (lastEl && data.connection.last_sync_at) {
                        lastEl.textContent = new Date(data.connection.last_sync_at).toUTCString().slice(0, 22) + ' UTC';
                    }
                    if (statusEl) {
                        statusEl.textContent = data.connection.last_sync_status || 'success';
                        statusEl.className = 'text-success';
                    }
                    if (errorEl) errorEl.textContent = '';
                    const connSelect = byId('import-connection');
                    if (connSelect && Number(connSelect.value) === data.connection.id) {
                        populateImportables(connectionId);
                    }
                })
                .catch(function (err) {
                    const statusEl = byId('sync-status-' + connectionId);
                    let errorEl = byId('sync-error-' + connectionId);
                    if (statusEl) {
                        statusEl.textContent = 'error';
                        statusEl.className = 'text-danger';
                    }
                    if (!errorEl) {
                        errorEl = document.createElement('p');
                        errorEl.id = 'sync-error-' + connectionId;
                        errorEl.className = 'text-danger small mt-2 mb-0';
                        btn.closest('.glass-card').querySelector('.mb-3.small').appendChild(errorEl);
                    }
                    errorEl.textContent = err.message || 'Sync failed';
                })
                .finally(function () {
                    btn.disabled = false;
                    btn.innerHTML = original;
                });
        });
    });

    const connSelect = byId('import-connection');
    if (connSelect) {
        populateImportables(connSelect.value);
        connSelect.addEventListener('change', function () {
            populateImportables(connSelect.value);
        });
    }

    const importBtn = byId('import-btn');
    if (importBtn) {
        importBtn.addEventListener('click', function () {
            const connectionId = byId('import-connection').value;
            const externalId = byId('import-external').value;
            const projectId = byId('import-project').value;
            const resultEl = byId('import-result');

            if (!externalId) return;

            importBtn.disabled = true;
            resultEl.textContent = 'Importing…';

            fetch('/integrations/import', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': cfg.csrfToken
                },
                body: JSON.stringify({
                    connection_id: connectionId,
                    external_campaign_id: externalId,
                    project_id: projectId
                })
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data.success) throw new Error(data.error || 'Import failed');
                    const msg = data.created
                        ? 'Campaign "' + data.campaign.name + '" created.'
                        : 'Campaign already imported (id ' + data.campaign.id + ').';
                    resultEl.innerHTML = '<span class="text-success">' + msg + '</span> '
                        + '<a href="/clients/' + data.campaign.project_id + '" class="text-indigo">View Client</a>';
                    const conn = connectionById(Number(connectionId));
                    if (conn && conn.importables) {
                        conn.importables.forEach(function (item) {
                            if (item.external_campaign_id === externalId) {
                                item.imported = true;
                                item.campaign_id = data.campaign.id;
                            }
                        });
                    }
                    populateImportables(connectionId);
                })
                .catch(function (err) {
                    resultEl.innerHTML = '<span class="text-danger">' + (err.message || 'Import failed') + '</span>';
                    importBtn.disabled = false;
                });
        });
    }
})();
