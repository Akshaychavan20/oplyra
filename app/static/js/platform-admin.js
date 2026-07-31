/**
 * Oplyra Internal Admin — UI chrome (sidebar, command palette, counters, drawer).
 * No auth/RBAC logic — presentation only.
 */
(function () {
  'use strict';

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  /* ── Sidebar collapse (mirrors customer app) ─────────────────────────── */
  function initSidebar() {
    var btn = qs('#sidebar-toggle-btn');
    var sidebar = qs('#pa-sidebar');
    if (!btn || !sidebar) return;

    btn.addEventListener('click', function () {
      if (window.innerWidth < 992) {
        sidebar.classList.toggle('show');
        return;
      }
      document.documentElement.classList.toggle('sidebar-collapsed');
      localStorage.setItem(
        'pa-sidebar-collapsed',
        document.documentElement.classList.contains('sidebar-collapsed') ? '1' : '0'
      );
    });
  }

  /* ── Animated counters ───────────────────────────────────────────────── */
  function animateValue(el) {
    var raw = el.getAttribute('data-count');
    if (raw == null || raw === '') return;
    var prefix = el.getAttribute('data-prefix') || '';
    var suffix = el.getAttribute('data-suffix') || '';
    var decimals = parseInt(el.getAttribute('data-decimals') || '0', 10);
    var target = parseFloat(String(raw).replace(/,/g, ''));
    if (isNaN(target)) {
      el.textContent = prefix + raw + suffix;
      return;
    }
    var start = performance.now();
    var duration = 700;
    function frame(now) {
      var t = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - t, 3);
      var val = target * eased;
      el.textContent =
        prefix +
        (decimals > 0 ? val.toFixed(decimals) : Math.round(val).toLocaleString()) +
        suffix;
      if (t < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function initCounters() {
    qsa('[data-count]').forEach(animateValue);
  }

  /* ── Command palette ─────────────────────────────────────────────────── */
  function buildCommands() {
    return qsa('[data-pa-cmd]').map(function (el) {
      return {
        title: el.getAttribute('data-pa-cmd'),
        group: el.getAttribute('data-pa-cmd-group') || 'Navigate',
        href: el.getAttribute('href'),
        icon: (el.querySelector('i') && el.querySelector('i').className) || 'bi bi-arrow-right',
      };
    });
  }

  function initCommandPalette() {
    var overlay = qs('#pa-cmd-overlay');
    var input = qs('#pa-cmd-input');
    var list = qs('#pa-cmd-list');
    var openBtn = qs('#pa-cmd-open');
    if (!overlay || !input || !list) return;

    var commands = buildCommands();
    var active = 0;
    var filtered = commands.slice();

    function render() {
      if (!filtered.length) {
        list.innerHTML = '<div class="pa-cmd-empty">No matches</div>';
        return;
      }
      list.innerHTML = filtered
        .map(function (c, i) {
          return (
            '<a class="pa-cmd-item' +
            (i === active ? ' is-active' : '') +
            '" href="' +
            c.href +
            '" data-idx="' +
            i +
            '">' +
            '<i class="' +
            c.icon +
            '"></i>' +
            '<span>' +
            c.title +
            '</span>' +
            '<span class="pa-cmd-hint">' +
            c.group +
            '</span></a>'
          );
        })
        .join('');
    }

    function open() {
      overlay.hidden = false;
      overlay.classList.add('is-open');
      input.value = '';
      filtered = commands.slice();
      active = 0;
      render();
      setTimeout(function () {
        input.focus();
      }, 10);
    }

    function close() {
      overlay.classList.remove('is-open');
      overlay.hidden = true;
    }

    function filter(q) {
      q = (q || '').trim().toLowerCase();
      filtered = !q
        ? commands.slice()
        : commands.filter(function (c) {
            return (
              c.title.toLowerCase().indexOf(q) !== -1 ||
              c.group.toLowerCase().indexOf(q) !== -1
            );
          });
      active = 0;
      render();
    }

    if (openBtn) openBtn.addEventListener('click', open);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    input.addEventListener('input', function () {
      filter(input.value);
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        active = Math.min(filtered.length - 1, active + 1);
        render();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        active = Math.max(0, active - 1);
        render();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filtered[active]) window.location.href = filtered[active].href;
      } else if (e.key === 'Escape') {
        close();
      }
    });

    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (overlay.classList.contains('is-open')) close();
        else open();
      }
      if (e.key === 'Escape' && overlay.classList.contains('is-open')) close();
    });

    list.addEventListener('mousemove', function (e) {
      var item = e.target.closest('.pa-cmd-item');
      if (!item) return;
      active = parseInt(item.getAttribute('data-idx'), 10) || 0;
      qsa('.pa-cmd-item', list).forEach(function (el, i) {
        el.classList.toggle('is-active', i === active);
      });
    });
  }

  /* ── Drawer ──────────────────────────────────────────────────────────── */
  function initDrawer() {
    var overlay = qs('#pa-drawer-overlay');
    var drawer = qs('#pa-drawer');
    var closeBtn = qs('#pa-drawer-close');
    if (!overlay || !drawer) return;

    function close() {
      drawer.classList.remove('is-open');
      overlay.classList.remove('is-open');
      drawer.setAttribute('aria-hidden', 'true');
      drawer.hidden = true;
      overlay.hidden = true;
    }

    function open(title, html) {
      var t = qs('#pa-drawer-title');
      var body = qs('#pa-drawer-body');
      if (t) t.textContent = title || 'Details';
      if (body) body.innerHTML = html || '';
      overlay.hidden = false;
      drawer.hidden = false;
      drawer.classList.add('is-open');
      overlay.classList.add('is-open');
      drawer.setAttribute('aria-hidden', 'false');
    }

    // Ensure closed on boot (no residual black overlay/strip)
    close();

    if (closeBtn) closeBtn.addEventListener('click', close);
    overlay.addEventListener('click', close);

    window.OplyraAdminUI = window.OplyraAdminUI || {};
    window.OplyraAdminUI.openDrawer = open;
    window.OplyraAdminUI.closeDrawer = close;

    qsa('[data-pa-drawer]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        e.preventDefault();
        open(el.getAttribute('data-pa-drawer-title') || 'Details', el.getAttribute('data-pa-drawer') || '');
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initSidebar();
    initCounters();
    initCommandPalette();
    initDrawer();
    var h1 = qs('.pa-page-header h1');
    var crumb = qs('.pa-crumb-current');
    if (h1 && crumb) crumb.textContent = h1.textContent.trim();
  });
})();
