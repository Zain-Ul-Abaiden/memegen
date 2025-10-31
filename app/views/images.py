import asyncio
import re

from sanic import Blueprint, exceptions, response
import random
from sanic.log import logger
from sanic.request import Request
from sanic_ext import openapi

from .. import helpers, settings, utils
from ..models import Template
from .helpers import render_image
from .schemas import (
    AutomaticRequest,
    CustomRequest,
    ErrorResponse,
    ExampleResponse,
    MemeRequest,
    MemeResponse,
)
from .templates import generate_url
from ..ai import gemini

blueprint = Blueprint("Images", url_prefix="/images")

security = {settings.API_KEY_HEADER: []} if settings.API_KEY_HEADER else None

# Rotate output file formats when not specified by the user
try:
    _LAST_EXTENSION  # type: ignore[name-defined]
except NameError:
    _LAST_EXTENSION = None  # type: ignore[assignment]
try:
    _LAST_TEMPLATE_ID  # type: ignore[name-defined]
except NameError:
    _LAST_TEMPLATE_ID = None  # type: ignore[assignment]

def _choose_extension(prefer_animated: bool = False) -> str:
    static_exts = sorted(list(settings.ALLOWED_EXTENSIONS - settings.ANIMATED_EXTENSIONS))
    animated_exts = sorted(list(settings.ANIMATED_EXTENSIONS & settings.ALLOWED_EXTENSIONS))
    population = animated_exts if prefer_animated and animated_exts else static_exts or list(settings.ALLOWED_EXTENSIONS)
    global _LAST_EXTENSION
    last = _LAST_EXTENSION
    choices = [e for e in population if e != last] or population
    chosen = random.choice(choices)
    _LAST_EXTENSION = chosen
    return chosen

@blueprint.get("/")
@openapi.summary("List example memes")
@openapi.parameter(
    "filter", str, "query", description="Part of the template name or example to match"
)
@openapi.response(
    200,
    {"application/json": list[ExampleResponse]},
    "Successfully returned a list of example memes",
)
async def index(request: Request):
    query = request.args.get("filter", "").lower()
    examples = await asyncio.to_thread(helpers.get_example_images, request, query)
    return response.json(
        [{"url": url, "template": template} for url, template in examples]
    )

@blueprint.post("/")
@openapi.summary("Create a meme from a template")
@openapi.body({"application/json": MemeRequest})
@openapi.response(
    201, {"application/json": MemeResponse}, "Successfully created a meme"
)
@openapi.response(
    400,
    {"application/json": ErrorResponse},
    'Required "template_id" missing in request body',
)
@openapi.response(
    404, {"application/json": ErrorResponse}, 'Specified "template_id" does not exist'
)
async def create(request: Request):
    return await generate_url(request, template_id_required=True)

@blueprint.post("/automatic")
@openapi.secured(security)
@openapi.summary("Create a meme using AI interpretation of natural language")
@openapi.description(
    "Send a natural language description of the meme you want to create. "
    "The AI will interpret your request and choose an appropriate template, text, and style. "
    "Example: 'Create a Fry meme about being confused if code is working or not'"
)
@openapi.body({"application/json": AutomaticRequest})
@openapi.response(
    201,
    {"application/json": MemeResponse},
    "Successfully created a meme. Response includes the meme URL and AI confidence score"
)
@openapi.response(
    400, {"application/json": ErrorResponse}, 'Required "text" missing in request body'
)
@openapi.response(
    404, {"application/json": ErrorResponse}, "No matching templates found for the request"
)
async def create_automatic(request: Request):
    if request.form:
        payload = dict(request.form)
    else:
        try:
            payload = request.json or {}
        except exceptions.InvalidUsage:
            payload = {}

    try:
        query = payload["text"]
    except KeyError:
        return response.json({"error": '"text" is required'}, status=400)
    # First try to interpret the natural-language query with Gemini (if configured).
    try:
        logger.info(f"Attempting Gemini interpretation for query: {query}")
        ai_result = await gemini.interpret_and_build_url(request, query)
        logger.info(f"Gemini result: {ai_result}")
    except Exception as e:
        logger.error(f"Gemini interpretation failed: {str(e)}")
        ai_result = None

    if ai_result:
        # Gemini returned a ready URL (or confidence). Return it directly.
        logger.info(f"Using Gemini-generated meme URL: {ai_result}")
        return response.json(
            {"url": ai_result["url"], "generator": ai_result.get("generator", "gemini"), "confidence": ai_result.get("confidence", 0.75)},
            status=201,
        )

    # Skip using previously generated images; select a template directly based on context
    templates = await asyncio.to_thread(helpers.get_valid_templates, request, query, None)
    if not templates:
        # broaden search to all valid templates if no match
        templates = await asyncio.to_thread(helpers.get_valid_templates, request, "", None)
        if not templates:
            return response.json({"message": f"No results matched: {query}"}, status=404)
    # Choose a template randomly, avoiding repeating the last one
    global _LAST_TEMPLATE_ID
    ids = [t["id"] for t in templates if t.get("id")]
    pool = [i for i in ids if i != _LAST_TEMPLATE_ID] or ids
    fallback_template_id = random.choice(pool)
    _LAST_TEMPLATE_ID = fallback_template_id

    # Pre-clean the query: remove boilerplate directives and template hints
    working_query = query.translate(str.maketrans({
        "“": '"', "”": '"', "‘": "'", "’": "'", "«": '"', "»": '"',
    }))
    cleanup_patterns = [
        r"^\s*(create|make|generate|build)\s+(a|an)?\s*meme\b[:,-]*\s*",
        r"\b(meme\s+about)\b\s*",
        r"\b(use|using)\s+[^\s]+\s+template\b",
        r"\btemplate\b",
        r"\bplease\b",
    ]
    for pat in cleanup_patterns:
        working_query = re.sub(pat, "", working_query, flags=re.IGNORECASE)
    working_query = re.sub(r"\s+", " ", working_query).strip(" -:;., ")

    # Split the query into up to two lines (heuristics)
    text_lines: list[str]
    match = re.search(r'"([^"]+)"|\'([^\']+)\'', working_query)
    if match:
        quoted = (match.group(1) or match.group(2) or "").strip()
        prefix = (working_query[: match.start()] + working_query[match.end() :]).strip()
        prefix = re.sub(r"\s+", " ", prefix).strip(" -:;.,")
        if prefix:
            text_lines = [prefix, quoted]
        else:
            text_lines = [quoted]
    else:
        qpos = working_query.find("?")
        if qpos != -1:
            left = working_query[:qpos].strip()
            right = working_query[qpos:].strip()
            lower_left = left.lower()
            if " another " in lower_left:
                left = left[: lower_left.index(" another ")].strip(" -:;.,") or left
            text_lines = [left, right] if left and right else [working_query]
        else:
            parts = re.split(r"\s*[:;\-—]\s*", working_query, maxsplit=1)
            if len(parts) == 2:
                left, right = parts
                text_lines = [left.strip(), right.strip()] if right.strip() else [left.strip()]
            else:
                split_alt = re.split(r"\banother\b", working_query, maxsplit=1, flags=re.IGNORECASE)
                if len(split_alt) == 2:
                    left, right = split_alt
                    text_lines = [left.strip(), right.strip()]
                else:
                    words = working_query.split()
                    if len(words) > 12:
                        mid = len(words) // 2
                        text_lines = [" ".join(words[:mid]), " ".join(words[mid:])]
                    else:
                        text_lines = [working_query]

    max_chars = 80
    text_lines = [line[:max_chars].rstrip() for line in text_lines if line]

    chosen_ext = _choose_extension(False)
    url = request.app.url_for(
        "Images.detail_text",
        template_id=fallback_template_id,
        text_filepath=utils.text.encode(text_lines) + "." + chosen_ext,
        _external=True,
        _scheme=settings.SCHEME,
    )
    url, _updated = await utils.meta.tokenize(request, url)
    return response.json({"url": utils.urls.clean(url), "generator": "fallback", "confidence": 0.55}, status=201)


@blueprint.post("/custom")
@openapi.summary("Create a meme from any image")
@openapi.body({"application/json": CustomRequest})
@openapi.response(
    201,
    {"application/json": MemeResponse},
    description="Successfully created a meme from a custom image",
)
async def create_custom(request: Request):
    return await generate_url(request)


@blueprint.get("/custom")
@openapi.summary("List popular custom memes")
@openapi.parameter("safe", bool, "query", description="Exclude NSFW results")
@openapi.parameter(
    "filter", str, "query", description="Part of the meme's text to match"
)
@openapi.response(
    200,
    {"application/json": list[MemeResponse]},
    "Successfully returned a list of custom memes",
)
async def index_custom(request: Request):
    query = request.args.get("filter", "").lower()
    safe = utils.urls.flag(request, "safe", True)

    results = await utils.meta.search(request, query, safe, mode="results")
    logger.info(f"Found {len(results)} result(s)")
    if not results:
        return response.json({"message": f"No results matched: {query}"}, status=404)

    items = []
    for result in results:
        url = utils.urls.normalize(result["image_url"])
        url, _updated = await utils.meta.tokenize(request, url)
        items.append({"url": url})

    return response.json(items, status=200)


@blueprint.get(r"/<template_filename:.+\.\w+>")
@openapi.summary("Display a template background")
@openapi.parameter(
    "template_filename",
    str,
    "path",
    description="Template ID and image format: `<template_id>.<extension>`",
)
@openapi.response(
    200, {"image/*": bytes}, "Successfully displayed a template background"
)
@openapi.response(404, {"image/*": bytes}, "Template not found")
@openapi.response(415, {"image/*": bytes}, "Unable to download image URL")
@openapi.response(
    422,
    {"image/*": bytes},
    "Invalid style for template or no image URL specified for custom template",
)
async def detail_blank(request: Request, template_filename: str):
    template_id, extension = template_filename.rsplit(".", 1)

    if (
        request.args.get("style") == "animated"
        and extension not in settings.ANIMATED_EXTENSIONS
    ):
        # TODO: Move this pattern to utils
        params = {k: v for k, v in request.args.items() if k != "style"}
        url = request.app.url_for(
            "Images.detail_blank",
            template_filename=template_id + ".gif",
            **params,
        )
        return response.redirect(utils.urls.clean(url), status=301)

    return await render_image(request, template_id, extension=extension)


@blueprint.get(r"/<template_id:slug>/<text_filepath:[^/].*\.\w+>")
@openapi.summary("Display a custom meme")
@openapi.parameter(
    "text_filepath",
    str,
    "path",
    description="Lines of text and image format: `<line1>/<line2>.<extension>`",
)
@openapi.parameter("template_id", str, "path", description="ID of a meme template")
@openapi.response(200, {"image/*": bytes}, "Successfully displayed a custom meme")
@openapi.response(404, {"image/*": bytes}, "Template not found")
@openapi.response(414, {"image/*": bytes}, "Custom text too long (length >200)")
@openapi.response(415, {"image/*": bytes}, "Unable to download image URL")
@openapi.response(
    422,
    {"image/*": bytes},
    "Invalid style for template or no image URL specified for custom template",
)
async def detail_text(request: Request, template_id: str, text_filepath: str):
    text_paths, extension = text_filepath.rsplit(".", 1)

    if (
        request.args.get("style") == "animated"
        and extension not in settings.ANIMATED_EXTENSIONS
    ):
        # TODO: Move this pattern to utils
        params = {k: v for k, v in request.args.items() if k != "style"}
        url = request.app.url_for(
            "Images.detail_text",
            template_id=template_id,
            text_filepath=text_paths + ".gif",
            **params,
        )
        return response.redirect(utils.urls.clean(url), status=301)

    slug, updated = utils.text.normalize(text_paths)
    if updated:
        url = request.app.url_for(
            "Images.detail_text",
            template_id=template_id,
            text_filepath=slug + "." + extension,
            **request.args,
        )
        return response.redirect(utils.urls.clean(url), status=301)

    url, updated = await utils.meta.tokenize(request, request.url)
    if updated:
        return response.redirect(url, status=302)

    watermark, updated = await utils.meta.get_watermark(request)
    if updated:
        # TODO: Move this pattern to utils
        params = {k: v for k, v in request.args.items() if k != "watermark"}
        url = request.app.url_for(
            "Images.detail_text",
            template_id=template_id,
            text_filepath=slug + "." + extension,
            **params,
        )
        return response.redirect(utils.urls.clean(url), status=302)

    return await render_image(request, template_id, slug, watermark, extension)

    return await render_image(request, template_id, slug, watermark, extension)
