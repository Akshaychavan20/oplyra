# Oplyra User Workflow

This document records the standard user journey of our target persona: a solo performance marketer managing multiple client portfolios. It details their day-to-day work, maps out their structural pain points, and defines how Oplyra provides a streamlined alternative.

---

## 1. Persona Profile
- **Name**: Akshay
- **Role**: Solo Freelancer & Performance Marketer
- **Client Count**: 10 clients (ranging from local service businesses to mid-sized e-commerce shops)
- **Workstations**: 1 Laptop, 2 Monitors, home office.

---

## 2. Chronological Day-in-the-Life (Current vs. Oplyra)

### A. Morning (8:00 AM - 9:30 AM)
*   **The Current Pain**:
    - Akshay opens his browser and checks 10 separate client Slack channels, WhatsApp messages, and Gmail threads.
    - He logs into Meta Ads Manager and Google Ads dashboard for all 10 accounts, looking for ad delivery problems, overspending, or drop-offs in conversions.
    - He reviews a manual, unstructured to-do list in Notion to figure out what needs attention today.
*   **The Oplyra Experience**:
    - Akshay opens Oplyra. The first screen he sees is the **Today Page** (`/`).
    - The screen greets him: *"Good Morning Akshay 👋. Here is your priority checklist for today."*
    - The checklist is dynamically generated based on pending task deadlines, client priorities, and system alerts (e.g., *"[Client ABC] Facebook Ad CTR dropped below 1.2% - Review Ad Copy"*).
    - **Clicks**: 1 click to open the application, immediately highlighting his daily tasks.

### B. Planning & Campaign Review (9:30 AM - 11:30 AM)
*   **The Current Pain**:
    - Checking SEO keyword ranks requires logging into Semrush or Ahrefs.
    - Checking Google Ads performance requires loading the heavy Google Ads UI, selecting the customer account, and querying date ranges.
    - If a client asks, "How are our summer campaigns doing?", Akshay has to navigate multiple browser tabs to gather numbers.
*   **The Oplyra Experience**:
    - Akshay clicks **Campaigns** in the sidebar. He selects the *“Summer Sale Campaign”* for *“ABC Furniture”*.
    - Inside this campaign dashboard, Oplyra displays aggregated views of SEO pages, Meta Ads drafts, Google Ads configurations, and files in one unified interface.
    - An AI-generated summary bullet tells him: *"SEO blog post draft is pending review. Google Search Console clicks are up 8% week-over-week. Facebook budget is pacing correctly."*
    - **Clicks**: 2 clicks (`Campaigns` → `ABC Furniture - Summer Sale`) to see the status.

### C. Creative Execution: Facebook & Google Ads Copy (11:30 AM - 1:30 PM)
*   **The Current Pain**:
    - Akshay needs to write new copy options for a Facebook Ad.
    - He opens ChatGPT, writes a prompt: *"Write 3 Facebook ad copy options for ABC Furniture summer sale..."*
    - ChatGPT generates generic text. Akshay has to write follow-ups: *"No, make it sound more professional. Include target audience: suburban homeowners. Keep it under 280 characters."*
    - He then copies the generated text, opens a Google Doc, formatting is lost, and he pastes it there to share with the client.
*   **The Oplyra Experience**:
    - From the campaign view, Akshay clicks **Tasks** → *"Draft Facebook Ad Copy"*.
    - He clicks **AI Assistant** next to the task. 
    - The AI Assistant panel slides out. It does not ask him for a prompt. Instead, it states: *"I have loaded the ABC Furniture Brand Kit (Color/Tone) and Summer Sale campaign details. Let's draft the Facebook Ad Copy."*
    - He clicks **Generate Copy Options**.
    - The AI generates 3 options instantly, respecting the brand kit tone guidelines.
    - Akshay clicks **Save to Campaign Assets**. The copy is saved directly under the campaign folder.
    - **Clicks**: 3 clicks (`View Task` → `AI Assistant` → `Generate & Save`) to produce brand-aligned ad options.

### D. SEO & Content Publishing (2:30 PM - 4:30 PM)
*   **The Current Pain**:
    - Akshay needs to write an SEO article for a local client to capture search intent.
    - He does keyword research in one tool, copies keywords, drafts the text in Word or Google Docs, and manually counts keyword density.
    - He runs a separate checklist to make sure title tags and meta descriptions are within length limits.
*   **The Oplyra Experience**:
    - Akshay goes to `Campaign` → `SEO` → **Create New Content**.
    - He selects `Type: Blog Post`. He inputs the target keyword (e.g. *"modern office furniture setup"*).
    - Oplyra autofills the Brand Kit profile. He clicks **Generate Article**.
    - The system runs the generation through the `AIGateway`, returning structured raw Markdown.
    - Once generated, Akshay clicks **Analyze SEO**. The system evaluates keyword frequency, readability, title tags, and meta length, showing visual badges (Green/Yellow/Red) in the right-side SEO panel.
    - He clicks **Export PDF** or **Sync to Web** to send it directly to the client's staging site.
    - **Clicks**: 3 clicks to generate, evaluate, and export an SEO-optimized blog article.

### E. Client Reporting & Communication (4:30 PM - 5:30 PM)
*   **The Current Pain**:
    - Generating weekly reports is a tedious chore. Akshay manually downloads CSV files from Meta Ads, Google Ads, and GA4.
    - He imports the numbers into Google Sheets, builds charts, writes summaries, and copies the charts into a PDF template or slides. This takes 45-60 minutes per client.
*   **The Oplyra Experience**:
    - Akshay navigates to **Reports** (`/reports`).
    - He selects the client name, chooses the date range (e.g. *Last 7 Days*), and clicks **Synthesize Weekly Report**.
    - Oplyra pulls the logged analytics, runs them through the `AIGateway` summarizing service to create professional insights, and outputs a formatted report.
    - Akshay reviews the draft and clicks **Download Client PDF**. The report is compiled and saved.
    - **Clicks**: 3 clicks (`Reports` → `Select Client` → `Synthesize & Export PDF`).

---

## 3. Screen-by-Screen Reference Table

The following table documents the user navigation pathways:

| Screen Name | Path | Core Question Addressed | Typical Actions | Clicks from Home |
|---|---|---|---|---|
| **Today Dashboard** | `/` | *What should I do today?* | Toggle task checkboxes, review priority warnings, view calendar schedule. | 0 |
| **Clients List** | `/clients` | *Who am I working for?* | Create/delete clients, view client company profiles, edit Brand Kits. | 1 |
| **Campaign Details** | `/campaigns/<id>` | *What am I managing?* | View budget tracking, access nested SEO/Ad assets, track task timelines. | 2 |
| **Task Management** | `/tasks` | *What needs to be completed?* | Create tasks, assign due dates, trigger context-aware AI helpers. | 1 |
| **AI Assistant Panel** | `/assistant` | *Help me complete this task.* | Generate copy, analyze SEO, rewrite content, track credit tokens used. | 1 |
| **Reports Portal** | `/reports` | *What should I send to my client?* | Pull campaign data, generate markdown summaries, export PDFs. | 1 |
| **Settings** | `/settings` | *How is the workspace configured?* | Manage user profile, configure API keys, update billing. | 1 |
