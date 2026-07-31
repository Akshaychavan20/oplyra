# Oplyra UI Guidelines

This document details the interface layout rules, typography guidelines, responsive standards, and component definitions for Oplyra. Every new screen, card, or button must adhere to this unified design system to maintain visual consistency and clarity.

---

## 1. Visual & Theme Foundation

Oplyra uses a **High-Density, Glassmorphic Design System** that supports both Dark (default) and Light modes.

### A. Color Systems (HSL Variables)
Colors are declared as HSL values inside [style.css](file:///c:/Users/Akshay/genny%20ai/app/static/css/style.css) to support smooth transitions and opacity blending:

- **Backgrounds**:
  - Dark Theme: `hsl(224, 25%, 4%)` (Deep Indigo Black).
  - Light Theme: `hsl(210, 40%, 98%)` (Soft Off-White).
- **Cards**:
  - Dark Theme: `hsl(223, 23%, 8%)` with `65%` opacity.
  - Light Theme: `hsl(0, 0%, 100%)` with `85%` opacity.
- **Borders**:
  - HSL: `225 39% 20%` with a subtle gradient/border-glow wrapper.
- **Accent Configurations**:
  - Blue (Default): Primary `hsl(221, 83%, 53%)` / Secondary `hsl(172, 66%, 50%)`.

---

## 2. Layout & Typography Rules

### A. Spacing Systems
To ensure clean alignment, all components must follow the 8px multiplier scale:
- `4px` (xs): Tight text label spacing.
- `8px` (sm): Internal padding for buttons, tiny icon alignments.
- `16px` (md): Inner padding for standard layout cards, gap alignments.
- `24px` (lg): Global sections padding, gap between main cards.
- `32px` (xl): Hero margins, page wrapper paddings.

### B. Typography
The default system sans-serif stack uses **Inter** and **Plus Jakarta Sans**:
- **Headers (`h1` - `h3`)**: Plus Jakarta Sans, semi-bold to extra-bold (`font-weight: 600` or `700`).
- **Body Text / Labels**: Inter, light to medium (`font-weight: 300` to `500`).

```css
font-family: 'Inter', 'Plus Jakarta Sans', -apple-system, sans-serif;
```

---

## 3. Core Component Design Rules

### A. The "Today's Work" Dashboard Layout
The `/` (Today) dashboard is optimized for quick, daily checklist interaction:
- **Primary Focus**: The screen must place the date header and daily task check-list box first.
- **Aggregated Summaries**: Display a high-density, horizontal summary panel of the active client counts, total items pending, and remaining credit limits.
- **Sidebar Integration**: The navigation sidebar is locked at `240px` width. It must stay collapsed on mobile screens using a responsive toggle hamburger menu.

### B. The Campaigns Layout
The campaign panel follows the strict nesting workflow:
- Campaign headers display the Name, Budget status (with percentage bar indicators), and active Timeframes.
- Tab panels divide nested items into:
  - **Tasks**: Checklists sorted by priority.
  - **Copywriting/Ad Copy Assets**: Clean text containers with "Copy to Clipboard" actions.
  - **SEO Articles**: Table grids with status badges (`draft`, `review_pending`, `approved`).
  - **Files / Reports**: Simple preview directories.

### C. Button & Card Standards
- **Primary Buttons**: HSL Primary gradient with a smooth transition on hover (`transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1)`).
- **Glassmorphic Cards**: Must use `-webkit-backdrop-filter: blur(10px); backdrop-filter: blur(10px);` along with a very thin `1px` translucent border.

---

## 4. Micro-interactions & Animations

To provide a premium feel, include subtle transition cues:
- **Hover Effects**: Buttons and links must scale up slightly (`transform: translateY(-1px)`) or gain a faint border glow.
- **Loader States**: Use small, spinning border circles (`.spinner-border`) inside buttons during AI text generation to indicate progress.
- **Toast Notifications**: Slide in from the bottom-right for alerts (e.g. "Copy saved to clipboard").

---

## 5. Responsive Design Rules

Oplyra must remain responsive for:
- **Desktop (>= 1024px)**: Dual-pane layout, active sidebar display (`240px`), full table grids.
- **Tablet (768px - 1023px)**: Collapsed sidebar (icon-only or top navbar), cards stack vertically.
- **Mobile (<= 767px)**: Full stack cards, high contrast, padding reduced from `24px` to `16px`, full-width buttons to facilitate thumb clicks.
