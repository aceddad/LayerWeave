# LayerWeave development

LayerWeave is a nonvisual core for layers, objects, configuration, storage and diagnostics.

- Start with `README.md`, then `src/runtime/API.md` and the relevant TOML configuration. Runnable round-trip example: `src/examples/read_write.py`.
- Internal tools import `runtime.api`. Reuse its read/load/save functions and existing `dispatch`; do not duplicate SQL, ID allocation, transaction logs or configuration merging in each tool.
- Core storage adaptation belongs in `src/runtime/storage/`. Tool implementations belong in `src/tools/<content-type>/` or `src/tools/common/`; create those directories only when implementing an actual tool. `tools/README.md` lists tools and the development guide. The first batch includes project overview, object search, relation queries and text collection; `src/examples/first_batch.py` demonstrates all four.
- Preserve simple model classes, explicit project context, post-commit diagnostics, and lazy imports. `config_ref` and `project_id` are storage metadata, not new model fields. Document new persistence semantics before extending them.
- For read-modify-write tools, use `dispatch(connection, request_factory)` so calculation runs inside the write transaction. Do not calculate a layer tail outside the transaction and save later. The second-batch tools are `src/tools/common/positions.py` and `src/tools/common/objects.py`; their combined example is `src/examples/second_batch.py`.
- The nonvisual `main` branch must remain usable without GUI dependencies. Start visualization on its own branch when requested; keep common improvements in the core.
- From `src/`, run `python -X utf8 -B -m unittest discover -s ../tests -v` for changes to persistence or shared execution. Tests and examples use their own temporary/in-memory databases; do not populate the user's output database.
