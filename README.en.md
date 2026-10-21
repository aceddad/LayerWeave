# LayerWeave

[简体中文](README.md) | **English**

**0.7.8 public preview · Windows**

**Fewer distractions: look only at the part that matters, and do only the task at hand.**

LayerWeave is an information management tool for people and AI. It places text, media references, and comments on axes ordered by time or sequence, organizes them with layers and relationships, and lets every participant find everything relevant to "this moment, right here."

This branch demonstrates an application built on the LayerWeave kernel; the view itself is a built-in tool package. The built-in tools show how to reuse the kernel, and the separate view plugins show how to extend the application further. These implementations are ready to use and serve as references for you and your agents to build new tools and applications.

It follows one design principle: **reduce scattered attention.** In most tasks, only a small part needs real thought, yet much of the attention goes into finding things, matching positions, tracking changes, and explaining which part you meant. LayerWeave hands that work to tools:

- An AI reads only the relevant content for a given span of time, instead of the whole project every time.
- A person points at the screen instead of describing which section or which shot again and again.
- Feedback stays next to the content it concerns and waits until the other side is ready, without interrupting their current work.
- When building a new feature, reuse storage, numbering, change records, and undo to keep attention on the feature itself.

The method is **composition** together with **information management**. Composition keeps every part small and single-purpose: objects sit in layers, layers form a tree, and relationships connect them; the core handles only the basic structure, while queries, editing, the view, skills, and plugins are parts you can add, remove, or replace. The finer things are split, the more scattered the information becomes, so information management ties those pieces back together by time, sequence, and relationship, and any piece can be found directly. Whether working through information or building a feature, you can focus on the part at hand.

The four parts below explain how.

## 1. Information management: see everything at the same moment together

Content sits on axes: videos and songs by the second, articles by paragraph, comics by page and panel, courses by learning step. Each item on an axis is an object with its own identity. Objects belong to layers, and layers form a tree; tracks such as shot notes, media, and dialogue can be compared at the same moment when they share a time scale. Paragraph numbers, page numbers, and seconds are not automatically converted. Comments are stored in sequence and point to the content they discuss through relationships and ranges. Relationships connect objects: which story beat a shot is based on, which piece of evidence a conclusion cites, which second a piece of feedback is about.

Checking a moment no longer means searching everywhere. Ask "what is at seconds 30–35?" and you get every layer's content in that span, the relationships between items, existing comments, and which tracks are empty there. To find out why, follow the relationships; to change something, edit that object by its identity instead of rewriting the whole section. Every change is recorded, with history and undo.

Time is not the only order. When content follows paragraphs, pages, or reading order, you can still select a passage and follow its relationships to evidence, illustrations, and discussion. The [twelve examples](examples/showcases/README.md) use this same structure for storyboards, hand-drawn MVs, close reading, fiction, comics, courses, research, interactive stories, requirements, translation review, and code navigation.

## 2. AI-friendly: easy to query, easy to see, clear feedback

LayerWeave was designed for AI use from the start. Every capability is available through Python, the CLI, or MCP. An AI starts with `layerweave_help` to learn which tools exist and how to fill in their parameters, then works on specific targets without reading the whole project. Each operation returns a structured result: what was written, whether there were issues, and the resulting identifiers.

A real task looks roughly like this. You write: "Seconds 30–35 feel disjointed. Take a look."

1. You select seconds 30–35 on the canvas, or send the AI a link to your current view.
2. The AI reads each layer's content, relationships, and comments in that span.
3. It captures a screenshot of the same range and compares the picture with the data to find the object at fault.
4. It follows relationships back: which story beat the shot is based on, which asset it uses, whether anyone has discussed it before.
5. It edits that object, then reads or captures the range again to check the result.
6. Anything left open is written down as a comment for next time.

The tools behind these steps:

| Tool | What it does |
|---|---|
| `view_state` | Reads the current view: which project and board, what is selected, where the playhead is |
| `view_at` | Reads each layer's content, relationships, and comments at a moment or over a range; without a range, it reads where the user is looking |
| `view_screenshot` | Captures the canvas, a given range, the target of a comment, or an installed plugin page; can locate the area directly from a view link |
| `view_walk` | Follows relationships step by step from an object, layer, or comment, with limits on direction, depth, and count |
| `view_note` | Adds, replies to, retargets, and marks comments as read or resolved; finds what is still waiting for you |
| `view_layout` | Reads and adjusts board positions, sizes, and joins |

Screenshots supply the visuals; queries supply object identities, text, and relationships. The shared project, selected objects, and position range connect the two.

This also makes human feedback more precise. Instead of describing "somewhere past the middle, around that transition" in a chat, attach a comment to that object or those seconds. When the AI reads the comment, it knows exactly what it refers to, and it can follow earlier comments and replies to see how the issue developed.

A few notes: understanding images is the job of an AI with vision capabilities, and LayerWeave itself does not do image search or image recognition. The screenshot tool opens a separate read-only page, so it never changes the view you are using, and it captures only LayerWeave's own pages. When comments are read and which AI handles them is up to the caller; LayerWeave does not include a multi-agent scheduler or timed wake-ups. See [view tools for AI (Chinese)](src/layerweave/tool/builtin/view/GUIDE.md#给-ai-用).

## 3. Developer-friendly: let the AI focus on one task

Making development easy was one of LayerWeave's original goals. When a new feature is needed, an AI or developer can focus on that feature and reuse existing support for saving, numbering, transactions, change records, history, and undo.

Suppose you have linked characters to shots and want a summary of where each character appears. Write a small tool that queries the existing project. When it saves results, it reuses the project's read/write operations and change records, so mistakes can be undone.

Common ways to extend it:

- **Use the existing structures:** read and write layers, objects, and relationships through Python; query by position, range, or subtree.
- **Add your own types:** define new layer or object types with a Python class and a TOML declaration.
- **Add your own tables:** a tool's tables need not follow the layer/object structure; once declared, they join the change records and support history and undo.
- **Compose existing tools:** call several tools in one transaction; if any step fails, the whole operation rolls back.
- **Build a dedicated interface:** write a view plugin that provides its own pages beyond the canvas.

Comments were built exactly this way: `Note` extends the ordinary text object, replies are relationships, and read states and the shared layout live in the view tool's own tables. A full collaboration feature grew out of the existing structure without changing it.

This is what composition makes possible: a new feature can reuse existing parts, letting you focus on the relevant interfaces and its own logic.

It is also light. Its core and support layer use only Python's standard library and come to roughly three thousand lines of Python; MCP and some skills have their own optional dependencies. Concrete operations live in replaceable tool packages; you can leave out the ones you don't need and embed the underlying data operations in your own Python application.

Pick a minimal integration path in the [extension guide](docs/build-with-layerweave/README.md). The [tool-owned table example](examples/tool_tables.py) shows how a new tool shares records, history, and undo; individual calls are in the [public API](src/layerweave/support/API.md), and the overall design is in the [architecture notes](docs/architecture.md). These detailed guides are in Chinese.

## 4. The visual layer: a window shared by people and AI

The first three parts work without opening the canvas. The visual layer is a window onto the same data: people look, point, and comment there, while the AI captures screenshots and reads where the person is looking.

- **See how far the AI has got.** The canvas syncs project changes every two seconds, so content the AI writes soon appears at its place on the timeline, and you can point out problems as you watch.
- **Comment without interrupting.** When you spot an issue, attach a comment there. The AI can finish what it is doing, then work through the comments, reply, and mark them resolved.
- **Follow the trail.** Start from an object and follow relationship lines to its sources, assets, and discussion; search for objects, review changes, or browse all assets at once.
- **Review the result.** When the AI is done, check the whole piece against the timeline on the canvas, looking at the same content the AI sees.

[Late Bloom](examples/showcases/late-bloom-scroll/README.md) shows this kind of collaboration: four AIs each painted one scene as an animated SVG, checked seams, colors, and changes through 32 comments, and joined them into a 9600×1400 scroll.

The web interface supports Chinese and English. The official plugins (overview, seams, preview, web) are installed separately, and the canvas works without any.

## Start with an example

| Example | Size | What you can see |
|---|---|---|
| [Article reading](examples/showcases/article-reading/README.md) · **recommended start** | 8 root layers, 32 objects, 68 relationships | An original Chinese essay of about 1,350 characters beside its paragraph-by-paragraph interpretation; start from a claim and follow relationships to evidence, illustrations, and discussion; five runnable reading tasks |
| [Storyboard and H3](examples/showcases/donut-hole-h3/README.md) | 30 layers, 228 objects, 210 relationships | The 60 shots of a song, linked to sections and implementation notes; shots using generated media also lead to clip stills and the model used, showing how several shots share one asset |
| [Hand-drawn MV](examples/showcases/donut-hole-tegaki/README.md) | 29 layers, 101 objects, 43 relationships | Another approach to the same song: listening notes and story, picture design for 14 sections with matching implementation notes, character sheets, and an overview of 32 moments |
| [Late Bloom](examples/showcases/late-bloom-scroll/README.md) | 4 layers, 37 objects including 32 comments | Four AIs collaborating through comments on one scroll; includes an animated preview that opens directly in a browser |

The article in the reading example is an original Chinese essay written for the example, not the full text or a translation of the external articles; opening those sources needs internet access. The hand-drawn and H3 examples are "no-video reading editions": the public package shows their structure and visuals through stills, without the song or video files, so the films cannot be regenerated from the download alone.

Eight more examples cover fiction writing, comics, course study, research, interactive stories, requirements design, translation review, and code navigation. Together the twelve examples contain 125 layers, 691 objects, and 927 relationships; see the [example directory](examples/showcases/README.md) for the full list and setup. Their content and detailed guides are currently in Chinese.

## What's included

| Part | In 0.7.8 |
|---|---|
| Internal commands | 46 across 15 tool packages: querying, range editing, copying and transfer, JSON exchange, checks, history and undo, the view, and more |
| Skill materials | 12 for AI to read as needed (stems and cue sheets, image generation, halftones, video generation and verification, motion reference, glyph deformation, and more); they are instructions and scripts and never run on their own |
| View | 0.31.0, with a Chinese and English web interface; four official plugins are installed separately |
| Integration | Python, CLI, and optional MCP; by default MCP exposes 4 general entry points plus three shortcuts: inbox, reply, and screenshot |
| Starter templates | Subtitles, storyboard, and hand-drawn MV; their structure can be freely adapted |

Images, audio, and video are referenced by file path or URL and are not copied into the project database. Generating and processing media is done by the caller, skills, or external tools.

## Windows quick start

The initial supported platform is Windows. The code requires Python 3.11+ and SQLite 3.35+; these examples use Python 3.11. [uv](https://docs.astral.sh/uv/getting-started/installation/) can prepare Python and the environment for you, or you can use an existing Python installation. Node is not needed to use the web view.

### Install the complete package with uv

Obtain `layerweave-0.7.8-py3-none-any.whl` and place it in your chosen working directory. After installing uv, run these commands in PowerShell from that directory:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

By default, uv downloads a suitable Python version if one is missing. Initial setup and dependency downloads require internet access. You do not need to activate the environment; later commands use its interpreter directly. [How uv manages Python](https://docs.astral.sh/uv/concepts/python-versions/)

If Python is already installed and you prefer pip:

```powershell
python -X utf8 -m venv .venv
.venv/Scripts/python.exe -X utf8 -m pip install "./layerweave-0.7.8-py3-none-any.whl[mcp]"
```

`[mcp]` adds the optional dependencies for AI integration; omit it for Python/CLI-only use. Installing the package does not install the official view plugins. These commands use a local wheel and do not assume this version is available on PyPI.

The wheel is already built, so installing LayerWeave itself does not require setuptools. The `[mcp]` dependencies may still need downloading, so the wheel is not a complete offline environment. Editable installation is only for source development; if it stalls while preparing build dependencies, see [source installation troubleshooting (Chinese)](docs/developer-conventions.md#可编辑安装与构建依赖).

### Try the article-reading example first

Copy `examples/showcases` from the matching source distribution, or extract the examples ZIP into an `examples` folder in your working directory, so that `examples/showcases/article-reading/project.json` exists. The software and the examples are distributed separately; this one is enough to start. The [example directory](examples/showcases/README.md) covers the other eleven.

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

Open the local URL printed by the server. Read the essay and interpretation layers, then pick a claim and follow its relationships to evidence and illustrations. The [article-reading guide (Chinese)](examples/showcases/article-reading/README.md) has five focused reading tasks. Keep the database in the example directory so relative image paths resolve. Use the project ID from the import result; importing again creates another copy.

This starter example needs no API key, FFmpeg, Node, or view plugin. Its content is in Chinese and works offline; only the external source articles need internet access.

### Create your own project

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.developer.database.cli project.sqlite3
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli templates
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.usage.exchange.cli apply project.sqlite3 --template subtitles --new-project
```

Templates cover subtitles, storyboards, and hand-drawn MVs, and their structure can be freely adapted after import. Pass the returned project ID to the view or query tools, and check help for parameters.

FFmpeg is an optional external program; the wheel, `[mcp]`, and uv do not install it. Ordinary data management and text views don't need it. Server-side frame extraction requires FFmpeg, and thumbnails and waveforms also use it; without it, those browsing features fall back or are not shown. Add its bin directory to PATH, or set the `FFMPEG` environment variable to the full path of ffmpeg.exe; see [setup and affected features (Chinese)](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg). AI screenshots also require Chrome, Edge, or Chromium. The user or AI chooses where media output goes.

## Connect an AI / MCP client

Save an `mcp.json` in your project working directory, with workspace set to its actual absolute path:

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

Replace the interpreter and configuration paths with your actual locations; where this configuration goes depends on the client. An AI can call `layerweave_help` first to see what is available, then work on specific targets without reading the whole project each time. Pass the database and project ID per call, or configure defaults; see the [MCP guide (Chinese)](src/layerweave/tool/builtin/shared/mcp/README.md).

For MCP-only use, uvx can prepare the environment and start the service in one command:

```powershell
uvx --python 3.11 --from "./layerweave-0.7.8-py3-none-any.whl[mcp]" layerweave-mcp --config ./mcp.json
```

This runs a persistent stdio service, normally managed by an MCP client; it does not open the web view. Use absolute paths in a client's uvx configuration; the MCP guide includes a full example. Once the package has a published download URL, that URL can be used as the source as well.

## Find tools and documentation

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

`command_help` lists the installed commands with call examples; `config_help` explains what each layer and object type is for, its fields, and how types build on each other. The detailed guides below are currently in Chinese, as are CLI/help descriptions and bundled templates; machine-readable field and command names are unchanged.

- [Usage guide](src/layerweave/tool/builtin/usage/README.md): start from a task, choose a tool, and inspect its inputs, outputs, and examples.
- [JSON exchange and templates](src/layerweave/tool/builtin/usage/exchange/README.md): batch operations and starting structures.
- [View and plugins](src/layerweave/tool/builtin/view/README.md): interface usage. [Official plugins](https://gitee.com/emotion1354414/layerweave-plugins) are installed separately; the canvas works with none.
- [Source development](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

`visualization` is the complete version. `main` contains the development sources without the view, keeps direct Python/CLI entry points, and shares the core, support layer, and non-visual tools. The view, MCP service, and release packaging are maintained on the complete branch. Commands use `-X utf8` so piped output stays readable on Chinese Windows; see the [encoding notes (Chinese)](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## AI-assisted development

The maintainer leads the project's design and maintenance. Astra (Codex) and Claude assisted with development, testing, and documentation on this branch.

## License

LayerWeave itself is licensed under [MIT](LICENSE). Bundled web components keep their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Separate plugins, skills, and external services follow their own terms.
