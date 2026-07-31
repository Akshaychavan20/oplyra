// Top navbar popovers — notifications & profile dropdowns

document.addEventListener('DOMContentLoaded', function () {
    const navbar = document.querySelector('.top-navbar');
    if (!navbar) return;

    const dropdownToggles = navbar.querySelectorAll('[data-bs-toggle="dropdown"]');

    dropdownToggles.forEach(function (toggle) {
        if (typeof bootstrap === 'undefined' || !bootstrap.Dropdown) return;

        const dropdownRoot = toggle.closest('.dropdown');
        const menu = dropdownRoot ? dropdownRoot.querySelector('.dropdown-menu') : null;
        if (!menu) return;

        bootstrap.Dropdown.getOrCreateInstance(toggle, { autoClose: true });

        dropdownRoot.addEventListener('show.bs.dropdown', function () {
            menu.classList.add('nav-popover-visible');
            toggle.setAttribute('aria-expanded', 'true');
        });

        dropdownRoot.addEventListener('hide.bs.dropdown', function () {
            menu.classList.remove('nav-popover-visible');
            toggle.setAttribute('aria-expanded', 'false');
        });
    });

    // Close any open navbar popover when clicking outside
    document.addEventListener('click', function (e) {
        if (navbar.contains(e.target)) return;

        dropdownToggles.forEach(function (toggle) {
            const instance = bootstrap.Dropdown.getInstance(toggle);
            if (instance) instance.hide();
        });
    });

    // Close on Escape
    document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;

        dropdownToggles.forEach(function (toggle) {
            const instance = bootstrap.Dropdown.getInstance(toggle);
            if (instance) instance.hide();
        });
    });
});
