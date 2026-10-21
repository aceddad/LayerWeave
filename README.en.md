# LayerWeave kernel and development sources

[简体中文](README.md) | **English**

[GitHub](https://github.com/aceddad/LayerWeave/tree/main) · [Gitee](https://gitee.com/emotion1354414/layer-weave/tree/main) · [Complete application and MCP](https://github.com/aceddad/LayerWeave/tree/visualization)

**Fewer distractions: reuse the groundwork and focus on the feature you are building.**

LayerWeave organizes information by time or sequence using layers, objects, and relationships. It provides shared storage, IDs, transactions, and change records so you and your agents can build queries, editors, collaboration tools, or specialized interfaces from reusable parts.

This is the **main development branch**, containing the kernel, support layer, and non-visual tools. The ready-to-use canvas application, MCP server, and release packages are on [visualization](https://github.com/aceddad/LayerWeave/tree/visualization), which also demonstrates an application built on the kernel.

## Run your first example

Windows is the currently supported platform. The code needs Python 3.11+ and SQLite 3.35+. With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, get this branch and prepare an environment in PowerShell:

```powershell
git clone --branch main https://github.com/aceddad/LayerWeave.git layerweave-core
cd layerweave-core
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe -e .
```

If you already have the source, start at `uv venv`. uv downloads a missing Python runtime; initial installation may need internet access. Editable installation makes source changes take effect immediately. Existing Python environments, build dependencies, and test setup are covered in the [development guide (Chinese)](docs/developer-conventions.md).

Save the following as `example.py`. It creates a temporary project, saves a text layer and object, and loads them back as Python instances:

```python
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.models import Text, TextLayer
from layerweave.support.api import (
    initialize_database, open_database, transaction,
    save_layer, save_object, load_layer,
)

with TemporaryDirectory() as folder:
    database = initialize_database(Path(folder) / "example.sqlite3")
    with closing(open_database(database)) as connection:
        with transaction(connection) as write:
            project = write.create("project", {"name": "Reading notes"})

        layer = TextLayer(name="Paragraphs")
        save_layer(connection, project["id"], layer)
        note = Text(layer=layer.id, begin=0, end=1,
                    information={"text": "This claim needs a source."})
        save_object(connection, project["id"], note)

        loaded = load_layer(connection, project["id"], layer.id)
        print(loaded.objects[0].information["text"])
```

```powershell
.venv/Scripts/python.exe -X utf8 example.py
```

It prints `This claim needs a source.`. The temporary directory cleans up the sample data; use your own persistent database path for real projects. IDs come from the API, and saving and loading instances requires no hand-written SQL. The [complete read/write example](examples/read_write.py) continues with reopening, editing, and reading history.

## What you can reuse

| Need | Existing capability |
|---|---|
| Organize information | Objects belong to layers, layers form a tree, and `bind` relationships connect objects and layers, including across projects |
| Find the relevant part | Query by layer, subtree, position, or range; read relationships and project overviews |
| Save a feature's results | A shared write session handles IDs, transactions, and change records |
| Correct an earlier edit | Editing, history, undo, and validation tools; multiple operations can share a transaction |
| Store a tool's own data | Declare tool-owned tables that share reading, writing, change records, and restoration |
| Add a content type | Pair a Python class with a TOML declaration and extend existing types |

An axis can mean seconds, paragraphs, or page numbers; the project defines its meaning, and units are not converted automatically. Images, audio, and video are referenced by path or URL. The core and support layer use only Python's standard library. Concrete operations live in replaceable tool packages.

## Compose the parts, focus on your feature

LayerWeave aims to **reduce the attention spent on coordination**. When working with content, read the relevant part. When developing a feature, reuse the groundwork and focus on its own logic.

Suppose characters are already linked to shots, and you need a list of every shot featuring each character. A tool can query those relationships, reuse the existing storage and change records to save results, and use the undo tool to recover from a change. It can also declare its own tables for data that needs a different structure.

**You and your agents are welcome to build on and extend this kernel.** Layers and objects compose through their structure and `bind` relationships; tools and skill materials are chosen for the task. Built-in tools provide useful operations and working development examples. The full version's view is itself a tool package, and its separate plugins demonstrate how to extend an application further.

Comments are one example: the full version extends the text object with `Note`, uses relationships for replies, and stores read states and layout in the view's own tables. It builds on the existing structure and storage.

| What you want to build | Start here |
|---|---|
| A new layer or object type | [Models and configuration](src/layerweave/models/README.md), [Title example](examples/title.py) |
| A tool with its own data | [Managed tables](docs/build-with-layerweave/03-managed-tables.md), [runnable example](examples/tool_tables.py) |
| Several operations in one transaction | [Composing tools](docs/build-with-layerweave/04-composing-tools.md) |
| An interface or cache that follows project changes | [Incremental reading](docs/build-with-layerweave/05-incremental-reading.md) |
| External skill materials for AI | [Skills and tools](src/layerweave/tool/README.md) |

The [extension guide](docs/build-with-layerweave/README.md) covers more approaches; the [public API](src/layerweave/support/API.md) documents parameters, and the [architecture notes](docs/architecture.md) explain responsibilities. These detailed guides are currently in Chinese.

## Find tools and examples

Use the existing help to discover commands and examples, or inspect layer and object fields, purposes, and type relationships:

```powershell
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.command_help
.venv/Scripts/python.exe -X utf8 -m layerweave.tool.builtin.shared.help.config_help
```

- [Article reading](examples/showcases/article-reading/README.md): query text, interpretation, and evidence through Python/CLI.
- [Twelve examples](examples/showcases/README.md): creation, reading, research, collaboration, and code navigation. Use the complete branch for examples needing the view or comments.
- [Using existing tools](src/layerweave/tool/builtin/usage/README.md): reading, writing, querying, editing, history, undo, JSON exchange, and templates.
- [Source development](docs/developer-conventions.md) · [Testing](tests/README.md) · [Documentation index](docs/README.md).

Skills are instructions and scripts for an AI to read as needed; they do not run on their own. This branch provides direct Python/CLI access without the web view or MCP server packaging. Example content, CLI/help descriptions, and detailed guides are currently in Chinese; machine-readable names are unchanged.

## AI-assisted development

The maintainer leads the project's design and maintenance. Astra (Codex) assisted with development, testing, and documentation on this branch.

## License

LayerWeave's source is licensed under [MIT](LICENSE). Separate skills, external libraries, and services follow their own terms. View builds and third-party web component notices are maintained on visualization.
