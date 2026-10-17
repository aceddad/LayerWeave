"""View-only language resources; project data and canonical plugin manifests stay unchanged."""
from functools import lru_cache
import json
from pathlib import Path
import re


@lru_cache(maxsize=2)
def dictionary(lang="zh"):
    return json.loads(Path(__file__).with_name("locales").joinpath(lang + ".json").read_text(encoding="utf-8"))


def translate(key, values=None, *, lang="zh"):
    lang = lang if lang in ("zh", "en") else "zh"
    text = dictionary(lang).get(key, dictionary("zh").get(key, key))
    values = values or {}
    return re.sub(r"\{(\w+)\}", lambda m: str(values[m[1]]) if m[1] in values else m[0], text)


class ViewError(ValueError):
    def __init__(self, key, values=None, *, detail=None):
        self.ui = {"key": key, "values": {k: v if isinstance(v, (str, int, float)) else str(v) for k, v in (values or {}).items()}}
        if detail:
            self.ui["detail"] = str(detail)
        super().__init__(translate(key, self.ui["values"]) + (f"\n{detail}" if detail else ""))


def error_payload(error):
    return {"error": str(error), "ui": getattr(error, "ui", {"key": "error.request", "detail": str(error)})}


def read_localizations(folder, manifest, *, include_usage=False):
    """Optional resources never make otherwise working JavaScript unloadable."""
    from .plugin_manifest import inside
    packs, warnings = {}, []
    for lang, relative in manifest.get("locales", {}).items():
        try:
            pack = json.loads(inside(folder, relative).read_text(encoding="utf-8"))
            if not isinstance(pack, dict):
                raise ValueError("language pack must be an object")
            messages = pack.get("messages", {})
            if not isinstance(messages, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in messages.items()):
                raise ValueError("messages must map keys to strings")
            display = pack.get("display", {})
            if not isinstance(display, dict) or any(k in display and not isinstance(display[k], str) for k in ("label", "title", "description")):
                raise ValueError("display labels must be strings")
            params = display.get("params", {})
            if not isinstance(params, dict) or not all(isinstance(v, str) for v in params.values()):
                raise ValueError("display.params must map parameter names to descriptions")
            result = {"messages": messages, "display": display}
            if pack.get("usage"):
                path = inside(folder, pack["usage"])
                if include_usage:
                    result["usage_text"] = path.read_text(encoding="utf-8")
            packs[lang] = result
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            warnings.append(f"{lang}: {error}")
    return packs, warnings
