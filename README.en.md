# LayerWeave

[简体中文](README.md) | **English**

[GitHub](https://github.com/aceddad/LayerWeave/tree/visualization) · [Gitee](https://gitee.com/emotion1354414/layer-weave/tree/visualization) · [Quick start](#quick-start) · [Connect an AI](#connect-an-ai) · [Build your own tools](#compose-the-parts-build-your-own-tools)

**Fewer distractions: look at the part that matters, and focus on the task at hand.**

LayerWeave keeps text, media references, evidence, and comments in one project. Arrange them by time, paragraph, or reading order, then connect them through layers and relationships. People can browse, point, and comment on the canvas; AI agents can query the same content, capture its view, and follow links back to its sources.

![A real music-video workspace: layers on the left, audio, stems, story, storyboards, and artwork on the timeline, with content and relationships in the Now panel](docs/images/handdraw-workspace.png)

*A real hand-drawn MV project: audio, stems, story, storyboards, and artwork organized by time. The Now panel shows the selected item and content and relationships at the playhead. Full production media is not included in the download. [View full-size image](docs/images/handdraw-workspace.png).*

## Quick start

The current release is the **0.7.9b1 Windows preview**. Open PowerShell in your chosen working directory and use either entry point.

With [uv](https://docs.astral.sh/uv/getting-started/installation/):

```powershell
uvx layerweave@0.7.9b1 demo
```

With Node.js 20+ / npm on Windows x64:

```powershell
npx --yes layerweave@0.7.9-beta.1 demo
```

The command prepares the environment and opens the article-reading example in your browser. uv manages Python; the npm entry point prepares uv and an independent Python 3.11 when needed. Initial setup needs internet access.

The project is saved in `./layerweave-demo/article-reading`. **Running the same command again preserves your edits**, including objects, comments, layout, and media. Keep the terminal running while using the view; Ctrl+C stops the server. Add `--no-browser` to print the URL without opening a browser.

Replace the final `demo` argument to do more:

| Arguments | Purpose |
|---|---|
| `demo --list` | List all twelve examples |
| `demo comic-creation --dir ./my-comic` | Download and open the comic example in a chosen directory |
| `view ./project.sqlite3` | Open an existing database |
| `new ./my-project --template subtitles` | Create a project from the subtitles template |
| `help project_overview` | Read the project overview tool's help |

Article reading is bundled; other examples download on demand. Project data stays separate from the download cache. See the [launcher guide (Chinese)](src/layerweave/tool/builtin/shared/launcher/README.md) for more options, or get installation files from [GitHub Releases](https://github.com/aceddad/LayerWeave/releases/tag/v0.7.9b1).

## Connect an AI

LayerWeave provides a stdio MCP server that compatible clients can start automatically. **The view and MCP work independently and can also access the same project together.**

The example below uses `D:/my-layerweave`. Replace it with the working directory where you ran the demo, and save an `mcp.json` there:

```json
{"workspace": "D:/my-layerweave"}
```

With uv installed, add this server to your client's MCP configuration:

```json
{
  "mcpServers": {
    "layerweave": {
      "command": "uvx",
      "args": ["--python", "3.11", "--from", "layerweave[mcp]==0.7.9b1", "layerweave", "mcp", "--config", "D:/my-layerweave/mcp.json"]
    }
  }
}
```

<details>
<summary>Connect with npm instead (Windows)</summary>

Replace the `layerweave` server entry above with this one. npm prepares Python and the MCP dependencies automatically:

```json
{
  "command": "cmd",
  "args": ["/c", "npx", "--yes", "layerweave@0.7.9-beta.1", "mcp", "--config", "D:/my-layerweave/mcp.json"]
}
```

</details>

The configuration location depends on your client. Replace the example paths; if the client cannot find uvx, use `(Get-Command uvx).Source` in PowerShell to find its full path. Once connected, try asking:

> Use layerweave_help to discover the tools, then inspect layerweave-demo/article-reading/project.sqlite3. Find the interpretation and evidence linked to the first paragraph.

The client manages the server process. Starting MCP does not open the canvas. Default databases and projects, tool exposure, and an existing Python environment are covered in the [MCP guide (Chinese)](src/layerweave/tool/builtin/shared/mcp/README.md).

## Keep attention on the relevant part

When you say “the transition at 30–35 seconds feels wrong,” attach a comment to that span or give the AI a view link. It can read the content across layers, capture the same range, follow relationships to the story, assets, and earlier discussion, then edit the relevant objects and check the result. Unfinished feedback stays with the content for later.

| What you want to do | What LayerWeave provides |
|---|---|
| Find the information related to “here” | Read by moment, range, layer, or subtree; follow relationships back to sources |
| Let AI compare the picture with the data | Query object identities, text, and relationships alongside a screenshot of the corresponding view |
| Leave feedback without interrupting work | Comments, replies, and pending states that people and agents can revisit |
| See how far the AI has got | A canvas that syncs project changes every two seconds |
| Recover from a mistaken edit | Change records, history, and undo, with explicit conflict reports |

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
