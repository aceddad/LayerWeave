# LayerWeave

[简体中文](README.md) | **English**

[GitHub](https://github.com/aceddad/LayerWeave/tree/visualization) · [Gitee](https://gitee.com/emotion1354414/layer-weave/tree/visualization) · [Quick install](#quick-install) · [Start using](#start-using-layerweave) · [Connect an AI](#connect-an-ai) · [Build your own tools](#compose-the-parts-build-your-own-tools)

**Fewer distractions: look at the part that matters, and focus on the task at hand.**

LayerWeave is an information management toolkit that AI agents can use and extend. Text, media references, evidence, and comments are organized by time, paragraph, or reading order, then connected through layers and relationships. Agents query, edit, and capture views through MCP; people can browse, point, and comment on the same project.

![A real music-video workspace: layers on the left, audio, stems, story, storyboards, and artwork on the timeline, with content and relationships in the Now panel](docs/images/handdraw-workspace.png)

*A real hand-drawn MV project: audio, stems, story, storyboards, and artwork organized by time. The Now panel shows the selected item and content and relationships at the playhead. Full production media is not included in the download. [View full-size image](docs/images/handdraw-workspace.png).*

## Quick install

The current release is the **0.7.9b1 Windows preview**. Choose either installation method in PowerShell.

With [uv](https://docs.astral.sh/uv/getting-started/installation/), including MCP dependencies:

```powershell
uv tool install --python 3.11 "layerweave[mcp]==0.7.9b1"
```

With Node.js 20+ / npm on Windows x64:

```powershell
npm install -g layerweave@0.7.9-beta.1
```

After installation, use the `layerweave` command. uv prepares an isolated Python environment; npm installs a launcher that prepares Python and the required dependencies on first use. Initial setup needs internet access. **Installation does not create an example project or open the view.** If the command is not found, follow the installer's PATH instructions and reopen your terminal and MCP client.

## Start using LayerWeave

### Connect an AI

**MCP is the recommended way for AI agents to use LayerWeave.** Agents can discover tools as needed, query and edit projects, inspect relevant views, and work through comments. People can view the same project and leave feedback on the canvas. Python and CLI interfaces remain available for scripts and custom tools.

<details>
<summary>MCP configuration after installing with uv or npm</summary>

Choose a working directory. The example uses `D:/my-layerweave`; save an `mcp.json` in that directory:

```json
{"workspace": "D:/my-layerweave"}
```

After installing with uv, add this server to your client's MCP configuration:

```json
{
  "mcpServers": {
    "layerweave": {
      "command": "layerweave",
      "args": ["mcp", "--config", "D:/my-layerweave/mcp.json"]
    }
  }
}
```

After installing with npm, replace the `layerweave` server entry with this one on Windows:

```json
{
  "command": "cmd",
  "args": ["/c", "layerweave", "mcp", "--config", "D:/my-layerweave/mcp.json"]
}
```

The configuration location depends on your client. Replace the example paths. If the client cannot find the command, use `(Get-Command layerweave).Source` to locate the uv-installed program, or `(Get-Command layerweave.cmd).Source` to locate the npm launcher.

Once connected, have the AI call `layerweave_help` to find tools for your task, then create or open your own project. Running a demo is optional. The client manages the server process; starting MCP does not open the canvas.

Default databases and projects, tool exposure, uvx/npx, and existing Python environments are covered in the [MCP guide (Chinese)](src/layerweave/tool/builtin/shared/mcp/README.md) and [npm guide](distribution/npm/README.en.md).

</details>

### Open or create your own project

| Command | Purpose |
|---|---|
| `layerweave --help` | List available commands |
| `layerweave view ./project.sqlite3` | Open an existing database |
| `layerweave new ./my-project --template subtitles` | Create a project from the subtitles template and open its view |
| `layerweave help project_overview` | Read the project overview tool's help |

The view and MCP can work independently or access the same project together. Keep the terminal running while using the view; Ctrl+C stops the server. Add `--no-browser` to print the URL without opening a browser.

### Optional: try an example

```powershell
layerweave demo
```

This opens the article-reading example in `./layerweave-demo/article-reading`. **Running the same command again preserves your objects, comments, layout, and media edits.** Use `layerweave demo --list` to see all twelve examples. Others download on demand, for example with `layerweave demo comic-creation --dir ./my-comic`.

<details>
<summary>Try it without installing first</summary>

With uv or npm available, use either command directly:

```powershell
uvx layerweave@0.7.9b1 demo
```

```powershell
npx --yes layerweave@0.7.9-beta.1 demo
```

</details>

Project data stays separate from the download cache. More options are in the [launcher guide (Chinese)](src/layerweave/tool/builtin/shared/launcher/README.md); installation files are on [GitHub Releases](https://github.com/aceddad/LayerWeave/releases/tag/v0.7.9b1). To import or extend the kernel in a Python project, start with [development and extension](#compose-the-parts-build-your-own-tools).

## Keep attention on the relevant part

### Collapse what you do not need right now

Collapse layers you are not working with while keeping their names, object counts, and expand controls visible. Make room for the current task and expand them again when needed.

![The user collapses stems, story, video planning, and other layers while their counts and expand controls remain visible](docs/images/handdraw-folded.png)

*[View the full-size collapsed view](docs/images/handdraw-folded.png). Collapsing changes the display; it does not delete content.*

### Same data, different areas of focus

At the same **2:57** moment, the AI looks at four relevant layers and selects a different piece of artwork. It can read object text and relationships as well as capture screenshots. These temporary filters leave the person's browsing state unchanged.

![An AI view around 2:57, filtered to interpretation, story, artwork, and shot design, with an independently selected image](docs/images/ai-focus-177.png)

*[View the full-size AI view](docs/images/ai-focus-177.png). “User collapsed” labels preserve the person's focus choices while allowing the AI to inspect that content for its task.*

| Need during work | What LayerWeave provides |
|---|---|
| Leave feedback that can be followed up | Comments, replies, and pending states attached to the relevant content |
| See how far the AI has got | A canvas that syncs project changes every two seconds |
| Correct an earlier edit | Change records, history, and undo, with explicit conflict reports |

Use seconds for video and music, paragraphs for articles, or pages and panels for comics. The project defines what each axis means; units are not converted automatically. Images, audio, and video are referenced by path or URL. Skills and external tools handle media generation and processing.

Understanding screenshots requires a vision-capable AI. The caller decides when to read comments and which agent handles them. Discover individual tools through help or the [view guide (Chinese)](src/layerweave/tool/builtin/view/GUIDE.md#给-ai-用).

## Try another setting

| Example | What you can do |
|---|---|
| [Article reading](examples/showcases/article-reading/README.md) · recommended start · [screenshot](docs/images/article-reading.png) | Compare text with its interpretation, then trace claims to evidence, illustrations, and discussion |
| [Storyboard and H3](examples/showcases/donut-hole-h3/README.md) | Compare shots, story sections, and implementation notes; trace shared assets |
| [Hand-drawn MV](examples/showcases/donut-hole-tegaki/README.md) | Keep listening notes, story, visual design, character sheets, and implementation records together |
| [Late Bloom](examples/showcases/late-bloom-scroll/README.md) | Follow four AIs using comments to coordinate seams and colors in one animated SVG scroll |

The twelve examples also cover fiction, comics, course study, research, interactive stories, requirements design, translation review, and code navigation. See the [full directory](examples/showcases/README.md). The article is an original essay; the hand-drawn and H3 examples use stills without the song or video files. Recreating the full films needs additional media. Example content and detailed guides are currently in Chinese.

## Compose the parts, build your own tools

LayerWeave aims to **reduce the attention spent on coordination**. Tools handle finding things, matching positions, and tracking changes. When building a new feature, you should be able to focus on its own logic, too.

The approach is **composition**: objects belong to layers, layers form a tree, and `bind` relationships connect them. The kernel provides the basic structure; the support layer handles storage, IDs, transactions, and change records. Tools, skills, and plugins can be added as needed. The core and support layer use only Python's standard library.

For example, a tool that lists “every shot featuring each character” can query the existing relationships. It can reuse the same storage and change records when saving results, with undo available through the undo tool. Tools can also declare their own tables for data that needs a different structure.

**You and your agents are welcome to build applications on this kernel.** This branch is a usable application example, and the view itself is a tool package. Built-in tools demonstrate how to reuse the kernel; separate view plugins demonstrate how to extend the application. Comments are one such example: `Note` extends the text object, replies use relationships, and read states and layout live in the view's own tables.

- [main development branch](https://github.com/aceddad/LayerWeave/tree/main): the kernel, support layer, and non-visual tools, with a minimal Python example.
- [Extension guide](docs/build-with-layerweave/README.md): add types or tables, compose tools, or consume incremental changes.
- [Public API](src/layerweave/support/API.md) and [tool-owned table example](examples/tool_tables.py): reuse the existing capabilities in your own features.
- [Official view plugins](https://github.com/aceddad/layerweave-plugins): overview, seams, preview, and web, all separately installed.

## Documentation and optional components

[Using tools](src/layerweave/tool/builtin/usage/README.md) · [JSON exchange and templates](src/layerweave/tool/builtin/usage/exchange/README.md) · [View and plugins](src/layerweave/tool/builtin/view/README.md) · [Source development](docs/developer-conventions.md) · [Documentation index](docs/README.md)

Ordinary data management and article reading need no API key, FFmpeg, or official view plugin. Server-side frame extraction, video thumbnails, and waveforms need [FFmpeg (Chinese guide)](src/layerweave/tool/builtin/view/GUIDE.md#选装-ffmpeg); AI screenshots need Chrome, Edge, or Chromium. The web UI supports Chinese and English. This release includes view component 0.31.1. The detailed documentation, CLI/help descriptions, and templates are currently in Chinese; machine-readable names are unchanged.

## AI-assisted development

The maintainer leads the project's design and maintenance. Astra (Codex) and Claude assisted with development, testing, and documentation on this branch.

## License

LayerWeave itself is licensed under [MIT](LICENSE). Bundled web components keep their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Separate plugins, skills, and external services follow their own terms.
