# Oplyra AI Principles

This document defines the constraints, model routing heuristics, prompting standards, and cost optimization rules governing artificial intelligence in Oplyra.

---

## 1. The Role of AI

> AI is an assistant, **never the center** of the application. The workflow remains the core product.

We do not design conversational Q&A interfaces that look like ChatGPT. Oplyra uses AI strategically to automate background tasks, generate structured ad layouts, conduct page-specific SEO auditing, and compile client reports. AI is integrated directly into workflow steps so that the freelancer does not have to worry about prompts.

---

## 2. Model Selection & Heuristics

The application routes requests dynamically using different models depending on speed, accuracy, context window, and API costs:

| Model Target | Ideal Use Case | Cost Profile | Default Allocation |
|---|---|---|---|
| **Gemini 1.5 Flash** | Copywriting, ad slogans, email drafts, SEO content generation. | Low | Primary generation model |
| **Gemini 1.5 Pro** | Deep analytics report summaries, multi-source campaigns analysis, code audits. | Medium-High | Complex analytics & summaries |
| **Gemini 1.5 Flash (8B)** | Text classification, quick title tag cleanups, tone changes. | Extremely Low | Minor post-processing tweaks |

---

## 3. Prompt Engineering Standards

All prompts must follow these structural guidelines:
1. **System Instructions separation**: Always set roles and core output guidelines using `system_instruction` parameter rather than mixing them into the user prompt.
2. **Raw Outputs**: Force models to output clean, raw Markdown strings instead of wrapping generations in ```markdown ... ``` blocks. This reduces parsing errors.
3. **Inject Context Automatically**: The prompt builder must pull in the user's saved client data, brand voice tone, target keyword list, and target persona without the user typing them out.
4. **Token Footprint Control**: Explicitly ask the model to avoid generic greeting phrases, intro/outro paragraphs, or repetitive transitions (e.g., "In this blog post, we will...").

---

## 4. Cache, Cost & Credit Management

To ensure that the SaaS tier limits remain sustainable:
- **Cached Identifiers**: `AIGateway` hashes the combined `prompt`, `system_instruction`, and `model` string. If a cache hit is found inside Redis or SQLite, the system returns the cached string instantly (saving token expenses).
- **Graceful Retries**: Call APIs using exponential backoff to handle rate limits (`ResourceExhausted` errors) without crashing the interface.
- **Credit Limit Checks**: The gateway must check the current user's monthly credits limit before calling the API. If credits are exhausted, raise a clean error message directing the user to upgrade.

---

## 5. Context Memory Management

When using the **AI Assistant** for interactive task completion:
- **Maximum Context Window**: Never pass the entire historic content log. Limit the memory context payload to the last 5 task interactions.
- **Structured JSON schemas**: For classification or SEO auditing tasks, use structured JSON schema declarations (`response_mime_type="application/json"`) to ensure data formats are consistent and easily parsed by the service controllers.
