# LayerWeave development sources

[简体中文](README.md) | **English**

Use layers, objects, and relations as a reusable Python foundation for your own AI tools.

`main` is the non-visual development branch. It contains the core, models, support layer, non-visual internal tools, definitions, templates, and skill materials. Call Python or CLI entry points directly and add or remove complete tool packages. Shared implementations match `visualization`; the complete branch maintains the view, MCP service, and end-user release packaging, which are not installed by main.

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

## Discover interfaces on demand

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

command_help lists installed tools and invocation examples. config_help explains layer and object purposes, fields, and definitions. The mcp metadata in command declarations is available to external adapters; it does not start a service.

The detailed guides below, CLI/help descriptions, and bundled template content are currently primarily Chinese. Machine-readable field and command names remain unchanged.

- [Use existing tools](src/layerweave/tool/builtin/usage/README.md): project CRUD, queries, timeline editing, history and undo, JSON exchange, and templates.
- [Foundation API](src/layerweave/support/API.md): raw reads, writes, model loading, and transactions.
- [Extension guide](docs/build-with-layerweave/README.md): tool-owned tables, composed write sessions, incremental reads, and numbering rules.
- [Source maintenance](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

Use the shared write entry points for business records. A new definition provides both a Python class and TOML. Complete tool packages can be replaced or removed. Skills are materials for an agent to read on demand; check their dependencies, credentials, and output directories before use.

## Validate changes

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -t . -v
```

Tests are grouped into architecture, foundation, and tools, and use temporary data. See the [test guide (Chinese)](tests/README.md). Windows command examples explicitly use -X utf8 for piped output; PYTHONUTF8=1 is an alternative. See the [encoding notes](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## License

LayerWeave source code is licensed under [MIT](LICENSE). Separate skills, external libraries, and services follow their own terms. See the visualization branch for web bundles and third-party distribution notices.
