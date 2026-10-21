# LayerWeave

[简体中文](README.md) | **English**

**0.7.8 public preview · Windows**

**Organize work into projects that agents can edit and tools can build on.**

LayerWeave keeps content, its relationships, and feedback in one project. People can inspect specific items and leave comments; agents can find the relevant material, read it, make changes, and continue the work. Images, audio, and video are referenced by file path or URL.

## What you can do

**Read an article and trace a claim to its evidence.** Connect the essay, interpretations, evidence, and illustrations. Select a claim to find its supporting material, ask an agent to read that portion, and revise an interpretation while keeping its links to the essay. The [article-reading example](examples/showcases/article-reading/README.md) includes five runnable reading tasks and is a good place to start.

**Plan a storyboard with its assets and implementation notes.** A shot can link to a story segment, images, and instructions for producing it. Adjust positions, replace assets, or edit a batch while retaining existing object identities; inspect change history or undo an operation when needed. The [storyboard and H3 example](examples/showcases/donut-hole-h3/README.md) uses still images to show how 60 shots are organized, with no video download required.

**Leave comments that others can pick up later.** Attach feedback to an item or time range. Another person or agent can read it, reply, and mark it resolved. Each participant can track what they have read and query pending discussions. [Late Bloom](examples/showcases/late-bloom-scroll/README.md) records how four agents used annotations to check scene boundaries and assemble an animated scroll.

Organize content by paragraph, page, sequence, or time, and connect related items. Use the existing tools through MCP, the command line, or Python; the optional web view supports Chinese and English. [Browse all twelve examples](examples/showcases/README.md). Their content and detailed walkthroughs are currently in Chinese.

## Add a tool for your own task

For example, after linking characters to shots, you can build a small tool that lists each character's shots from the existing project. When saving results, reuse the project's read/write operations, identifiers, and change records.

Developers and agents can use the existing content structures through Python, or add their own types and database tables. View plugins provide specialized interfaces. Tool packages can be added or removed, and the underlying data operations can also be embedded directly in your own Python application.

Start with the [extension guide](docs/build-with-layerweave/README.md). The [tool-owned table example](examples/tool_tables.py) demonstrates how a new tool shares record storage, history, and undo. See the [public API](src/layerweave/support/API.md) for individual calls. These detailed guides are in Chinese.

## Windows quick start

The initial supported platform is Windows. The code requires Python 3.11+ and SQLite 3.35+; these examples use Python 3.11. [uv](https://docs.astral.sh/uv/getting-started/installation/) can prepare Python and the environment for you, or you can use an existing Python installation. Node is not needed to use the web view.

### Install the complete package with uv

Obtain `layerweave-0.7.8-py3-none-any.whl` and place it in your chosen working directory. After installing uv, run these commands in PowerShell from that directory:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

By default, uv downloads a suitable Python version if one is missing. Initial setup and dependency downloads require internet access. You do not need to activate the environment; subsequent commands use its interpreter directly. [How uv manages Python](https://docs.astral.sh/uv/concepts/python-versions/)

If Python is already installed and you prefer pip, use:

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

`[mcp]` adds the optional dependencies for AI integration. Omit it for Python/CLI-only use. Installing the package does not install the official view plugins. These commands use a local wheel and do not assume that this version is available on PyPI.

The wheel is already built, so installing LayerWeave itself does not require setuptools. The `[mcp]` dependencies may still need downloading; the wheel is not a complete offline environment. Editable installation is for source development. If it stalls while preparing build dependencies, see [source installation troubleshooting (Chinese)](docs/developer-conventions.md#可编辑安装与构建依赖).

### Start with the article-reading example

Copy `examples/showcases` from the matching source distribution, or extract the examples ZIP into an `examples` folder in your working directory. The result should include `examples/showcases/article-reading/project.json`. Examples are separate from the installed software. Start with article reading; the [case directory](examples/showcases/README.md) lists all twelve examples and their prerequisites.

Run these commands from the working directory where you installed the wheel:

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli examples/showcases/article-reading/reading.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply examples/showcases/article-reading/reading.sqlite3 --data-file examples/showcases/article-reading/project.json --new-project --result-file import-result.json
$caseImport = Get-Content -Raw -Encoding utf8 import-result.json | ConvertFrom-Json
if (-not $caseImport.ok) { throw 'Import failed; inspect import-result.json' }
$caseProjectId = $caseImport.data.project_id
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.query.project_overview examples/showcases/article-reading/reading.sqlite3 $caseProjectId
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.view.server examples/showcases/article-reading/reading.sqlite3 --project $caseProjectId
```

Open the local URL printed by the server. Read the original essay and its interpretations, then follow a claim to its evidence and illustrations. The [article-reading guide (Chinese)](examples/showcases/article-reading/README.md) provides five focused reading tasks. Keep the database in the case directory so relative image paths resolve. Use the returned project ID; importing again creates another project.

This starter case needs no API key, FFmpeg, Node, or view plugin. Local content is in Chinese and works offline; following external article links needs internet access. The hand-drawn MV and H3 cases use still images for offline reading, with no video or audio files in the public case package.

### Create your own project

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --template subtitles --new-project
```

Templates cover subtitles, storyboards, and illustrated music videos. Their structure can be freely adapted. Pass the returned project ID to the view or query tools; use help for their parameters.

FFmpeg is an optional external program installed by the user; the wheel, `[mcp]`, and uv do not install it automatically. Ordinary data management and text views do not need it. Server-side frame extraction requires FFmpeg; thumbnails and waveforms also use it, with some browsing fallbacks when absent. Add its bin directory to PATH or set `FFMPEG` to the full path of ffmpeg.exe; see [setup and affected features (Chinese)](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg). AI screenshots also require Chrome, Edge, or Chromium. The user or AI chooses the media output directories.

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
uvx --python 3.11 --from "./layerweave-0.7.8-py3-none-any.whl[mcp]" layerweave-mcp --config ./mcp.json
```

This runs a persistent stdio service, normally managed by an MCP client; it does not open the web view. Use absolute paths in a client's uvx configuration; the MCP guide includes an example. Once the package has a published download URL, that URL can also identify its source without adding a separate business API.

## Find tools and documentation

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

The detailed guides below are currently in Chinese; CLI/help descriptions and bundled template content are also primarily Chinese. Machine-readable field and command names remain unchanged.

- [Usage guide](src/layerweave/tool/builtin/usage/README.md): choose a tool and inspect its inputs, outputs, and examples.
- [JSON exchange and templates](src/layerweave/tool/builtin/usage/exchange/README.md): batch operations and starting structures.
- [View and plugins](src/layerweave/tool/builtin/view/README.md): interface usage. [Official plugins](https://gitee.com/emotion1354414/layerweave-plugins) are optional; the canvas works with no plugins.
- [Source development](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

`visualization` is the complete version. `main` contains non-visual development sources with direct Python/CLI entry points and the same shared core, support layer, and non-visual tools. The complete branch maintains the view, MCP service, and release packaging. Commands use `-X utf8` for reliable piped output on Chinese Windows; see the [encoding notes](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## License

LayerWeave itself is licensed under [MIT](LICENSE). Bundled web dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Separate plugins, skills, and external services follow their own terms.
