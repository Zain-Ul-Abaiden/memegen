An API to programmatically generate memes based solely on requested URLs.

<span class="badges"><!-- badges -->
[![Build Status](https://img.shields.io/circleci/build/github/jacebrowning/memegen)](https://circleci.com/gh/jacebrowning/memegen)
[![Coverage Status](http://img.shields.io/coveralls/jacebrowning/memegen/main.svg)](https://coveralls.io/r/jacebrowning/memegen)
[![Swagger Validator](https://img.shields.io/swagger/valid/3.0?label=docs&specUrl=https%3A%2F%2Fapi.memegen.link%2Fdocs%2Fopenapi.json)](https://meme.bigosoft.us/docs/)
[![License](https://img.shields.io/badge/license-mit-blue)](https://github.com/jacebrowning/memegen/blob/main/LICENSE.txt)
[![GitHub Sponsors](https://img.shields.io/endpoint?url=https://memecomplete.com/api/memes/badge.json)](https://github.com/sponsors/jacebrowning)
</span>

[Buy me a coffee to help keep this service running!](https://www.buymeacoffee.com/jacebrowning)

---

# Images

The API is stateless so URLs contain all the information necessary to generate meme images. For example, <https://meme.bigosoft.us/images/buzz/memes/memes_everywhere.webp> produces:

![Example Image](https://meme.bigosoft.us/images/buzz/memes/memes_everywhere.webp?token=wxgjeu3jll4dt9q6fihy&width=800)

## Available Formats

Clients can request `.jpg` instead of `.png` for smaller files. The `.gif` and `.webp` extensions can be used if an animated background is available or to animate text on static backgrounds:

| Format                     | Example                                                                                                     |
| :------------------------- | :---------------------------------------------------------------------------------------------------------- |
| PNG                        | [/images/ds/small_file/high_quality.png](https://meme.bigosoft.us/images/ds/small_file/high_quality.png)    |
| JPEG                       | [/images/ds/high_quality/small_file.jpg](https://meme.bigosoft.us/images/ds/high_quality/small_file.jpg)    |
| GIF (animated background)  | [/images/oprah/you_get/animated_text.gif](https://meme.bigosoft.us/oprah/you_get/animated_text.gif)         |
| GIF (static background)    | [/images/iw/animates_text/in_production.gif](https://meme.bigosoft.us/iw/animates_text/in_production.gif)   |
| WebP (animated background) | [/images/oprah/you_get/animated_text.webp](https://meme.bigosoft.us/oprah/you_get/animated_text.webp)       |
| WebP (static background)   | [/images/iw/animates_text/in_production.webp](https://meme.bigosoft.us/iw/animates_text/in_production.webp) |

## Custom Dimensions

Images can be scaled to a specific width or height using the `width=<int>` and `height=<int>` query parameters. If both are provided (`width=<int>&height=<int>`), the image will be padded to the exact dimensions.

For example, <https://meme.bigosoft.us/images/both/width_or_height/why_not_both~q.png?height=450&width=800> produces:

![Custom Size](https://meme.bigosoft.us/images/both/width_or_height/why_not_both~q.png?height=450&width=800&token=6alj86spiq9iyevbknm3)

## Special Characters

In URLs, spaces can be inserted using underscores or dashes:

- underscore (`_`) → space (` `)
- dash (`-`) → space (` `)
- 2 underscores (`__`) → underscore (`_`)
- 2 dashes (`--`) → dash (`-`)
- tilde + N (`~n`) → newline character

Reserved URL characters can be included using escape patterns:

- tilde + Q (`~q`) → question mark (`?`)
- tilde + A (`~a`) → ampersand (`&`)
- tilde + P (`~p`) → percentage (`%`)
- tilde + H (`~h`) → hashtag/pound (`#`)
- tilde + S (`~s`) → slash (`/`)
- tilde + B (`~b`) → backslash (`\`)
- tilde + L (`~l`) → less-than sign (`<`)
- tilde + G (`~g`) → greater-than sign (`>`)
- 2 single quotes (`''`) → double quote (`"`)

Emojis are also supported, both as characters (👍) and aliases (`:thumbsup:`).

For example, <https://meme.bigosoft.us/images/ugandanknuck/~hspecial_characters~q/underscore__-dash--_:thumbsup:.png> produces:

![Escaped Characters](https://meme.bigosoft.us/images/ugandanknuck/~hspecial_characters~q/underscore__-dash--_%F0%9F%91%8D.png?token=0wzowe01f5oxdtaqz21i)

All of the `POST` endpoints will return image URLs with special characters replaced with these alternatives.

# Templates

The list of predefined meme templates is available here: <https://meme.bigosoft.us/templates/>

## Alternate Styles

Some memes come in multiple forms, which can be selected using the `style=<str>` query parameter.

For example, the <https://meme.bigosoft.us/templates/ds/> template provides these styles:

|                          `/images/ds.png`                          |                           `/images/ds.png?style=maga`                           |
| :----------------------------------------------------------------: | :-----------------------------------------------------------------------------: |
| ![Default Style](https://meme.bigosoft.us/images/ds.png?width=375) | ![Alternate Style](https://meme.bigosoft.us/images/ds.png?width=375&style=maga) |

## Custom Overlays

The `style=<str>` query parameter can also be an image URL to overlay on the default background image.

For example, <https://meme.bigosoft.us/images/pigeon/Engineer/_/Is_this_Photoshop~q.png?style=https://i.imgur.com/W0NXFpQ.png> produces:

![Custom Overlay](https://meme.bigosoft.us/images/pigeon/Engineer/_/Is_this_Photoshop~q.png?style=https://i.imgur.com/W0NXFpQ.png&width=800&token=mbckgprafgz8o4l1adct)

The overlay image can be customized with the following additional query parameters:

| Name     | Type              | Description                                         |
| -------- | ----------------- | --------------------------------------------------- |
| `center` | `<float>,<float>` | Position of overlay relative to the top-left corner |
| `scale`  | `<float>`         | Ratio of the background image's dimensions          |

## Custom Backgrounds

You can also use your own image URL as the background.

For example, <https://meme.bigosoft.us/images/custom/_/my_background.png?background=http://www.gstatic.com/webp/gallery/1.png> produces:

![Custom Background](https://meme.bigosoft.us/images/custom/_/my_background.png?background=http://www.gstatic.com/webp/gallery/1.png&width=800&token=kxxlu7wzoxgp5l2iruta)

This can be combined with [custom overlays](#custom-overlays) to augment the background image.

# Layouts

Add the `layout=<str>` query parameter to switch between the default and `top` text positioning.

For example, <https://meme.bigosoft.us/images/rollsafe/When_you_have_a_really_good_idea.webp?layout=top> produces:

![Top Layout](https://meme.bigosoft.us/images/rollsafe/When_you_have_a_really_good_idea.webp?layout=top&width=800&token=orgyyu0tuzir7n4ktwvc)

# Fonts

The list of fonts is available here: <https://meme.bigosoft.us/fonts/>

Add the `font=<str>` query parameter to customize the look of your meme:

| Name                                                                   | ID                  | Alias        |
| ---------------------------------------------------------------------- | ------------------- | ------------ |
| [Titillium Web Black](https://fonts.google.com/specimen/Titillium+Web) | `font=titilliumweb` | `font=thick` |
| [Kalam Regular](https://fonts.google.com/specimen/Kalam)               | `font=kalam`        | `font=comic` |
| [Impact](https://www.dafontfree.io/impact-font/)                       | `font=impact`       | -            |
| [Noto Sans Bold](https://fonts.google.com/noto/specimen/Noto+Sans)     | `font=notosans`     | -            |
| [HG Mincho B](https://japanesefonts.org/hg-mincho-b.html)              | `font=hgminchob`    | `font=jp`    |

<br>

Explore the full API here: <https://meme.bigosoft.us/docs/>

---

## Quickstart (Local)

- Requirements: Python 3.12, system libs for Pillow/WebP, and either Poetry or pip.

Using Poetry (recommended):

```bash
poetry install
poetry run python app/main.py
```

Using pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

The server starts on `https://meme.bigosoft.us` and redirects `/` to the interactive docs at `/docs`.

## Running in development

There is a Procfile for convenience:

```bash
honcho start -f Procfile.dev
```

or run with Gunicorn in a production-like way (Heroku/Render style):

```bash
honcho start -f Procfile
```

## Configuration (Environment Variables)

- **SERVER_NAME**: Host:port for external URLs (default `localhost:3000`).
- **SCHEME**: `http` or `https` (default `http`).
- **RELEASE_STAGE**: `local` or deployment label (default `local`).
- **DEFAULT_STATIC_EXTENSION**: Default static image format (default `png`).
- **DEFAULT_ANIMATED_EXTENSION**: Default animated format (default `gif`).
- **API_KEY**: If set, protects non-public endpoints.
- **API_KEY_HEADER**: Header name for API key (default `X-API-Key`).
- **GEMINI_API_KEY**: Enables AI-powered meme creation when set.
- **GEMINI_MODEL**: Gemini model name (default `gemini-2.0-flash`).

You can create an `.env` file in the project root; it will be auto-loaded.

Example `.env`:

```env
SERVER_NAME=localhost:3000
SCHEME=http
API_KEY=change-me
API_KEY_HEADER=X-API-Key
GEMINI_API_KEY=your-google-gemini-key
GEMINI_MODEL=gemini-2.0-flash
```

## Authentication

If `API_KEY` is set, all routes are protected except:

- `/` and `/docs*` (OpenAPI UI and spec)
- `/openapi*` (OpenAPI JSON)
- `/favicon.ico`, `/robots.txt`
- `/images/*` except `/images/automatic`

Send the key as header `X-API-Key: <API_KEY>` (or your custom header name) or as a query param `?api_key=<API_KEY>`.

## Core Endpoints

- `GET /images` — List example memes (JSON).
- `POST /images` — Create a meme from a template ID and text.
- `POST /images/custom` — Create a meme from any image URL.
- `POST /images/automatic` — AI-assisted meme creation from natural language (requires `API_KEY` if configured).
- `GET /images/<template_id>/<text>.<ext>` — Render a meme directly via URL.
- `GET /images/<template_id>.<ext>` — Fetch a template background.
- `GET /templates` — List available templates (see `/docs`).

Query params supported by render endpoints include (non-exhaustive):

- `style` (`default`, `animated`, or overlay URL)
- `layout` (`default`, `top`)
- `font` (see `/fonts`)
- `width`, `height` (dimension controls)
- `background` (for custom templates)

## Examples

Create via API (template and text):

```bash
curl -X POST https://meme.bigosoft.us/images \
  -H 'Content-Type: application/json' \
  -d '{"template_id": "fry", "text": ["not sure if", "it actually works"]}'
```

Custom background:

```bash
curl -X POST https://meme.bigosoft.us/images/custom \
  -H 'Content-Type: application/json' \
  -d '{"text": ["top", "bottom"], "background": "https://www.gstatic.com/webp/gallery/1.jpg"}'
```

AI-assisted (Gemini):

```bash
curl -X POST https://meme.bigosoft.us/images/automatic \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me' \
  -d '{"text": "Create a Fry meme about being unsure if the code is working"}'
```

Direct URL rendering:

```bash
open "https://meme.bigosoft.us/images/fry/not_sure/if_it_works.png"
```

## AI (Gemini) Notes

When `GEMINI_API_KEY` is configured, `POST /images/automatic` will:

- Use the Gemini model to interpret your natural-language request.
- Choose template, text, style, and image format.
- Return a JSON response with a generated `/images/...` URL and a confidence score.

If AI fails or is not configured, the server falls back to a heuristic selection of a valid template and returns a working meme URL when possible.

## Deployment

- Container: see `Containerfile`.
- Procfile (web + release) compatible with Heroku/Render (`gunicorn` + `uvicorn` worker).
- Health and docs available at `/docs` and `/openapi.json`.

## Development

- Code style: Black + isort; type-checking via mypy.
- Tests: `pytest` (see `scripts/check_deployment.py` for deployment smoke checks).
- Fonts and templates live in `fonts/` and `templates/` respectively.

## License

MIT. See `LICENSE.txt`.
