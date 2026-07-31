# Oplyra Non-Negotiable Rules

This document outlines the ten core commandments of Oplyra. These rules govern every design choice, coding style, database design, and product feature. They must never be violated under any circumstances.

---

## The Ten Commandments of Oplyra

### 1. Home is "Today's Work"
- **Rule**: The application homepage (`/`) must always render the current day's focus and task checklist. 
- **Reason**: The solo marketer's biggest problem is deciding *what to work on right now*. Home must never be a generic analytics graph or an empty chat input.

### 2. Campaigns are the Center of the Universe
- **Rule**: All task files, generated copy assets, SEO article records, notes, and metrics must be nested inside a specific campaign under a client.
- **Reason**: Performance marketers organize their actual daily billing and work by campaign. Unnested, global lists of copy or files lead to fragmentation.

### 3. AI is an Assistant, Not the Product
- **Rule**: AI must serve to execute a workflow step (e.g. "Create ad copy drafts inside this task panel"). Do not build open-ended "AI chat rooms" or generalized prompt inputs.
- **Reason**: Conversational chatbots generate high cognitive load (the user has to invent prompts). Oplyra provides context-aware accelerators instead.

### 4. Workflow Over Features
- **Rule**: Prioritize smooth, fast task execution (creation → AI generation → SEO check → export) over adding hundreds of independent tool features.
- **Reason**: An integrated, three-click workflow saves the freelancer hours of work, whereas many disconnected features increase setup work.

### 5. The Three-Click Constraint
- **Rule**: Any core task—such as logging a client, starting a campaign, generating a blog post, or exporting a PDF report—must require no more than three clicks from the home dashboard.
- **Reason**: Solo freelancers are busy. If an operation is buried under four or five submenus, it increases friction and will be ignored.

### 6. Minimizing Cognitive Load
- **Rule**: UI screens must be clean, focused, and free of clutter. Use high-contrast headings, collapse advanced options, and group metrics logically.
- **Reason**: Marketers suffer from daily dashboard fatigue from navigating tools like Meta Ads Manager. Oplyra must feel like a calm, productive sanctuary.

### 7. No Unnecessary Menus
- **Rule**: Do not create new sidebar menu directories. The sidebar is frozen to: `Home`, `Clients`, `Campaigns`, `Tasks`, `AI Assistant`, `Reports`, and `Settings`.
- **Reason**: Expanding the sidebar list breaks visual simplicity and makes the application look like standard, bloated enterprise CRM platforms.

### 8. Never Clone ChatGPT
- **Rule**: Do not build generic Q&A prompt boxes that say *"What would you like to generate today?"*. Instead, display *"What task are we trying to accomplish?"* and inject local client details automatically.
- **Reason**: Solo freelancers can use ChatGPT in another tab for free. Oplyra's value lies in its automation using client history and brand kits.

### 9. Always Reduce Tool Switching
- **Rule**: Every features design must aim to eliminate browser tab switching (e.g. keeping writing tools, SEO analysis, and PDF templates local).
- **Reason**: Switching between browser tabs breaks cognitive focus. Consolidating execution actions inside Oplyra is our primary goal.

### 10. Protect Simplicity
- **Rule**: Reject any feature request that is built for "agencies with roles", "client feedback client portals", or "enterprise workflows."
- **Reason**: Oplyra is built for the *solo solopreneur* on a laptop. Multi-user permissions add database complexity and ruin layout simplicity.

### 11. Recommendations Must Answer Three Questions
- **Rule**: Every recommendation shown to the user must explicitly answer three questions: "Why is this shown?", "What should I do?", and "What happens if I ignore it?". If a recommendation cannot supply all three, it must not be displayed.
- **Reason**: Vague prompts increase cognitive friction. Solopreneurs need precise, actionable warnings that explicitly state the risk of inaction.

