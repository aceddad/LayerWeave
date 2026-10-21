# LayerWeave development sources

[简体中文](README.md) | **English**

**Fewer distractions: look only at the part that matters, and do only the task at hand.**

LayerWeave is an information management tool for people and AI. It places text, media references, and comments on axes ordered by time or sequence, organizes them with layers and relationships, and lets every participant find everything relevant to "this moment, right here." Images, audio, and video are referenced by file path or URL.

Its design principle is to **reduce scattered attention**: finding things, matching positions, tracking changes, and explaining which part you meant are handed to tools, so people and AI can spend their attention on the small part that actually needs thought.

The method is **composition** together with **information management**. Composition keeps every part small and single-purpose: objects sit in layers, layers form a tree, and relationships connect them; the core handles only the basic structure, while queries, editing, the view, skills, and plugins are parts you can add, remove, or replace. The finer things are split, the more scattered the information becomes, so information management ties those pieces back together by time, sequence, and relationship, and any piece can be found directly. Whether working through information or building a feature, you can focus on the part at hand.

This is the **main development branch**. It has no web view: you read, query, and edit projects directly through Python and the CLI, and it is the starting point for building new tools. The canvas, comments, AI screenshots, MCP service, and release packaging live on the **visualization branch**, the complete version. Both share the same core, support layer, and non-visual tools.

**You are welcome to build on and extend the LayerWeave kernel.** You and your agents can reuse its foundations, add or replace tools, and build your own applications. The built-in tools provide usable functionality and examples of how to use the kernel. The view is one example application built on it; the separate view plugins demonstrate how that application can be extended further.

## 1. Information management: see everything at the same moment together

Content sits on axes: videos and songs by the second, articles by paragraph, comics by page and panel, courses by learning step. Each item is an object with its own identity. Objects belong to layers, and layers form a tree; tracks sharing a time scale can be compared at the same moment, and relationships connect the objects. Paragraph numbers, page numbers, and seconds are not automatically converted. The complete version stores comments in sequence, pointing to content through relationships and ranges.

Query seconds 30–35 and you get each layer's shots, media references, and relationships in one go, along with which tracks are empty there. Follow relationships to the story beat and assets behind a shot, then edit that object by its identity, with history and undo available. Content ordered by paragraph or reading order works the same way: select a passage and follow its relationships to evidence, illustrations, and discussion.

## 2. AI-friendly: easy to query, easy to see, clear feedback

Every capability can be called from Python and the CLI, and each operation returns a structured result: what was written, whether there were issues, and the resulting identifiers. An AI starts with `command_help` to learn which tools exist and how to fill in their parameters, then works on specific targets without reading the whole project.

The complete version adds an MCP service and tools for reading the current view, reading by moment, following relationships, comments, and screenshots. A person can give the AI a view link or a comment attached to specific content, so the AI knows what "here" means and can follow earlier comments to see how an issue developed.

## 3. Developer-friendly: let the AI focus on one task

Making development easy was one of LayerWeave's original goals, and it is this branch's main purpose. When a new feature is needed, you can focus on that feature and reuse existing support for saving, numbering, transactions, change records, history, and undo.

Suppose you have linked characters to shots and want a summary of where each character appears. Write a small tool that queries the existing project. When it saves results, it reuses the project's read/write operations and change records, so mistakes can be undone.

Common ways to extend it:

- **Use the existing structures:** read and write layers, objects, and relationships through Python; query by position, range, or subtree.
- **Add your own types:** define new layer or object types with a Python class and a TOML declaration.
- **Add your own tables:** a tool's tables need not follow the layer/object structure; once declared, they join the change records and support history and undo.
- **Compose existing tools:** call several tools in one transaction; if any step fails, the whole operation rolls back.
- **For a dedicated interface:** use view plugins from the complete version.

Comments in the complete version were built this way: `Note` extends the ordinary text object, replies are relationships, and read states and the shared layout live in the view tool's own tables, without changing the existing structure.

This is what composition makes possible: a new feature can reuse existing parts, letting you focus on the relevant interfaces and its own logic.

It is also light. Its core and support layer use only Python's standard library and come to roughly three thousand lines of Python; the complete version's MCP integration and some skills have their own optional dependencies. Concrete operations live in replaceable tool packages; you can remove the ones you don't need and embed the underlying data operations in your own Python application. This branch currently has 33 internal commands across 13 tool packages, plus 12 skill materials for AI to read as needed; skills never run on their own.

Pick a minimal integration path in the [extension guide](docs/build-with-layerweave/README.md). The [tool-owned table example](examples/tool_tables.py) shows how a new tool shares records, history, and undo; individual calls are in the [public API](src/layerweave/support/API.md), and the overall design is in the [architecture notes](docs/architecture.md). These detailed guides are in Chinese.

## 4. The visual layer: in the complete version

The canvas is a window shared by people and AI: people look, point, and comment there, while the AI captures screenshots and reads where the person is looking. It syncs project changes every two seconds, so you can see how far the AI has got at any time; when you spot an issue, attach a comment there, and the AI can finish its current work before handling the comments one by one. This part is maintained on the visualization branch and shares this branch's data format and non-visual tools.

## Examples

| Example | Size | What you can see |
|---|---|---|
| [Article reading](examples/showcases/article-reading/README.md) · **recommended start** | 8 root layers, 32 objects, 68 relationships | An original Chinese essay beside its interpretation; trace a claim to evidence, illustrations, and discussion; five reading tasks that need only the basic Python/CLI tools |
| [Storyboard and H3](examples/showcases/donut-hole-h3/README.md) | 30 layers, 228 objects, 210 relationships | The 60 shots of a song, linked to sections and implementation notes; shots using generated media also lead to clip stills and the model; read through stills, with no video download required |
| [Hand-drawn MV](examples/showcases/donut-hole-tegaki/README.md) | 29 layers, 101 objects, 43 relationships | Another approach to the same song: story, picture design for 14 sections, implementation notes, and character sheets |
| [Late Bloom](examples/showcases/late-bloom-scroll/README.md) | 4 layers, 37 objects including 32 comments | Four AIs checking scene seams through comments and assembling a scroll; uses the complete version's comment types |

The twelve examples contain 125 layers, 691 objects, and 927 relationships; the other eight cover fiction, comics, courses, research, interactive stories, requirements, translation review, and code navigation. See the [example directory](examples/showcases/README.md). Their content and guides are currently in Chinese.

## Start developing

The initial supported platform is Windows. The code requires Python 3.11+ and SQLite 3.35+. After obtaining this branch, [uv](https://docs.astral.sh/uv/getting-started/installation/) can prepare Python for you. Run these commands in PowerShell from the source root:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

By default, uv downloads a missing Python version; initial setup and dependency downloads require internet access. You do not need to activate the environment; use its interpreter directly. If Python is already installed and you prefer pip:

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install -e ".[dev]"
.venv/Scripts/python.exe -X utf8 -B examples/read_write.py
```

An editable installation lets other working directories import layerweave, and source changes take effect immediately. pyproject.toml provides the local development entry point; this branch does not produce a separate end-user package. The core and ordinary tools need only the standard library at runtime; dev dependencies are for development checks. The examples use temporary data and do not modify real projects.

Installing from source also needs setuptools>=77.0.3 and wheel. pip prepares them in a temporary build environment by default, so it may download them even if setuptools is already installed. If installation stalls at Installing build dependencies, see [source installation troubleshooting (Chinese)](docs/developer-conventions.md#可编辑安装与构建依赖); turn off build isolation only after installing the build dependencies yourself.

To try the examples, set `$casePython = (Resolve-Path .venv/Scripts/python.exe).Path` in the same PowerShell session, then follow the chosen example's import and query steps.

## Explore the interfaces

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

`command_help` lists the installed tools with call examples; `config_help` explains what each layer and object type is for, its fields, and how types build on each other. The mcp metadata in commands is read by external adapters and does not start a service by itself.

- [Use the existing tools (Chinese)](src/layerweave/tool/builtin/usage/README.md): reading and writing projects, queries, time-based editing, history and undo, JSON exchange, and starter templates.
- [Source maintenance (Chinese)](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

All business-record writes go through one shared entry point; new types come with both a Python class and TOML. Complete tool packages can be replaced or removed. Skills are materials for AI to read as needed; check their dependencies, keys, and output directories before use.

## Verify changes

```powershell
.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s tests -t . -v
```

Tests are grouped into architecture, foundation, and tools, and use temporary data; see the [test guide (Chinese)](tests/README.md). Piped commands on Windows use -X utf8 explicitly; alternatively set PYTHONUTF8=1, as described in the [encoding notes (Chinese)](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## AI-assisted development

The maintainer leads the project's design and maintenance. Astra (Codex) assisted with development, testing, and documentation on this branch.

## License

LayerWeave source code is licensed under [MIT](LICENSE). Separate skills, external libraries, and services follow their own terms. Distribution notes for the view build and third-party web components are on the visualization branch.
