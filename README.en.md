# LayerWeave development sources

[简体中文](README.md) | **English**

**Find project information by time and visual context.**

LayerWeave organizes text, media references, and feedback into projects that can be queried by time or sequence. Its underlying data gives objects identities and relationships. The complete version connects that data to a canvas and screenshots for agents, so participants can examine visuals alongside project content. Images, audio, and video are referenced by file path or URL.

This is the main development branch, with direct Python and CLI access. The visualization branch provides the web view, annotation tools, MCP service, and release packaging. Both share the same core, support layer, and non-visual tools.

## Start with a concrete task

**Find information by time.** Query seconds 30–35 for shots, media references, and relationships, then locate specific objects to edit. The complete version can also capture that range for a visual check. The [storyboard and H3 example](examples/showcases/donut-hole-h3/README.md) illustrates 60 shots with still images, requiring no video download.

**Connect “here” to specific content.** The complete version exposes the current view, selected objects, content at a moment, and screenshots. People can share a view link or leave an annotation for an agent to read, reply to, and address. [Late Bloom](examples/showcases/late-bloom-scroll/README.md) shows four agents checking scene boundaries through annotations; it uses the complete version's annotation types.

**Find material in reading order.** Arrange an essay, interpretations, and illustrations by paragraph or page, then follow relationships to evidence and discussion. The [article-reading example](examples/showcases/article-reading/README.md) offers five runnable tasks using the base Python/CLI tools and is the recommended starting point.

Content queries return object identities, text, and relationships; the complete version's screenshots supply the corresponding visuals. Developers can reuse the underlying queries and edits directly and add a view as needed. [Browse all twelve examples](examples/showcases/README.md). Their content and detailed walkthroughs are currently in Chinese.

## Build your own tools

For example, after linking characters to shots, you can write a tool that lists each character's shots from the existing project. Save its results using the same read/write operations, identifiers, and change records.

Developers and agents can use the existing content structures or add their own types and database tables. Tool packages can be added or removed, and the underlying data operations can be embedded directly in your own Python application. Specialized interfaces can use the complete version's view plugins.

Start with the [extension guide](docs/build-with-layerweave/README.md). The [tool-owned table example](examples/tool_tables.py) demonstrates how a new tool shares record storage, history, and undo. See the [public API](src/layerweave/support/API.md) for individual calls. These detailed guides are in Chinese.

## Start developing

The initial supported platform is Windows. The code requires Python 3.11+ and SQLite 3.35+. After obtaining this branch's sources, you can let [uv](https://docs.astral.sh/uv/getting-started/installation/) prepare Python automatically. Run from the source root in PowerShell:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

By default, uv downloads Python if needed; initial setup and dependencies require internet access. No environment activation is needed. If Python is already installed and you prefer pip, use:

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

Editable installation makes layerweave importable from other working directories and exposes source changes immediately. pyproject.toml provides this local development entry point; main does not produce a separate end-user release package. The core and ordinary tools need only the standard library at runtime; dev dependencies support development checks. Examples use temporary data and do not modify real projects.

Source installation also needs setuptools>=77.0.3 and wheel. By default, pip prepares them in an isolated build environment and may download them even if setuptools is installed in the current environment. If installation stalls at Installing build dependencies, see [source installation troubleshooting (Chinese)](docs/developer-conventions.md#可编辑安装与构建依赖). Disable build isolation only after installing the required build dependencies.

To try a case, set `$casePython = (Resolve-Path .venv/Scripts/python.exe).Path` in the same PowerShell session, then follow that case's import and query instructions.

## Discover interfaces on demand

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

command_help lists installed tools and invocation examples. config_help explains layer and object purposes, fields, and definitions. The mcp metadata in command declarations is available to external adapters; it does not start a service.

The detailed guides below, CLI/help descriptions, and bundled template content are currently primarily Chinese. Machine-readable field and command names remain unchanged.

- [Use existing tools](src/layerweave/tool/builtin/usage/README.md): project CRUD, queries, timeline editing, history and undo, JSON exchange, and templates.
- [Source maintenance](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

Use the shared write entry points for business records. A new definition provides both a Python class and TOML. Complete tool packages can be replaced or removed. Skills are materials for an agent to read on demand; check their dependencies, credentials, and output directories before use.

## Validate changes

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -t . -v
```

Tests are grouped into architecture, foundation, and tools, and use temporary data. See the [test guide (Chinese)](tests/README.md). Windows command examples explicitly use -X utf8 for piped output; PYTHONUTF8=1 is an alternative. See the [encoding notes](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## License

LayerWeave source code is licensed under [MIT](LICENSE). Separate skills, external libraries, and services follow their own terms. See the visualization branch for web bundles and third-party distribution notices.
