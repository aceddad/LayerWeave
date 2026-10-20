# LayerWeave

[简体中文](README.md) | **English**

Organize content into layers, objects, and relations so AI agents and programs can read, edit, and extend a project on demand.

LayerWeave provides a Python API, command-line tools, MCP integration, and a local web view. It can represent subtitles, storyboards, illustrated music videos, asset lists, and ordered information. Objects hold content and positions; layers organize them; relations connect entries; axes explain what position values mean.

## What it does

- Inspect layer trees and read selected subtrees, objects, or time ranges. Update by name or a stable key while retaining identities and relations.
- Append, arrange, split, shift, copy, and transfer objects. Import and export batches as JSON.
- Store data and change history in SQLite, with undo and redo by operation.
- Extend the system with Python classes, TOML definitions, and tool-owned tables. Add or remove complete tool packages.
- Inspect projects on a canvas and collaborate with AI through annotations. Install the assets, cuts, and preview plugins separately.

The interface supports Chinese and English; user content is left unchanged. Media objects store resource references. Skills or the caller perform media generation and processing.

## Windows quick start

The initial supported platform is Windows. The code requires Python 3.11+ and SQLite 3.35+; these examples use Python 3.11. [uv](https://docs.astral.sh/uv/getting-started/installation/) can prepare Python and the environment for you, or you can use an existing Python installation. Node is not needed to use the web view.

### Install the complete package

Obtain `layerweave-0.7.6-py3-none-any.whl` and place it in your chosen working directory. After installing uv, run these commands in PowerShell from that directory:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "./layerweave-0.7.6-py3-none-any.whl[mcp]"
```

By default, uv downloads a suitable Python version if one is missing. Initial setup and dependency downloads require internet access. You do not need to activate the environment; subsequent commands use its interpreter directly. [How uv manages Python](https://docs.astral.sh/uv/concepts/python-versions/)

If Python is already installed and you prefer pip, use:

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install "./layerweave-0.7.6-py3-none-any.whl[mcp]"
```

`[mcp]` adds the optional dependencies for AI integration. Omit it for Python/CLI-only use. Installing the package does not install the official view plugins. These commands use a local wheel and do not assume that this version is available on PyPI.

The wheel is already built, so installing LayerWeave itself does not require setuptools. The `[mcp]` dependencies may still need downloading; the wheel is not a complete offline environment. Editable installation is for source development. If it stalls while preparing build dependencies, see [source installation troubleshooting (Chinese)](docs/developer-conventions.md#可编辑安装与构建依赖).

### Create a project and open the view

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --template subtitles --new-project
```

Templates cover subtitles, storyboards, and illustrated music videos. Their structure can be freely adapted. The import result includes the project ID; replace `PROJECT_ID` below with that value:

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.query.project_overview project.sqlite3 PROJECT_ID
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.view.server project.sqlite3 --project PROJECT_ID
```

Open the local URL printed by the server. FFmpeg is an optional external program installed by the user; the wheel, `[mcp]`, and uv do not install it automatically. Ordinary data management and text views do not need it. Server-side frame extraction requires FFmpeg; thumbnails and waveforms also use it. Some browsing features fall back when it is absent, potentially loading more media data. After installing FFmpeg, add its bin directory to PATH or set `FFMPEG` to the full path of ffmpeg.exe (for example, `D:/tools/ffmpeg/bin/ffmpeg.exe`). See [setup and affected features (Chinese)](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg). AI screenshots also require Chrome, Edge, or Chromium. The user or AI chooses the media output directories.

## Connect an AI / MCP client

Save `mcp.json` in your project working directory, using its actual absolute path for workspace:

```json
{"workspace": "D:/my-project"}
```

Configure a client that supports stdio MCP, for example:

```json
{
  "mcpServers": {
    "layerweave": {
      "command": "D:/my-project/.venv/Scripts/python.exe",
      "args": ["-X", "utf8", "-m", "layerweave.tool.builtin.shared.mcp", "--config", "D:/my-project/mcp.json"]
    }
  }
}
```

Replace the interpreter and configuration paths with your actual locations. Where this configuration belongs depends on the client. An agent can start with `layerweave_help` and then operate on specific targets without reading the whole project. Pass the database and project ID per call, or configure defaults; see the [MCP guide (Chinese)](src/layerweave/tool/builtin/shared/mcp/README.md).

For MCP-only use, uvx can prepare the environment and start the service in one command:

```powershell
uvx --python 3.11 --from "./layerweave-0.7.6-py3-none-any.whl[mcp]" layerweave-mcp --config ./mcp.json
```

This runs a persistent stdio service, normally managed by an MCP client; it does not open the web view. Use absolute paths in a client's uvx configuration; the MCP guide includes an example. Once the package has a published download URL, that URL can also identify its source without adding a separate business API.

## Find help and extend the system

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

The detailed guides below are currently in Chinese; CLI/help descriptions and bundled template content are also primarily Chinese. Machine-readable field and command names remain unchanged.

- [Usage guide](src/layerweave/tool/builtin/usage/README.md): choose a tool and inspect its inputs, outputs, and examples.
- [JSON exchange and templates](src/layerweave/tool/builtin/usage/exchange/README.md): batch operations and starting structures.
- [View and plugins](src/layerweave/tool/builtin/view/README.md): interface usage. [Official plugins](https://gitee.com/emotion1354414/layerweave-plugins) are optional; the canvas works with no plugins.
- [Extension guide](docs/build-with-layerweave/README.md): build your own tools, definitions, and tables.
- [Source development](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

`visualization` is the complete version. `main` contains non-visual development sources with direct Python/CLI entry points and the same shared core, support layer, and non-visual tools. The complete branch maintains the view, MCP service, and release packaging. Commands use `-X utf8` for reliable piped output on Chinese Windows; see the [encoding notes](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## License

LayerWeave itself is licensed under [MIT](LICENSE). Bundled web dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Separate plugins, skills, and external services follow their own terms.
