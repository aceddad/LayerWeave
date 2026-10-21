# LayerWeave

[简体中文](README.md) | **English**

[GitHub](https://github.com/aceddad/LayerWeave/tree/visualization) · [Gitee](https://gitee.com/emotion1354414/layer-weave/tree/visualization) · [Kernel development branch](https://github.com/aceddad/LayerWeave/tree/main)

**0.7.9b1 public preview · Windows**

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
| Internal commands | 47 across 16 tool packages: unified startup, querying, range editing, copying and transfer, JSON exchange, checks, history and undo, the view, and more |
| Skill materials | 12 for AI to read as needed (stems and cue sheets, image generation, halftones, video generation and verification, motion reference, glyph deformation, and more); they are instructions and scripts and never run on their own |
| View | 0.31.0, with a Chinese and English web interface; four official plugins are installed separately |
| Integration | Python, CLI, and optional MCP; by default MCP exposes 4 general entry points plus three shortcuts: inbox, reply, and screenshot |
| Starter templates | Subtitles, storyboard, and hand-drawn MV; their structure can be freely adapted |

Images, audio, and video are referenced by file path or URL and are not copied into the project database. Generating and processing media is done by the caller, skills, or external tools.

## Windows quick start

Open PowerShell in your chosen working directory and choose either entry point.

With [uv](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
uvx layerweave@0.7.9b1 demo
```

With Node.js 20+ / npm on Windows x64:

```powershell
npx --yes layerweave@0.7.9-beta.1 demo
```

Both entry points use the same Python implementation, prepare the article-reading example, and open your browser. uv manages Python; the npm entry point automatically prepares uv and an independent Python 3.11 when needed. Initial setup needs internet access. The uv route does not require Node.

The project lives in `./layerweave-demo/article-reading`. Running the same command again preserves objects, comments, layout, and media edits. Keep the terminal running while using the view; Ctrl+C stops the server. Use `--no-browser` to print the URL without opening a browser.

Replace the final `demo` argument with one of these:

| Arguments | Purpose |
|---|---|
| `demo --list` | List all twelve examples |
| `demo comic-creation --dir ./my-comic` | Download and open the comic example on demand |
| `view ./project.sqlite3` | Open an existing database; optionally select a project with `--project 1` |
| `new ./my-project --template subtitles` | Create a project from the subtitles template |
| `help project_overview` | Read the tool's detailed help |

Article reading is bundled; other examples download and cache on first use. Projects live in your working directory, so clearing caches does not delete them. See the [launcher guide (Chinese)](src/layerweave/tool/builtin/shared/launcher/README.md), [npm guide](distribution/npm/README.en.md), and [example directory](examples/showcases/README.md).

### Install into your own Python environment

For scripts that import LayerWeave, or a persistent development environment:

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe "layerweave[mcp]==0.7.9b1"
```

`[mcp]` adds the optional AI integration dependencies; omit it for Python/CLI-only use. The wheel, source archive, and npm package are also available on the [GitHub Release page](https://github.com/aceddad/LayerWeave/releases/tag/v0.7.9b1) for installation from local files. Installing LayerWeave itself from a wheel does not require setuptools; runtime dependencies may still need downloading.

Ordinary data management and article reading need no API key, FFmpeg, or official view plugin. FFmpeg is optional for server-side frame extraction, thumbnails, and waveforms. AI screenshots require Chrome, Edge, or Chromium. See the [FFmpeg guide (Chinese)](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg). Official view plugins remain separately installed.

## Connect an AI / MCP client

Save an `mcp.json` in your project working directory, with workspace set to its actual absolute path:

```json
{"workspace": "D:/my-project"}
```

When using the Python environment created above, configure a stdio MCP client as follows:

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
uvx --python 3.11 --from "layerweave[mcp]==0.7.9b1" layerweave-mcp --config ./mcp.json
```

This runs a persistent stdio service, normally managed by an MCP client; it does not open the web view. Use an absolute configuration-file path in your client; the MCP guide includes a full example. You can also point `--from` at a downloaded local wheel.

## Find tools and documentation

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

`command_help` lists the installed commands with call examples; `config_help` explains what each layer and object type is for, its fields, and how types build on each other. The detailed guides below are currently in Chinese, as are CLI/help descriptions and bundled templates; machine-readable field and command names are unchanged.

- [Usage guide](src/layerweave/tool/builtin/usage/README.md): start from a task, choose a tool, and inspect its inputs, outputs, and examples.
- [JSON exchange and templates](src/layerweave/tool/builtin/usage/exchange/README.md): batch operations and starting structures.
- [View and plugins](src/layerweave/tool/builtin/view/README.md): interface usage. [Official plugins](https://github.com/aceddad/layerweave-plugins) are installed separately; the canvas works with none.
- [Source development](docs/developer-conventions.md), [runnable examples](docs/examples.md), and [documentation index](docs/README.md).

`visualization` is the complete version. `main` contains the development sources without the view, keeps direct Python/CLI entry points, and shares the core, support layer, and non-visual tools. The view, MCP service, and release packaging are maintained on the complete branch. Commands use `-X utf8` so piped output stays readable on Chinese Windows; see the [encoding notes (Chinese)](src/layerweave/tool/builtin/usage/README.md#命令行编码).

## AI-assisted development

The maintainer leads the project's design and maintenance. Astra (Codex) and Claude assisted with development, testing, and documentation on this branch.

## License

LayerWeave itself is licensed under [MIT](LICENSE). Bundled web components keep their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Separate plugins, skills, and external services follow their own terms.
