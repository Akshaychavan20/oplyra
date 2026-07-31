// Workspace & Projects UI Helpers - Oplyra

document.addEventListener('DOMContentLoaded', function () {
    initEditProjectModal();
    initProjectsList();
    initWorkspaceDetail();
});

/**
 * Debounce helper for search inputs.
 */
function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

/**
 * Populate edit modal from triggering button data attributes.
 */
function initEditProjectModal() {
    const editProjectModal = document.getElementById('editProjectModal');
    if (!editProjectModal) return;

    editProjectModal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        if (!button) return;

        const id = button.getAttribute('data-bs-id');
        const name = button.getAttribute('data-bs-name');
        const description = button.getAttribute('data-bs-description');

        const form = editProjectModal.querySelector('#edit-project-form');
        const nameInput = editProjectModal.querySelector('#edit-name');
        const descriptionInput = editProjectModal.querySelector('#edit-description');

        if (form) form.action = `/clients/${id}/edit`;
        if (nameInput) nameInput.value = name || '';
        if (descriptionInput) descriptionInput.value = description || '';
    });
}

/**
 * Workspace list: search, sort, visible count.
 */
function initProjectsList() {
    const grid = document.getElementById('project-card-grid');
    if (!grid) return;

    const searchInput = document.getElementById('project-search');
    const sortSelect = document.getElementById('project-sort');
    const noProjectsMessage = document.getElementById('no-projects-found');
    const countBadge = document.getElementById('projects-visible-count');

    let cards = Array.from(grid.querySelectorAll('.project-card-item'));
    const totalCount = cards.length;

    function getCardData(card) {
        return {
            name: (card.getAttribute('data-name') || '').toLowerCase(),
            description: (card.getAttribute('data-description') || '').toLowerCase(),
            updated: parseFloat(card.getAttribute('data-updated')) || 0,
            created: parseFloat(card.getAttribute('data-created')) || 0,
            assetCount: parseInt(card.getAttribute('data-asset-count'), 10) || 0
        };
    }

    function sortCards(sortValue) {
        const sorted = [...cards].sort((a, b) => {
            const da = getCardData(a);
            const db = getCardData(b);

            switch (sortValue) {
                case 'oldest':
                    return da.updated - db.updated;
                case 'name-asc':
                    return da.name.localeCompare(db.name);
                case 'name-desc':
                    return db.name.localeCompare(da.name);
                case 'assets-desc':
                    return db.assetCount - da.assetCount;
                case 'newest':
                default:
                    return db.updated - da.updated;
            }
        });

        sorted.forEach(card => {
            if (noProjectsMessage) {
                grid.insertBefore(card, noProjectsMessage);
            } else {
                grid.appendChild(card);
            }
        });
        cards = sorted;
    }

    function applyFilters() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        let visibleCount = 0;

        cards.forEach(card => {
            const data = getCardData(card);
            const matches = !query || data.name.includes(query) || data.description.includes(query);
            card.classList.toggle('d-none', !matches);
            if (matches) visibleCount++;
        });

        if (noProjectsMessage) {
            const showEmpty = visibleCount === 0 && totalCount > 0;
            noProjectsMessage.classList.toggle('d-none', !showEmpty);
            noProjectsMessage.hidden = !showEmpty;
            noProjectsMessage.setAttribute('aria-hidden', showEmpty ? 'false' : 'true');
        }

        if (countBadge) {
            if (totalCount === 0) {
                countBadge.textContent = '0 workspaces';
            } else if (visibleCount === totalCount) {
                countBadge.textContent = `${totalCount} workspace${totalCount !== 1 ? 's' : ''}`;
            } else {
                countBadge.textContent = `${visibleCount} of ${totalCount} workspaces`;
            }
        }
    }

    if (sortSelect) {
        sortSelect.addEventListener('change', function () {
            sortCards(this.value);
            applyFilters();
        });
        sortCards(sortSelect.value || 'newest');
    }

    if (searchInput) {
        const debouncedFilter = debounce(applyFilters, 150);
        searchInput.addEventListener('input', debouncedFilter);

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                searchInput.value = '';
                applyFilters();
                searchInput.blur();
            }
        });
    }

    applyFilters();
}

/**
 * Workspace detail: asset search, type filter, sort.
 */
function initWorkspaceDetail() {
    const grid = document.getElementById('asset-card-grid');
    if (!grid) return;

    const searchInput = document.getElementById('asset-search');
    const sortSelect = document.getElementById('asset-sort');
    const noAssetsMessage = document.getElementById('no-assets-found');
    const countBadge = document.getElementById('assets-visible-count');
    const filterPills = document.querySelectorAll('.workspace-filter-pill');

    let cards = Array.from(grid.querySelectorAll('.asset-card-item'));
    const totalCount = cards.length;
    let activeFilter = 'all';

    function getAssetData(card) {
        return {
            title: (card.getAttribute('data-title') || '').toLowerCase(),
            type: card.getAttribute('data-type') || '',
            date: parseFloat(card.getAttribute('data-date')) || 0,
            status: card.getAttribute('data-status') || ''
        };
    }

    function sortAssets(sortValue) {
        const sorted = [...cards].sort((a, b) => {
            const da = getAssetData(a);
            const db = getAssetData(b);

            switch (sortValue) {
                case 'date-asc':
                    return da.date - db.date;
                case 'title-asc':
                    return da.title.localeCompare(db.title);
                case 'title-desc':
                    return db.title.localeCompare(da.title);
                case 'type-asc':
                    return da.type.localeCompare(db.type);
                case 'date-desc':
                default:
                    return db.date - da.date;
            }
        });

        sorted.forEach(card => {
            if (noAssetsMessage) {
                grid.insertBefore(card, noAssetsMessage);
            } else {
                grid.appendChild(card);
            }
        });

        cards = sorted;
    }

    function applyAssetFilters() {
        const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
        let visibleCount = 0;

        cards.forEach(card => {
            const data = getAssetData(card);
            const matchesSearch = !query || data.title.includes(query);
            const matchesType = activeFilter === 'all' || data.type === activeFilter;
            const visible = matchesSearch && matchesType;
            card.classList.toggle('d-none', !visible);
            if (visible) visibleCount++;
        });

        if (noAssetsMessage) {
            const showEmpty = visibleCount === 0 && totalCount > 0;
            noAssetsMessage.classList.toggle('d-none', !showEmpty);
            noAssetsMessage.hidden = !showEmpty;
            noAssetsMessage.setAttribute('aria-hidden', showEmpty ? 'false' : 'true');
        }

        if (countBadge) {
            if (visibleCount === totalCount) {
                countBadge.textContent = totalCount;
            } else {
                countBadge.textContent = `${visibleCount}/${totalCount}`;
            }
        }
    }

    filterPills.forEach(pill => {
        pill.addEventListener('click', function () {
            filterPills.forEach(p => {
                p.classList.remove('active');
                p.setAttribute('aria-pressed', 'false');
            });
            this.classList.add('active');
            this.setAttribute('aria-pressed', 'true');
            activeFilter = this.getAttribute('data-filter') || 'all';
            applyAssetFilters();
        });

        pill.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.click();
            }
        });
    });

    if (sortSelect) {
        sortSelect.addEventListener('change', function () {
            sortAssets(this.value);
            applyAssetFilters();
        });
        sortAssets(sortSelect.value || 'date-desc');
    }

    if (searchInput) {
        const debouncedFilter = debounce(applyAssetFilters, 150);
        searchInput.addEventListener('input', debouncedFilter);

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                searchInput.value = '';
                applyAssetFilters();
                searchInput.blur();
            }
        });
    }

    applyAssetFilters();
}
