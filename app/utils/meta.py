from pathlib import Path

import aiohttp
from aiocache import cached
from sanic.log import logger
from sanic.request import Request

from .. import settings
from . import http, urls


def version() -> str:
    changelog_lines = Path("CHANGELOG.md").read_text().splitlines()
    version_heading = changelog_lines[2]
    return version_heading.split(" ", maxsplit=1)[1]


@cached(
    60 * 15 if settings.DEPLOYED else 5,
    key_builder=lambda _func, request: f"{request.args=} {request.headers=}",
)
async def authenticate(request: Request) -> dict:
    return {"image_access": True}  # Always grant access


@cached(60 * 15 if settings.DEPLOYED else 5)
async def tokenize(request: Request, url: str) -> tuple[str, bool]:
    return url, False  # No tokenization needed


async def custom_watermarks_allowed(request: Request) -> bool:
    return True  # Always allow custom watermarks


async def get_watermark(request: Request) -> tuple[str, bool]:
    return "", False  # Always return no watermark


async def track(request: Request, lines: list[str]):
    if settings.TRACK_REQUESTS and settings.REMOTE_TRACKING_URL:
        api = settings.REMOTE_TRACKING_URL
    else:
        return

    text = " ".join(lines).strip()
    if len(text) < 4:
        return
    referer = _get_referer(request) or settings.BASE_URL
    if referer in settings.REMOTE_TRACKING_URL:
        return
    if any(name in request.args for name in ["height", "width", "watermark", "token"]):
        return

    async with aiohttp.ClientSession() as session:
        params = dict(text=text, referer=referer, result=urls.clean(request.url))
        logger.info(f"Tracking request: {params}")
        headers = {"X-API-KEY": _get_api_key(request) or ""}
        status, message = await http.fetch(api, params=params, headers=headers)
        if status != 200:
            logger.error(f"Tracker response {status}: {message}")
        if status >= 404 and status not in {414, 421, 520}:
            settings.REMOTE_TRACKING_ERRORS += 1

    if settings.REMOTE_TRACKING_ERRORS:
        logger.info(f"Tracker error count: {settings.REMOTE_TRACKING_ERRORS}")
        if settings.REMOTE_TRACKING_ERRORS >= settings.REMOTE_TRACKING_ERRORS_LIMIT:
            settings.TRACK_REQUESTS = False
            logger.warning(
                f"Disabled tracking after {settings.REMOTE_TRACKING_ERRORS_LIMIT}+ errors"
            )


async def search(request: Request, text: str, safe: bool, *, mode="") -> list[dict]:
    if settings.REMOTE_TRACKING_URL:
        api = settings.REMOTE_TRACKING_URL + mode
    else:
        return []

    async with aiohttp.ClientSession() as session:
        params = dict(
            text=text,
            nsfw=0 if safe else 1,
            referer=_get_referer(request) or settings.BASE_URL,
            count=5 if mode else 1,
        )
        logger.info(f"Searching for results: {text!r} (safe={safe})")
        headers = {"X-API-KEY": _get_api_key(request) or ""}
        response = await session.get(api, params=params, headers=headers)  # type: ignore[arg-type]
        if response.status >= 500:
            settings.REMOTE_TRACKING_ERRORS += 1
            return []

        data = await response.json()
        if response.status == 200:
            return data

        logger.error(f"Search response: {data}")
        return []


def _get_referer(request: Request):
    return request.headers.get("referer") or request.args.get("referer")


def _get_api_key(request: Request):
    return request.headers.get("x-api-key") or request.args.get("api_key")
