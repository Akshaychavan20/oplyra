# Oplyra Feature Decision Matrix

To ensure that Oplyra remains the simplest daily operating system for solo performance marketers and does not bloated into a complex, enterprise software suite, every new feature proposal must be run through this scoring rubric. 

Any feature failing to meet the passing threshold must be rejected.

---

## 1. Feature Evaluation Rubric

Every feature request must be evaluated against the following 6 core questions, each rated on a scale of 0 to 3.

### Core Metrics (Scale: 0-3)

#### 1. Work Reduction (WR)
- **Question**: Does this feature directly automate or reduce manual repetitive work for the solo marketer?
- **Scoring**:
  - `3`: Automates a multi-step task entirely (e.g., auto-formatting a PDF report from database inputs).
  - `2`: Reduces manual effort by at least 50% (e.g., keyword density checker highlighting words while typing).
  - `1`: Slightly simplifies a step, but user still performs the core task manually.
  - `0`: Does not reduce execution time or adds extra tracking steps.

#### 2. Click Reduction (CR)
- **Question**: Does it eliminate browser-tab hopping or tool-switching?
- **Scoring**:
  - `3`: Replaces an external application entirely (e.g., local preview of blog post vs copy-pasting to WordPress).
  - `2`: Reduces clicks required to execute the action within Oplyra down to 1 or 2 clicks.
  - `1`: Saves occasional clicks, but the user still needs multiple tabs open to cross-reference.
  - `0`: Adds more clicks, steps, or requires setting up complex configurations first.

#### 3. Client & Campaign Integration (CI)
- **Question**: Does it fit naturally inside our existing Campaign hierarchy, or does it require a new top-level database entity/menu?
- **Scoring**:
  - `3`: Purely nested under `Client` → `Campaign` (fits directly into campaign folders/notes).
  - `2`: Fits into an existing main menu option (e.g., `Today`, `Tasks`, `Reports`) with zero new database models.
  - `1`: Fits in settings or profile submenus, requiring minimal new database schemas.
  - `0`: Requires a new top-level database entity and an independent sidebar navigation entry.

#### 4. Frequency of Use (FU)
- **Question**: Will a solo performance marketer managing 10 clients use this feature every week?
- **Scoring**:
  - `3`: Used daily as part of the core checklist (e.g., checking Today tasks, writing ad copy).
  - `2`: Used weekly (e.g., sending weekly client performance reports, reviewing budgets).
  - `1`: Used once a month (e.g., updating client contracts, exporting historic data backups).
  - `0`: Used only during setup or once a year.

#### 5. Competitive Differentiation over General Q&A (CD)
- **Question**: Can ChatGPT/Claude already handle this task out-of-the-box without this tool?
- **Scoring**:
  - `3`: No. It requires rich local context, specific client campaign data, and local databases that external Q&A LLMs cannot access.
  - `2`: Partially. An LLM can write the copy, but Oplyra's value is auto-inserting the client's Brand Kit and keywords without the user prompting.
  - `1`: Yes, but having it local saves time copy-pasting.
  - `0`: Yes. The user can simply prompt any chat interface to get the same output (e.g., generic marketing tips).

---

## 2. Feature Scoring System & Equations

The Feature Score (FS) is calculated using the following formula:

$$\text{FS} = \text{WR} + \text{CR} + \text{CI} + \text{FU} + \text{CD}$$

Maximum possible score = **15**.

### Score Categories

| Score Range | Outcome | Action Required |
|---|---|---|
| **12 - 15** | **Approved** | Queue for immediate development. Fits the core vision. |
| **8 - 11** | **Pending Review** | Refine the feature. Simplify the interface. Nest it deeper in existing pages before building. |
| **0 - 7** | **Rejected** | Reject immediately. Out of scope or increases complexity. |

---

## 3. Rules to Reject Bloat

To protect usability, the Founder/CPO must enforce these rules:
1. **The Navigation Freeze**: No new top-level navigation items. If a feature does not fit in the existing sidebar elements (`Home`, `Clients`, `Campaigns`, `Tasks`, `AI Assistant`, `Reports`, `Settings`), it must be designed as a contextual sub-panel or rejected.
2. **The Integration Preference**: If a tool already exists (e.g., billing, invoicing, tracking pixels), do not build it. Integrate with Stripe, Meta API, or Google API.
3. **No Multi-User Complexity**: Reject any feature request that is built for "marketing agencies with roles" or "manager approvals." Oplyra is for *one solopreneur*. Do not add user invite loops or permissions tables that complicate the simple SQLite database structure.
