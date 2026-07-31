# Oplyra Product Vision and Rules

This document outlines the product vision, mission, and rules for Oplyra. Every code change, UI change, database change, and architectural decision must adhere to this document.

---

## Mission & Philosophy
- **Mission**: Build the world's simplest operating system for solo Performance Marketers and Freelancers.
- **Core Philosophy**: ChatGPT answers questions. **Oplyra helps users finish work.**
- **Target User**: A single freelancer running Facebook Ads, Google Ads, and SEO for 3–20 clients from their laptop. Optimize everything for this person. Never design for enterprises, Fortune 500s, or large teams.

---

## Core Product Design Rules

### 1. Application Home (TODAY Page)
The Home page is **TODAY's Work**, not analytics, reports, or AI Chat. It must display:
- Greeting & Current Date.
- A list of task checkboxes for the day (e.g., Review Facebook Ads, Publish SEO Blog, Send Weekly Report).
- Answer the core question: **"What should I do today?"**

### 2. Application Structure
Keep the main navigation minimal. The only allowed top-level pages/menus unless absolutely necessary are:
1. **Home** (What should I do today?)
2. **Clients** (Who am I working for?)
3. **Campaigns** (What am I managing?)
4. **Tasks** (What needs to be completed?)
5. **AI Assistant** (Help me complete this task.)
6. **Reports** (What should I send to my client?)
7. **Settings**

### 3. Client & Campaign Structure
- Everything must be nested inside campaigns under clients.
- Path: `Client` → `Campaign` → `Tasks/Files/Reports/Notes`.
- Never create hundreds of unrelated menus. Everything belongs inside the campaign.

### 4. AI Role & Integration
- AI is an assistant, not the product. The workflow is the center of the application.
- Instead of asking *"What do you want to generate?"*, AI should ask: **"What are you trying to accomplish today?"**
- AI should be workflow-aware, using client context, campaign history, task memory, and upcoming deadlines, rather than just acting as a generic text generator.
- **AI Gateway**: Always route queries through the AI Gateway. Never bypass it.

### 5. Features Checklist
Before implementing any new feature, verify:
- Does it reduce the freelancer's workload?
- Does it remove repetitive work?
- Does it simplify the workflow?
- Does it fit inside the campaign?
- Does it require a new menu? (Prefer not)
- Can it be integrated instead of rebuilt?
- Would a freelancer use this every day?
- Would ChatGPT already solve this? (If yes, make it workflow-aware).

---

## Out of Scope (Do NOT Build)
Do not build the following, as they are already handled by other existing products. We will integrate with them in the future:
- CRM, Invoice/Accounting Software, Payroll/HR, Inventory.
- Email Marketing Platform, Facebook/Google Ads Managers, SEO keyword databases.

---

## Design Principles
- Minimal, clean, modern, professional, and fast.
- Maximum of three clicks to reach any action or detail.
- Never overwhelm users.
- Every change must reduce work.
