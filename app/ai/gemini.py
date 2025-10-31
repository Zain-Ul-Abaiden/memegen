import json
import asyncio
from pathlib import Path
from typing import Any
import random

import google.generativeai as genai
from sanic.log import logger

from .. import settings, utils, models


TEMPLATES_DIR = Path(settings.ROOT) / "templates"
try:
    _LAST_TEMPLATE_ID  # type: ignore[name-defined]
except NameError:
    _LAST_TEMPLATE_ID = None  # type: ignore[assignment]
try:
    _LAST_EXTENSION  # type: ignore[name-defined]
except NameError:
    _LAST_EXTENSION = None  # type: ignore[assignment]


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
                for ext in ("png", "jpg", "jpeg", "gif", "webp"):
                    if (p / f"default.{ext}").exists():
                        templates.append(p.name)
                        extensions.add(ext)
                        break
    except Exception:
        templates = []
        extensions = set()
    if not templates:
        templates = [p.name for p in sorted(TEMPLATES_DIR.iterdir()) if p.is_dir()]
    # Always show all supported extensions to Gemini for variety, not just those found in templates
    extensions = {"png", "jpg", "gif", "webp"}

    fonts = []
    try:
        fonts_dir = Path(settings.ROOT) / "fonts"
        for f in sorted(fonts_dir.iterdir()):
            if f.suffix.lower() in {".ttf", ".ttc", ".otf"}:
                fonts.append(f.stem)
    except Exception:
        fonts = []

    # Note: double braces {{ }} below escape literal JSON braces in an f-string
    prompt = f"""
You are an expert meme generator with access to these real templates: {', '.join(templates)}.
Available fonts: {', '.join(fonts)}.
File types: {', '.join(extensions)}.

Instructions:
- If the user query directly names a template, font, style, or filetype/extension, you must use that if available.
- Some templates have multiple styles (style=<str>). Choose a valid style if context implies a variant (e.g., "animated"), otherwise omit or use "default".
- If the user provides only part of a meme (a single line or fragment), complete it into a sensible full meme using your knowledge and choose a fitting template.
- Always use ONLY the above template names/fonts/extensions, never invent new ones.
- If you cannot use the user's request exactly, select the closest valid option and ALWAYS return a meme generation result.
- IMPORTANT: For the "extension" field:
  * If user explicitly requests a file format (png, jpg, gif, webp), use that exact format
  * Otherwise, pick randomly from ALL available formats to provide variety - DO NOT default to png
  * Vary the extension each time for similar requests to provide different outputs

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
    
    logger.info(f"Gemini returned extension: {extension} for query")
    
    # Force variety: if Gemini returns png (common default), use fallback logic instead
    gemini_extension = extension
    extension = ""  # Reset to force fallback logic for variety

    allowed_templates = []
    try:
        from pathlib import Path
        allowed_templates = [p.name for p in sorted((Path(settings.ROOT) / "templates").iterdir()) if p.is_dir() and any((p / f"default.{ext}").exists() for ext in ("png", "jpg", "jpeg", "gif", "webp"))]
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

    # Helper to choose a valid extension when not specified, varying based on context
    def _choose_extension(meme_template_id: str = None, meme_text: list = None, prefer_animated: bool = False) -> str:
        static_exts = sorted(list(settings.ALLOWED_EXTENSIONS - settings.ANIMATED_EXTENSIONS))
        animated_exts = sorted(list(settings.ANIMATED_EXTENSIONS & settings.ALLOWED_EXTENSIONS))
        population = animated_exts if prefer_animated and animated_exts else static_exts or list(settings.ALLOWED_EXTENSIONS)
        
        # Use a context-based approach to add variety
        # Generate a hash from template and text to create consistent variety for similar memes
        if meme_template_id and meme_text:
            context_str = str(meme_template_id) + "".join(meme_text[:2] if meme_text else [])
            context_hash = abs(hash(context_str))
        else:
            context_str = None
            context_hash = random.randint(0, 1000)
        
        # Rotate through extensions based on context hash for variety
        # This ensures same meme gets different formats over time
        global _LAST_EXTENSION
        try:
            last = _LAST_EXTENSION
        except NameError:
            last = None
        
        # Create weighted choices - prefer different from last, but allow all options
        choices = [e for e in population if e != last] or population
        
        # Use context hash to select from available options deterministically
        # but add time-based randomness for variety
        selection_index = (context_hash + (hash(str(context_str)) % 100 if context_str else 0)) % len(choices)
        chosen = choices[selection_index] if choices else population[0] if population else "png"
        
        _LAST_EXTENSION = chosen
        return chosen

    # Build a memegen URL using existing model utilities
    if image_url:
        # Treat as custom background
        template = models.Template.objects.get_or_create(image_url)
        if not extension:
            extension = _choose_extension(template_id, text, style == "animated")
        url = template.build_custom_url(request, text, background=image_url, style=style, font=font, extension=extension)
    elif template_id:
        template = models.Template.objects.get_or_create(template_id)
        # Validate requested style; if invalid, fall back to default
        try:
            styles = template.styles
        except Exception:
            styles = []
        if style and style not in {"default", "animated"} and style not in styles:
            style = "default"
        # Avoid reusing the same template consecutively
        global _LAST_TEMPLATE_ID
        if _LAST_TEMPLATE_ID and template_id == _LAST_TEMPLATE_ID and allowed_templates:
            alts = [t for t in allowed_templates if t != template_id]
            if alts:
                template_id = random.choice(alts)
                template = models.Template.objects.get_or_create(template_id)
        if not extension:
            extension = _choose_extension(template_id, text, style == "animated")
        url = template.build_custom_url(request, text, style=style, font=font, extension=extension)
        if not template.valid:
            # Try fallback template, if not already tried
            import difflib
            valid_templates = [t for t in allowed_templates if t != template_id]
            fallback = difflib.get_close_matches(template_id, valid_templates, n=1)
            if fallback:
                template_id = fallback[0]
                template = models.Template.objects.get_or_create(template_id)
                if not extension:
                    extension = _choose_extension(template_id, text, style == "animated")
                url = template.build_custom_url(request, text, style=style, font=font, extension=extension)
                used_fallback = True
            elif valid_templates:
                template_id = valid_templates[0]
                template = models.Template.objects.get_or_create(template_id)
                if not extension:
                    extension = _choose_extension(template_id, text, style == "animated")
                url = template.build_custom_url(request, text, style=style, font=font, extension=extension)
                used_fallback = True
            else:
                return None
    else:
        # Nothing usable returned
        return None

    url, _updated = await utils.meta.tokenize(request, url)
    _LAST_TEMPLATE_ID = template_id or _LAST_TEMPLATE_ID
    if used_fallback:
        logger.warning(f"Gemini requested invalid template '{original_template}', using fallback '{template_id}' instead.")
    return {"url": url, "generator": "gemini", "confidence": float(data.get("confidence", 0.75))}
