import asyncio

from sanic import Sanic, response
from sanic.request import Request
from sanic_ext import openapi
from app import settings

from app import config, helpers, settings, utils

app = Sanic(name="memegen")
config.init(app)

@app.on_request
def enforce_api_key(request):
    public_paths = ["/", "/docs", "/favicon.ico", "/robots.txt"]
    # Allow public access to docs, openapi, and all /images/* EXCEPT /images/automatic
    if (
        request.path in public_paths
        or request.path.startswith("/openapi")
        or request.path.startswith("/docs")
        or (request.path.startswith("/images") and not request.path.startswith("/images/automatic"))
    ):
        return
    if not settings.API_KEY:
        return
    provided = (
        request.headers.get(settings.API_KEY_HEADER)
        or request.args.get("api_key")
    )
    if provided != settings.API_KEY:
        return response.json({"error": "Unauthorized"}, status=401)

# === BEGIN OPENAPI SECURITY SCHEME ===
# NOTE: sanic-ext 'openapi.security' does not exist!
# To secure endpoints, use the @openapi.secured decorator per endpoint, like:
#
# @openapi.secured(settings.API_KEY_HEADER)
# @app.post("/your_path")
# async def your_handler(request):
#     ...
#
# To apply to all relevant endpoints, add the decorator as needed.
#
# The global security definition block has been removed for compatibility.
# === END OPENAPI SECURITY SCHEME ===

@app.get("/")
@openapi.exclude(True)
def index(request: Request):
    return response.redirect("/docs")

@app.get("/test")
@openapi.exclude(True)
async def test(request: Request):
    if not settings.DEBUG:
        return response.redirect("/")

    urls = await asyncio.to_thread(helpers.get_test_images, request)
    content = utils.html.gallery(urls, columns=False, refresh=20)
    return response.html(content)

@app.get("/favicon.ico")
@openapi.exclude(True)
async def favicon(request: Request):
    return await response.file("app/static/favicon.ico")

@app.get("/robots.txt")
@openapi.exclude(True)
async def robots(request: Request):
    return await response.file("app/static/robots.txt")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=3000,
        debug=settings.DEBUG,
        auto_reload=True,
        access_log=False,
        motd=False,
        fast=not settings.DEBUG,
    )
