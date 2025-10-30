import hashlib
import re
from urllib.parse import unquote


def encode(lines: list[str]) -> str:
    encoded_lines = []

    for line in lines:
        if line == "/":
            encoded_lines.append("_")
        elif line:
            encoded_lines.append(_encode(line))
        else:
            encoded_lines.append("_")

    slug = "/".join(encoded_lines)

    return slug or "_"


def _encode(line):
    has_trailing_under = "_ " in line

    encoded = unquote(line)

    for before, after in [
        ("_", "__"),
        ("-", "--"),
        (" ", "_"),
        ("?", "~q"),
        ("%", "~p"),
        ("#", "~h"),
        (":", "~c"),
        ('"', "''"),
        ("/", "~s"),
        ("\\", "~b"),
        ("\n", "~n"),
        ("&", "~a"),
        ("<", "~l"),
        (">", "~g"),
        ("‘", "'"),
        ("’", "'"),
        ("“", '"'),
        ("”", '"'),
        ("–", "-"),
    ]:
        encoded = encoded.replace(before, after)

    if has_trailing_under:
        encoded = encoded.replace("___", "__-")

    # On Windows, path segments cannot end with a dot. Replace any trailing dots.
    # Preserve length by converting trailing '.' characters to underscores.
    while encoded.endswith("."):
        encoded = encoded[:-1] + "_"

    return encoded


def decode(slug: str) -> list[str]:
    has_dash = "_----" in slug
    has_flag = "_--" in slug
    has_arrow = "_--~g" in slug
    has_under = "___" in slug

    slug = slug.replace("_", " ").replace("  ", "_")
    slug = slug.replace("-", " ").replace("  ", "-")
    slug = slug.replace("''", '"')

    if has_dash:
        slug = slug.replace("-- ", " --")
    elif has_flag:
        slug = slug.replace("- ", " -")

    if has_arrow:
        slug = slug.replace("- ~g", " -~g")

    if has_under:
        slug = slug.replace("_ ", " _")

    for before, after in [
        ("~q", "?"),
        ("~p", "%"),
        ("~h", "#"),
        ("~n", "\n"),
        ("~a", "&"),
        ("~l", "<"),
        ("~g", ">"),
        ("~b", "\\"),
        ("~c", ":"),
    ]:
        slug = slug.replace(before, after)

    lines = slug.split("/")
    lines = [line.replace("~s", "/") for line in lines]

    return lines


def normalize(slug: str) -> tuple[str, bool]:
    slug = unquote(slug)
    normalized_slug = encode(decode(slug))
    return normalized_slug, slug != normalized_slug


def fingerprint(value: str, *, prefix="_custom-", suffix="") -> str:
    if not value.strip():
        return ""
    return prefix + hashlib.sha1(value.encode()).hexdigest() + suffix


def slugify(value: str) -> str:
    # Allow either pure slugs, or _custom-hash style
    if value.startswith("_custom-"):
        # Ensure that what's after _custom- is a hex string
        suffix = value[len("_custom-"):]
        if suffix and all(c in "0123456789abcdef" for c in suffix.lower()):
            return value
        # fallback: strip anything else
        return re.sub(r"[^_a-z0-9-]", "", value).strip("-")
    return re.sub(r"[^a-z0-9-]", "", value).strip("-")
