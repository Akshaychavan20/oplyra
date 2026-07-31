import os
import time
import re
from google import genai
from google.genai import types
from google.genai.errors import APIError
from flask import current_app

def generate_content(prompt, system_instruction=None, api_key=None, model=None):
    """Sends a prompt to the Google Gemini API, handles error statuses, and returns (response_text, token_usage)."""
    
    # 1. Fetch API Key securely if not explicitly provided
    if not api_key:
        try:
            # Check if inside Flask application context
            if current_app:
                api_key = current_app.config.get('GEMINI_API_KEY')
        except RuntimeError:
            # Outside Flask application context (e.g. running scripts)
            pass
            
        if not api_key:
            api_key = os.environ.get('GEMINI_API_KEY')

        # Never accept client-supplied API keys (headers/form) — server config only.

    # 2. Check for missing/empty API key
    if not api_key or not api_key.strip():
        raise ValueError(
            "Gemini API Key is missing. Configure GEMINI_API_KEY on the server (.env)."
        )

    # 3. Dynamic Mock mode fallback if dummy/placeholder key is present
    if api_key == "your_gemini_api_key_here" or api_key.startswith("your_"):
        time.sleep(1.0) # Simulate API latency
        
        prompt_lower = str(prompt).lower()
        
        # Regex parsers to dynamically pull inputs from the generated prompt structure
        topic_match = re.search(r"(?:Topic/Title|Email Campaign Topic/Focus|Core Campaign Focus):\s*(.*)", prompt, re.IGNORECASE)
        product_match = re.search(r"(?:Featured Product to promote|Product Name):\s*(.*)", prompt, re.IGNORECASE)
        keywords_match = re.search(r"(?:Target Keywords to naturally integrate|Target Keywords to integrate|Target Keywords):\s*(.*)", prompt, re.IGNORECASE)
        audience_match = re.search(r"(?:Target Reader Audience|Target Audience):\s*(.*)", prompt, re.IGNORECASE)
        tone_match = re.search(r"Tone of Voice:\s*(.*)", prompt, re.IGNORECASE)
        
        topic = topic_match.group(1).strip() if topic_match and topic_match.group(1).strip() else "Top Content Marketing Strategy"
        product_name = product_match.group(1).strip() if product_match and product_match.group(1).strip() else "Oplyra Pro"
        keywords = keywords_match.group(1).strip() if keywords_match and keywords_match.group(1).strip() else "marketing, content creation"
        audience = audience_match.group(1).strip() if audience_match and audience_match.group(1).strip() else "affiliate marketers"
        tone = tone_match.group(1).strip() if tone_match and tone_match.group(1).strip() else "persuasive"
        
        if 'blog' in prompt_lower:
            mock_text = f"""# {topic}

Welcome to our deep dive into the world of **{product_name}**. If you are looking for a solution that caters specifically to **{audience}**, you have come to the right place. In this article, we will outline why this is a game-changer and how it integrates key aspects of **{keywords}** to deliver a top-tier experience.

## Why {product_name} is a Game Changer
When evaluating products in this space, several factors come to mind. Written in a **{tone}** style, here are the key reasons why this product stands out:
1. **Targeted Design**: Tailored specifically to meet the high demands of **{audience}**.
2. **Feature Set**: Built to highlight the core concepts of **{keywords}** without compromise.
3. **Reliable Performance**: Consistently delivers quality results under real-world conditions.

## Key Features & Practical Breakdown
Whether you are a beginner or a seasoned professional, the ease of use and robustness of **{product_name}** will impress you. By focusing on **{keywords}**, the developers have ensured that every user can maximize their output.

## Summary & Next Steps
In summary, if you want to elevate your workspace and get the most out of your campaigns, **{product_name}** is highly recommended. It hits all the marks for **{audience}**.

**Call to Action:** Ready to take the next step? [Check out the official page for {product_name} here] and get started today!"""
        elif 'email' in prompt_lower:
            mock_text = f"""Subject Options:
1. Boost your results with {product_name} - Today!
2. Why {audience} are choosing {product_name}
3. Exclusive: Discover the power of {keywords} inside {product_name}

Pre-header: The ultimate guide for {audience} to achieve success using {product_name}.

Dear Reader,

If you are a part of the **{audience}** community, you know how challenging it can be to find tools that match your standards.

That is why we are excited to introduce **{product_name}**.

Designed to address your specific needs with a focus on **{keywords}**, this is the upgrade you have been waiting for. We are sharing this with you in a **{tone}** spirit because we believe it can transform your workflow.

Here is what you get:
- High efficiency tailored for **{audience}**.
- Direct integration of **{keywords}** for maximum impact.
- Exceptional durability and premium quality.

Don't wait! This offer is only available for a limited time.

[Insert Affiliate Link Here - Buy {product_name} Now]

Best regards,
The Oplyra Team"""
        elif 'facebook' in prompt_lower or 'fb' in prompt_lower or 'social' in prompt_lower:
            hashtag_prod = product_name.replace(" ", "")
            hashtag_aud = audience.replace(" ", "")
            hashtag_kw = keywords.split(',')[0].strip().replace(" ", "") if ',' in keywords else keywords.replace(" ", "")
            
            mock_text = f"""🚀 Transforming the game for **{audience}**! 🌟

Meet the all-new **{product_name}** - the ultimate choice for anyone looking to master **{keywords}**. 

We are sharing this in a **{tone}** style because the results speak for themselves:
✅ Tailored specifically for **{audience}**
✅ Highly optimized for **{keywords}**
✅ Premium build and design

What is your favorite feature of **{product_name}**? Let us know in the comments below! 👇

👉 Click the link to grab yours today: [Insert Affiliate Link Here]

#Review #{hashtag_prod} #{hashtag_kw} #{hashtag_aud} #Oplyra"""
        else:
            mock_text = f"""# Detailed Review: Is {product_name} Really Worth It?

Today, we are taking a close look at **{product_name}** to see if it lives up to the hype for **{audience}**. Written with a **{tone}** perspective, here is our honest verdict.

## Standout Features
- **Keyword Integration**: Fully leverages **{keywords}** to deliver maximum productivity.
- **Audience Focus**: Every aspect is optimized for **{audience}**.

## Pros & Cons

### Pros:
- Exceptionally high build quality.
- Integrates **{keywords}** naturally.
- Perfect fit for **{audience}**.

### Cons:
- Higher price point than entry-level models.
- Slight learning curve for beginners.

## Overall Rating
Rating: **4.8 / 5 Stars**

## Verdict
For **{audience}** members looking to take their projects to the next level, **{product_name}** is an outstanding investment. It is highly recommended!

[Buy {product_name} Here - Best Price Online]"""
            
        token_count = len(prompt.split()) + len(mock_text.split())
        return mock_text, token_count
    
    max_retries = 4
    retry_delay = 10.0
    
    for attempt in range(max_retries):
        try:
            # 4. Initialize the latest google-genai Client
            client = genai.Client(api_key=api_key)
            
            # We target the requested model or fallback to the centralized default
            from app.services.ai_gateway import DEFAULT_MODEL
            model_name = model if model else DEFAULT_MODEL
            
            # 5. Configure system instructions if provided
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction
                )
                
            # 6. Request generation from Gemini
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            
            # 7. Check for empty response
            if not response or not response.text:
                raise ValueError("Received an empty response from Gemini API.")
                
            # 8. Retrieve token usage
            token_count = 0
            if response.usage_metadata:
                token_count = response.usage_metadata.total_token_count
            else:
                # Word-count fallback estimation
                token_count = len(prompt.split()) + len(response.text.split())
                
            return response.text, token_count
            
        except APIError as e:
            # Check for transient errors (503 Service Unavailable, 429 Rate Limit)
            if e.code in [503, 429] and attempt < max_retries - 1:
                try:
                    current_app.logger.warning(f"Gemini API returned transient error {e.code}. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                except Exception:
                    print(f"Gemini API returned transient error {e.code}. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
                
            # Detect Rate Limit (HTTP 429) specifically or general API failures
            if e.code == 429:
                raise RuntimeError(f"Gemini API Rate Limit Exceeded. Please wait a moment before trying again: {str(e)}")
            else:
                raise RuntimeError(f"Gemini API failure (HTTP code {e.code}): {str(e)}")
        except ValueError as ve:
            # Propagate validation errors (empty response, missing config)
            raise ve
        except Exception as e:
            if attempt < max_retries - 1:
                try:
                    current_app.logger.warning(f"Unexpected error {str(e)}. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                except Exception:
                    print(f"Unexpected error {str(e)}. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            # General catch-all wrapper
            raise RuntimeError(f"Unexpected error calling Gemini API: {str(e)}")
