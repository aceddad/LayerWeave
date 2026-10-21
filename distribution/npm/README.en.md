# LayerWeave npm launcher

[简体中文](https://github.com/aceddad/LayerWeave/blob/v0.7.9b1/distribution/npm/README.md) | English

Start LayerWeave with one command on Windows x64. This package prepares the runtime and forwards arguments. All example, project, view, and MCP behavior lives in the same Python application used by uv.

## Quick start

Run from your chosen working directory:

```powershell
npx --yes layerweave@0.7.9-beta.1 demo
```

This npm preview uses the next dist-tag and pins Python package `0.7.9b1`. It supports Windows x64 and Node.js 20+. Python and uv do not need to be installed beforehand.

## Commands

- `demo`: prepare and open article reading in `./layerweave-demo/article-reading`.
- `demo --list`: list examples; other examples download on demand.
- `demo comic-creation --dir ./my-comic`: prepare another example at a chosen location.
- `view ./project.sqlite3` or `view ./my-comic`: open an existing database or launcher project.
- `new ./my-project --template subtitles`: create a project from a template.
- `help project_overview`: reuse the existing detailed tool help.
- `mcp --config ./mcp.json`: run MCP; the npm launcher requests the matching mcp extra.

Reopening preserves edits. The server runs in the foreground; Ctrl+C stops it without deleting project data. Use `--no-browser` to print the URL only, or `--port` to choose a port. Environment setup messages go to stderr, leaving MCP stdout for its protocol.

## Runtime and maintenance

The launcher reuses uv >= 0.9 from PATH when available. Otherwise it downloads a pinned official uv archive, verifies SHA-256, and extracts it into the user's cache. uv prepares an independent Python 3.11 and application environment without changing PATH or shell configuration. First use needs internet access; later runs reuse caches.

The default cache is `%LOCALAPPDATA%/LayerWeave/cache`. LAYERWEAVE_CACHE_DIR changes its location; LAYERWEAVE_UV selects an existing executable; LAYERWEAVE_PYTHON_PACKAGE selects a local wheel or full Python requirement for unpublished-package testing. Custom sources should match the npm package's Python version and include the mcp extra when needed.

Run `npm test` to verify and `npm pack` to build. Only the launcher is shipped: no user data, install-time scripts, or duplicate Python implementation. Registry publication requires the maintainer's accounts and authorization.
