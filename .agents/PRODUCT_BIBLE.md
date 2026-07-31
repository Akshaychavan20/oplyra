# Oplyra Product Bible

This document is the absolute source of truth for the product strategy, vision, and core purpose of Oplyra. All features, designs, and architectural decisions must serve this document.

---

## 1. Mission
Build the world's simplest operating system for solo Performance Marketers and Freelancers. 

We do not build software for teams, enterprises, or large agencies. We build tools that help a single individual running campaigns from their laptop manage and complete their daily tasks.

---

## 2. Core Philosophy
> ChatGPT answers questions. **Oplyra helps users finish work.**

Solo marketers do not suffer from a lack of text generation tools. They suffer from fragmented workflows, context switching, and the daily cognitive load of managing multiple clients. Oplyra is designed as a workflow engine first, with AI integrated to accelerate task completion, rather than a conversational prompt interface.

---

## 3. Target User Profile (The Solo Marketer)
The application is designed specifically for:
- **Role**: Solo Freelancer / Performance Marketer.
- **Scale**: Managing **3 to 20 clients** simultaneously.
- **Core Services Offered**:
  - Facebook Ads (Meta Ads) management.
  - Google Ads management.
  - SEO keyword optimization, blogging, and technical audits.
  - Client weekly/monthly reporting.
  - Content copywriting and asset preparation.
  - Client communication and status management.
- **Constraints**: Works alone. Limited time. No design or engineering departments. Must handle accountancy, client acquisition, and execution by themselves.

---

## 4. Target Problems & Gaps
Solo marketers face three key challenges:
1. **The "What Should I Do Today?" Dilemma**: Managing tasks across 10 clients without a centralized daily plan causes cognitive fatigue and missed deadlines.
2. **Context Switching Overload**: Moving between Meta Ads Manager, Google Ads console, Semrush, Google Docs, Notion, Slack, and reporting dashboards.
3. **Execution Friction**: Taking a task (e.g., "Write SEO Blog post") and spending hours generating, copy-pasting, manually optimizing, and formatting it into PDFs or staging environments.

---

## 5. Unique Selling Proposition (USP) & Positioning
Oplyra is the **Daily Operating System**. 
- **Positioning vs. Competitors**: Unlike horizontal project managers (Notion, ClickUp) or broad AI assistants (ChatGPT, Claude), Oplyra is *nested campaign-aware*. It has full memory of client history, campaign budgets, active task backlogs, past content guidelines, and target audiences.
- **Key Advantage**: Contextual prompt injection. The user never starts with a blank prompt box. Oplyra knows exactly who the client is, what campaign is running, what the budget is, and feeds that data automatically to the underlying models.

---

## 6. Success Metrics
We measure the success of Oplyra using the following core metrics:
- **Weekly Active Days**: Solo freelancers should open the app every single working day.
- **Clicks to Complete Task**: Minimizing the steps between task assignment, AI generation, approval, and final export/execution (targeting < 3 clicks).
- **Time Saved per Campaign**: Calculated by reducing the hours spent building reports and writing ad copy.
- **Token Efficiency / Cost per Task**: Ensuring AIGateway cache hits are optimized to keep operation costs low.

---

## 7. Things We Never Build (Out of Scope)
To protect simplicity, we do NOT build:
- **CRM/Lead pipelines**: Use integrations instead.
- **Invoicing, Accounting, Payroll, or HR systems**: Already served by QuickBooks, Stripe, or Wave.
- **Ad Managers/Bid Optimizers**: We do not replace Meta Ads Manager or Google Ads bidding algorithms. We assist with copy, creatives, and performance reports.
- **Raw SEO databases**: We do not scrape Google or host multi-terabyte keyword databases. We integrate with existing SEO APIs or Google Search Console.

---

## 8. Things We Always Build
- **Unified Campaign Workflows**: Consolidating SEO, Facebook Ads, and Google Ads under a single Campaign entity.
- **Context-Aware AI Assistants**: Tools that generate assets based on pre-configured Client Brand Kits and Campaign Briefs.
- **Automated Client Reporting**: Drag-and-drop generators that synthesize campaign data into clean PDFs.
- **"Today's Work" Control Panel**: A prioritized checkboxes panel acting as the app homepage.

---

## 9. Product Principles
1. **Context Over Prompts**: The AI should already know the context. Never make the user type long instruction prompts.
2. **Three-Click Rule**: No core workflow action (e.g. creating a client, launching a campaign, exporting a report) should take more than three clicks.
3. **Zero Placeholder Policy**: Design layouts for real, long, and dynamic text. Never use text truncation that hides critical campaign insights.
4. **Offline Resilience**: Allow the freelancer to draft work offline. Sync cleanly when the internet is active.
5. **No AI for AI's Sake**: Do not add feature buttons (e.g., "AI brainstorming") unless they directly result in a concrete artifact (e.g., a drafted ad copy task).
