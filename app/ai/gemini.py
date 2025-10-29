import json
import asyncio
from pathlib import Path
from typing import Any

import google.generativeai as genai
from sanic.log import logger

from .. import settings, utils, models


TEMPLATES_DIR = Path(settings.ROOT) / "templates"


async def _call_gemini(prompt: str) -> dict | None:
    """Call the Google Gemini API to interpret a meme request.
    
    Returns a dictionary with meme parameters like:
    {
      "template_id": "fry",
      "text": ["top text","bottom text"],
      "font": "thick",
      "style": "default"
    }
    
    Returns None if the API call fails or the response can't be parsed.
    """
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    model_name = getattr(settings, "GEMINI_MODEL", "gemini-pro")

    if not api_key:
        logger.error("GEMINI_API_KEY not configured")
        return None

    try:
        # Configure the Gemini client
        genai.configure(api_key=api_key)

        # Generate response
        logger.info(f"Calling Gemini API with model: {model_name}")
        logger.info(f"Prompt: {prompt}")
        
        model = genai.GenerativeModel(model_name)
        
        # Use coroutines for async operation
        response = await asyncio.to_thread(model.generate_content, prompt)
        
        if not response.text:
            logger.error("Empty response from Gemini")
            return None

        # Get the response text and parse it as JSON
        response_text = response.text
        logger.info(f"Raw response text: {response_text}")
        
        # Find JSON in response (handle cases where model outputs additional text)
        try:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                result = json.loads(json_str)
                logger.info(f"Parsed result: {result}")
                return result
            else:
                logger.error("No JSON object found in response")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response as JSON: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        return None


def _build_prompt(query: str) -> str:
    """Create a compact prompt describing available templates, fonts, and expected output.

    Optimized for Gemini's JSON response format with clear instructions on output structure.
    """
    templates = []
    try:
        for p in sorted(TEMPLATES_DIR.iterdir()):
            if p.is_dir():
                templates.append(p.name)
    except Exception:
        templates = []

    fonts = []
    try:
        fonts_dir = Path(settings.ROOT) / "fonts"
        for f in sorted(fonts_dir.iterdir()):
            if f.suffix.lower() in {".ttf", ".ttc", ".otf"}:
                fonts.append(f.stem)
    except Exception:
        fonts = []

    # Build a compact but informative prompt for Gemini
    prompt = f"""As a meme generator, analyze this request and generate appropriate meme parameters.
Request: {query}

Instructions:
1. Choose from these templates: {", ".join(templates[:20])}... (more available)
2. Available fonts: {", ".join(fonts[:10])}... (more available)
3. Output must be valid JSON with this structure:
{{
    "template_id": "template_name",
    "text": ["top text", "bottom text"],
    "font": "font_name",
    "style": "default"
}}

Requirements:
- template_id must be a valid template from the list
- text should be 1-2 lines
- font should be from available fonts or omitted
- style is optional (default if omitted)

Please provide ONLY the JSON response, no additional text."""

    return prompt

    prompt = (
        f"You are a meme-generation assistant. Create a meme based on this request: \"{query}\"\n\n"
        f"Return ONLY a JSON object with these keys:\n"
        f"- template_id: Pick from [{', '.join(templates[:30])}]\n"
        f"- text: Array of 1-2 text lines for the meme\n"
        f"- font: One of [{', '.join(fonts[:10])}] (optional)\n"
        f"- style: Usually 'default' (optional)\n\n"
        f"Example response:\n"
        f'{{"template_id": "fry", "text": ["Not sure if code works", "Or I just got lucky"], "font": "thick"}}\n\n'
        f"Return ONLY the JSON, no other text."
    )
    return prompt


async def interpret_and_build_url(request, query: str) -> dict | None:
    """Interpret a natural-language query via Gemini and build a memegen URL.

    Returns the same structure as the existing automatic endpoint JSON response,
    e.g. {"url": ..., "generator": "gemini", "confidence": 0.9}
    or None on failure so callers can fallback to existing search.
    """
    prompt = _build_prompt(query)
    data = await _call_gemini(prompt)
    if not data:
        return None

    # Merge returned values conservatively
    template_id = data.get("template_id") or data.get("template")
    text = data.get("text") or data.get("lines") or []
    if isinstance(text, str):
        text = [text]
    font = data.get("font") or ""
    style = data.get("style") or "default"
    image_url = data.get("image_url") or data.get("background")

    # Build a memegen URL using existing model utilities
    if image_url:
        # Treat as custom background
        template = models.Template.objects.get_or_create(image_url)
        url = template.build_custom_url(request, text, background=image_url, style=style, font=font)
    elif template_id:
        template = models.Template.objects.get_or_create(template_id)
        url = template.build_custom_url(request, text, style=style, font=font)
        if not template.valid:
            # fallback
            return None
    else:
        # Nothing usable returned
        return None

    url, _updated = await utils.meta.tokenize(request, url)
    return {"url": url, "generator": "gemini", "confidence": float(data.get("confidence", 0.75))}
