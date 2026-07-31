import os
from flask import current_app
from flask_login import current_user
from app.services.ai_gateway import AIGateway, DEFAULT_MODEL

class GeminiService:
    """Service class interfacing with AIGateway to generate marketing assets with minimal token footprint."""
    
    def __init__(self, api_key=None):
        # Prefer explicit arg, then Flask config (source of truth in-context),
        # then raw environment. Config-first lets testing force mock mode.
        self.api_key = api_key
        if not self.api_key:
            try:
                if current_app:
                    self.api_key = current_app.config.get('GEMINI_API_KEY')
            except RuntimeError:
                pass
        if not self.api_key:
            self.api_key = os.environ.get('GEMINI_API_KEY')
        
        self.gateway = AIGateway(api_key=self.api_key)
        self.last_prompt = None
        self.last_system_instruction = None

    def _generate(self, prompt, system_instruction=None, model=None):
        """Internal helper forwarding to the centralized AI Gateway."""
        self.last_prompt = prompt
        self.last_system_instruction = system_instruction
        
        # Determine active user ID from Flask login context
        user_id = None
        provider = None
        try:
            if current_user and current_user.is_authenticated:
                user_id = current_user.id
                # Honor user Auto / preferred provider when no explicit model override
                if not model:
                    from app.models import UserAIPreference
                    prefs = UserAIPreference.query.filter_by(user_id=user_id).first()
                    if prefs and prefs.preferred_provider:
                        provider = prefs.preferred_provider
                        if prefs.preferred_model and prefs.preferred_provider != 'auto':
                            model = prefs.preferred_model
        except Exception:
            pass

        try:
            return self.gateway.generate(
                prompt=prompt,
                system_instruction=system_instruction,
                model=model,
                provider=provider,
                user_id=user_id
            )
        except Exception as e:
            try:
                current_app.logger.error(f"AI Gateway Exception: {str(e)}")
            except Exception:
                pass
            raise RuntimeError(str(e))

    def generate_blog(self, topic, keywords, audience, tone, product_name=None, length=None, cta=None, model=None):
        """Generates a structured, SEO-friendly blog post article using optimized prompts."""
        system_instruction = (
            "You are a professional, world-class SEO copywriter and marketing strategist. "
            "Write with absolute authority, avoiding fluff, hype, or robotic transitions. "
            "Output raw Markdown directly (do NOT wrap the output in markdown code block fences)."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Write a structured, engaging blog article.
        Topic: {topic}
        {f'Product to promote: {product_name}' if product_name else ''}
        Keywords to naturally integrate: {keywords_str}
        Reader Audience: {audience}
        Tone: {tone}
        Length: {length if length else '800 to 1200 words'}
        CTA Preference: {cta if cta else 'persuasive final call-to-action'}
        
        Instructions:
        1. Contextually integrate keywords. Do not repeat terms or audience names.
        2. Use clear H2 and H3 subheadings for sections.
        3. End with a complete, conversion-focused CTA sentence (do not use generic bracket placeholders).
        """
        
        # Route to optimal blog model (centralized DEFAULT_MODEL)
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_email(self, product_name, keywords, audience, tone, topic=None, length=None, cta=None, model=None):
        """Generates high-converting promotional marketing emails."""
        system_instruction = (
            "You are a direct-response email copywriter who builds trust and drives action. "
            "Output raw Markdown directly (do NOT wrap output in markdown code fences)."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Write a benefit-driven marketing email.
        Product: {product_name}
        {f'Focus: {topic}' if topic else ''}
        Keywords: {keywords_str}
        Audience: {audience}
        Tone: {tone}
        Length: {length if length else 'Standard email length'}
        CTA Preference: {cta if cta else 'Click through CTA'}
        
        Instructions:
        1. Provide exactly three subject line options and one pre-header.
        2. Write a conversational email body. Highlight product benefits for user pain points.
        3. Use a friendly greeting and professional sign-off. Include a complete, realistic click link (no brackets).
        """
        
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_facebook_post(self, product_name, keywords, audience, tone, topic=None, length=None, cta=None, model=None):
        """Generates engaging social media copy optimized for Facebook reach."""
        system_instruction = (
            "You are an expert social media manager. Write punchy, authentic, shareable social media posts. "
            "Output raw Markdown directly."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Create a Facebook post.
        Product: {product_name}
        {f'Campaign Theme: {topic}' if topic else ''}
        Keywords: {keywords_str}
        Audience: {audience}
        Tone: {tone}
        Length: {length if length else 'Short ad post'}
        CTA: {cta if cta else 'Actionable CTA link'}
        
        Instructions:
        1. Start with an immediate, engaging hook.
        2. Use concise, mobile-friendly sentences with line breaks and appropriate emojis.
        3. End with a complete purchase link followed by 3-5 relevant hashtags.
        """
        
        # Route to cheapest model for social media posts (centralized DEFAULT_MODEL)
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_product_review(self, product_name, keywords, audience, tone, length=None, cta=None, model=None):
        """Generates detailed, honest-looking affiliate product reviews."""
        system_instruction = (
            "You are an independent product review editor providing balanced, objective assessments. "
            "Output raw Markdown directly."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Write an objective product review.
        Product: {product_name}
        Keywords: {keywords_str}
        Audience: {audience}
        Tone: {tone}
        Length: {length if length else 'Detailed review length'}
        CTA: {cta if cta else 'Buy Link'}
        
        Structure:
        1. Title & Introduction.
        2. Standout features with real-world performance context.
        3. Direct comparison against 2 competitors.
        4. Objective bullet-point Pros & Cons.
        5. Star rating and final buy recommendation with a complete URL link.
        """
        
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_carousel(self, product_name, keywords, audience, tone, topic=None, length=None, cta=None, model=None):
        """Generates a multi-slide social media carousel deck."""
        system_instruction = (
            "You are a master of visual social storytelling, designing step-by-step carousels. "
            "Output raw Markdown directly."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Design a multi-slide carousel.
        Product: {product_name}
        Focus: {topic if topic else 'Benefit breakdown'}
        Keywords: {keywords_str}
        Audience: {audience}
        Tone: {tone}
        Length: {length if length else '5 slides'}
        CTA: {cta if cta else 'Follow for more'}
        
        Instructions:
        1. Format as: "Slide [number]: [title]" followed by short slide text.
        2. Describe visual graphic recommendations in brackets on each slide.
        3. Slide 1 must be an attention-grabbing hook. Final slide must contain the CTA.
        """
        
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_video_script(self, product_name, keywords, audience, tone, topic=None, length=None, cta=None, model=None):
        """Generates engaging video storyboard and narration script (TikTok/Shorts)."""
        system_instruction = (
            "You are a professional video producer. Output raw Markdown directly."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Write a short-form video script storyboard.
        Product: {product_name}
        Focus: {topic if topic else 'Tutorial'}
        Keywords: {keywords_str}
        Audience: {audience}
        Tone: {tone}
        Duration: {length if length else '30 seconds'}
        CTA: {cta if cta else 'Link in bio'}
        
        Instructions:
        1. Format as a table/alternating segments of [Visual Scene Description] and Narration.
        2. Start with a 3-second visual hook. Keep pacing fast and conversational.
        3. End with a visual overlay indicator of the CTA.
        """
        
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_image_prompt(self, product_name, keywords, topic=None, model=None):
        """Generates detailed, realistic descriptive prompts for image synthesis."""
        system_instruction = (
            "You are a professional AI generative artist. Output raw text directly."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Create an image prompt for Stable Diffusion XL / Midjourney.
        Subject: {product_name}
        Context: {topic if topic else 'Photorealistic'}
        Keywords: {keywords_str}
        
        Instructions:
        Provide exactly 2 variations of a detailed prompt paragraph specifying camera angles, lighting, background, and rendering style:
        Variation 1: Photo-realistic style.
        Variation 2: Futuristic digital art style.
        """
        
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)

    def generate_ad_copy(self, product_name, keywords, audience, tone, topic=None, length=None, cta=None, model=None):
        """Generates growth marketing ad headlines and body copy options."""
        system_instruction = (
            "You are a senior growth copywriter. Output raw Markdown directly."
        )
        
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        prompt = f"""
        Generate high-CTR marketing ad copies.
        Product: {product_name}
        Focus: {topic if topic else 'Promo offer'}
        Keywords: {keywords_str}
        Audience: {audience}
        Tone: {tone}
        CTA: {cta if cta else 'Shop Now'}
        
        Instructions:
        1. Provide exactly three headline options.
        2. Provide exactly two variations of body copy (one short and punchy, one long-form story format).
        3. List clear CTA button copy for each option.
        """
        
        model_target = model if model else DEFAULT_MODEL
        return self._generate(prompt, system_instruction, model=model_target)
