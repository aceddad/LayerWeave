"""Generate package-index introductions from the two repository READMEs."""
from pathlib import Path
import re
from urllib.parse import quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def render(root, filename, version):
    text = (root / filename).read_text(encoding="utf-8")

    def link(match):
        start, target, end = match.groups()
        if urlsplit(target).scheme or target.startswith("//"):
            return match.group(0)
        # Package registries do not all preserve GitHub's heading anchors.
        if target.startswith("#"):
            target = filename + target
        prefix = (f"https://raw.githubusercontent.com/aceddad/LayerWeave/v{version}/"
                  if start.startswith("!") else
                  f"https://github.com/aceddad/LayerWeave/blob/v{version}/")
        return start + prefix + quote(target.removeprefix("./"), safe="/#%:@") + end

    parts = re.split(r"(```.*?```)", text, flags=re.S)
    for index in range(0, len(parts), 2):
        parts[index] = re.sub(r"(!?\[[^\]]*\]\()([^\)\n]+)(\))", link, parts[index])
    return f"<!-- Generated from {filename}; edit the repository source. -->\n\n" + "".join(parts)


def prepare(root=ROOT):
    version = re.search(r'__version__ = "([^"]+)"',
                        (root / "src/layerweave/__init__.py").read_text(encoding="utf-8")).group(1)
    for filename in ("README.md", "README.en.md"):
        text = render(root, filename, version)
        (root / "distribution/npm" / filename).write_text(text, encoding="utf-8")
        if filename == "README.md":
            (root / "distribution/PYPI_README.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    prepare()
