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
    """Create a compact prompt describing available templates, fonts, filetypes, and expected output.
    List only valid templates (those with default.png, default.jpg, or default.gif).
    """
    templates = []
    extensions = set()
    try:
        for p in sorted(TEMPLATES_DIR.iterdir()):
            if p.is_dir():
                for ext in ("png", "jpg", "jpeg", "gif"):  # Add others if supported
                    if (p / f"default.{ext}").exists():
                        templates.append(p.name)
                        extensions.add(ext)
                        break
    except Exception:
        templates = []
        extensions = set()
    if not templates:
        templates = [p.name for p in sorted(TEMPLATES_DIR.iterdir()) if p.is_dir()]
    if not extensions:
        extensions = {"png", "jpg", "gif"}

    fonts = []
    try:
        fonts_dir = Path(settings.ROOT) / "fonts"
        for f in sorted(fonts_dir.iterdir()):
            if f.suffix.lower() in {".ttf", ".ttc", ".otf"}:
                fonts.append(f.stem)
    except Exception:
        fonts = []

    prompt = f"""
You are an expert meme generator with access to these real templates: {', '.join(templates)}.
Available fonts: {', '.join(fonts)}.
File types: {', '.join(extensions)}.

Instructions:
- If the user query directly names a template, font, or filetype/extension, you must use that if available.
- Otherwise, pick the most contextually appropriate values.
- Always use ONLY the above template names/fonts/extensions, never invent new ones.
- If you cannot use the user's request exactly, select the closest valid option and always return a meme generation result.

Return only valid JSON with this structure:
{{
    "template_id": "template_name",
    "text": ["top text", "bottom text"],
    "font": "font_name",
    "extension": "filetype",
    "style": "default"
}}
All fields above are required except font and style (style defaults to 'default' if missing).
template_id, font, and extension must match items given in the lists above.

Request: {query}

Only provide the JSON response, no extra text, markdown, or comments.
"""
    return prompt


async def interpret_and_build_url(request, query: str) -> dict | None:
    """Interpret a natural-language query via Gemini and build a memegen URL.

    Always generate a meme if at all possible, using the closest valid template if directly requested one isn't available.
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
    extension = data.get("extension") or ""
    image_url = data.get("image_url") or data.get("background")

    allowed_templates = []
    try:
        from pathlib import Path
        allowed_templates = [p.name for p in sorted((Path(settings.ROOT) / "templates").iterdir()) if p.is_dir() and any((p / f"default.{ext}").exists() for ext in ("png", "jpg", "jpeg", "gif"))]
    except Exception:
        allowed_templates = []

    used_fallback = False
    original_template = template_id
    if template_id and (template_id not in allowed_templates):
        # Fallback to closest valid by string similarity or just pick first valid one
        import difflib
        matches = difflib.get_close_matches(template_id, allowed_templates, n=1)
        if matches:
            template_id = matches[0]
        elif allowed_templates:
            template_id = allowed_templates[0]
        used_fallback = True

    # Build a memegen URL using existing model utilities
    if image_url:
        # Treat as custom background
        template = models.Template.objects.get_or_create(image_url)
        url = template.build_custom_url(request, text, background=image_url, style=style, font=font, extension=extension)
    elif template_id:
        template = models.Template.objects.get_or_create(template_id)
        url = template.build_custom_url(request, text, style=style, font=font, extension=extension)
        if not template.valid:
            # Try fallback template, if not already tried
            import difflib
            valid_templates = [t for t in allowed_templates if t != template_id]
            fallback = difflib.get_close_matches(template_id, valid_templates, n=1)
            if fallback:
                template_id = fallback[0]
                template = models.Template.objects.get_or_create(template_id)
                url = template.build_custom_url(request, text, style=style, font=font, extension=extension)
                used_fallback = True
            elif valid_templates:
                template_id = valid_templates[0]
                template = models.Template.objects.get_or_create(template_id)
                url = template.build_custom_url(request, text, style=style, font=font, extension=extension)
                used_fallback = True
            else:
                return None
    else:
        # Nothing usable returned
        return None

    url, _updated = await utils.meta.tokenize(request, url)
    if used_fallback:
        logger.warning(f"Gemini requested invalid template '{original_template}', using fallback '{template_id}' instead.")
    return {"url": url, "generator": "gemini", "confidence": float(data.get("confidence", 0.75))}
