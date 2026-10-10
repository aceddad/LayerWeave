"""批注：视图工具自带的批注层（notes/）的读写入口。给人和 AI 留意见、说明、待办，每条用关联指向它说的东西。
批注层是项目里的一个根层（类型 note，轴的单位是"条"，第 n 条占 [n, n+1)），第一次写批注时自动创建。
写入走 support 的写会话：进改动日志，可以用撤销工具撤回。视图网页写批注也走这里，这是视图唯一会写入的地方。

python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID                       列出批注
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID add "正文" [--to object:16] [--to layer:1 --span 3 5] [--author Claude]
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID done 40               标记已处理（reopen 40 重新打开）
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID edit 40 "新正文"
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID remove 40             删除这条批注和它发出的关联
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import open_database, read_record, run_operation

from .data import open_readonly
from .notes import AXIS, LAYER_REF, OBJECT_REF

STATUS = {"open": "待处理", "done": "已处理"}


def is_note_layer(layer):
    return layer.get("config_ref") == LAYER_REF


def parse_target(text, project_id):
    """object:16、layer:5，或带项目的 object:2:16。"""
    parts = str(text).split(":")
    if len(parts) not in (2, 3) or parts[0] not in ("object", "layer") or not all(p.isdigit() for p in parts[1:]):
        raise ValueError(f"指向写成 object:编号、layer:编号，或 object:项目:编号；收到 {text!r}")
    return parts[0], int(parts[1]) if len(parts) == 3 else project_id, int(parts[-1])


def _label(connection, project_id, kind, target_project, target_id):
    if target_project != project_id:
        return f"项目 {target_project} 的{'层' if kind == 'layer' else '对象'} #{target_id}", True
    row = read_record(connection, kind, project_id=target_project, id=target_id)
    if row is None:
        return f"{'层' if kind == 'layer' else '对象'} #{target_id}（已删除）", False
    if kind == "layer":
        return f"层 #{target_id} {row['name']}", True
    layer = read_record(connection, "layer", project_id=target_project, id=row["layer"])
    info = row["information"] if isinstance(row["information"], dict) else {}
    name = row["name"] or (info.get("text") if isinstance(info.get("text"), str) else "") or Path(str(info.get("source", ""))).name
    return f"#{target_id} {name}（{layer['name'] if layer else '层 ' + str(row['layer'])}）", True


def list_notes(connection, project_id, status=None):
    """按顺序列出批注：正文、状态、作者、空白时间段，以及它指向的东西（含是否还在）。"""
    layers = [l for l in read_record(connection, "layer", project_id=project_id) if is_note_layer(l)]
    binds = read_record(connection, "bind", filters={"source_project_id": project_id, "source_kind": "object"})
    notes = []
    for layer in layers:
        for row in read_record(connection, "object", project_id=project_id, filters={"layer": layer["id"]}):
            info = row["information"] if isinstance(row["information"], dict) else {}
            state = info.get("status") if info.get("status") in STATUS else "open"
            if status and state != status:
                continue
            targets = []
            for bind in (b for b in binds if b["source_id"] == row["id"]):
                label, exists = _label(connection, project_id, bind["target_kind"], bind["target_project_id"], bind["target_id"])
                targets.append({"kind": bind["target_kind"], "project": bind["target_project_id"], "id": bind["target_id"],
                                "label": label, "exists": exists, "tips": bind["tips"]})
            notes.append({"id": row["id"], "layer": layer["id"], "index": row["begin"], "text": info.get("text", ""),
                          "status": state, "author": info.get("author", ""), "span": info.get("span"), "targets": targets})
    return notes


def _note_layer(write, project_id):
    found = [l for l in write.read("layer", project_id=project_id) if is_note_layer(l)]
    if found:
        return found[0]
    return write.create("layer", {"type": "note", "config_ref": LAYER_REF, "name": "批注", "axis": AXIS,
                                  "tips": "视图工具的批注容器"}, project_id=project_id)


def _run(database, work):
    with closing(open_database(database)) as connection:
        result = run_operation(connection, work)
    if not result["ok"]:
        error = result.get("error") or {}
        raise ValueError(error.get("message") or str(error))
    return {**(result["data"] or {}), "operation_id": result["operation_id"]}


def add_note(database, project_id, text, *, targets=(), span=None, author=None):
    """写一条批注，接在最后。targets 是 (kind, project, id) 列表；span 只和指向层的关联一起用。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("批注正文不能为空")
    if span is not None:
        begin, end = span
        if not any(kind == "layer" for kind, _, _ in targets):
            raise ValueError("span 表示某个层时间轴上的一段，要和指向那个层的关联（--to layer:编号）一起用")
        span = {"begin": float(begin), "end": float(end)} if end >= begin else {"begin": float(end), "end": float(begin)}

    def work(write):
        for kind, target_project, target_id in targets:
            if target_project == project_id and write.read(kind, project_id=project_id, id=target_id) is None:
                raise ValueError(f"项目 {project_id} 里没有{'层' if kind == 'layer' else '对象'} #{target_id}")
        layer = _note_layer(write, project_id)
        existing = write.read("object", project_id=project_id, filters={"layer": layer["id"]})
        index = int(max((row["end"] for row in existing), default=0))
        information = {"text": text, "status": "open"}
        if author:
            information["author"] = author
        if span:
            information["span"] = span
        note = write.create("object", {"config_ref": OBJECT_REF, "name": "", "layer": layer["id"], "begin": index,
                                       "end": index + 1, "information": information, "tips": ""}, project_id=project_id)
        for kind, target_project, target_id in targets:
            write.create("bind", {"source_kind": "object", "source_project_id": project_id, "source_id": note["id"],
                                  "target_kind": kind, "target_project_id": target_project, "target_id": target_id, "tips": ""})
        return {"note": note["id"], "layer": layer["id"], "index": index}
    return _run(database, work)


def _own_note(write, project_id, note_id):
    row = write.read("object", project_id=project_id, id=note_id)
    layer = row and write.read("layer", project_id=project_id, id=row["layer"])
    if not row or not layer or not is_note_layer(layer):
        raise ValueError(f"#{note_id} 不是这个项目批注层里的批注")
    return row


def update_note(database, project_id, note_id, *, text=None, status=None):
    """改正文或状态（open / done）；information 里的其他内容保留。"""
    if status is not None and status not in STATUS:
        raise ValueError("status 只能是 open 或 done")
    if text is not None and not text.strip():
        raise ValueError("批注正文不能为空")

    def work(write):
        row = _own_note(write, project_id, note_id)
        information = dict(row["information"]) if isinstance(row["information"], dict) else {}
        if text is not None:
            information["text"] = text
        if status is not None:
            information["status"] = status
        write.update("object", note_id, {"information": information}, project_id=project_id)
        return {"note": note_id, "status": information.get("status", "open")}
    return _run(database, work)


def remove_note(database, project_id, note_id):
    """删除批注和它发出的关联（指向它的回复保留，会显示为目标已删除）。"""
    def work(write):
        _own_note(write, project_id, note_id)
        for bind in write.read("bind", filters={"source_project_id": project_id, "source_kind": "object", "source_id": note_id}):
            write.delete("bind", bind["id"])
        write.delete("object", note_id, project_id=project_id)
        return {"note": note_id, "removed": True}
    return _run(database, work)


def describe(notes):
    if not notes:
        return "还没有批注。"
    lines = []
    for n in notes:
        head = f"#{n['id']} 第 {n['index']:g} 条 [{STATUS[n['status']]}]" + (f" {n['author']}：" if n["author"] else " ")
        where = "；".join(t["label"] + (f" 的 {n['span']['begin']:g}–{n['span']['end']:g}" if n["span"] and t["kind"] == "layer" else "")
                         for t in n["targets"]) or "整个项目"
        lines.append(f"{head}{n['text']}\n    → {where}")
    return "\n".join(lines)


def note(database, project_id, action="list", *, text=None, to=None, span=None, author=None, note_id=None, status=None):
    """批注的统一入口。action：list（可按 status 过滤）、add、done、reopen、edit、remove。"""
    if action == "list":
        with closing(open_readonly(database)) as connection:
            notes = list_notes(connection, project_id, status)
        return {"notes": notes, "text": describe(notes)}
    if action == "add":
        targets = [parse_target(item, project_id) for item in (to or [])]
        return add_note(database, project_id, text, targets=targets, span=span, author=author)
    if note_id is None:
        raise ValueError(f"{action} 需要批注编号")
    if action in ("done", "reopen"):
        return update_note(database, project_id, note_id, status="done" if action == "done" else "open")
    if action == "edit":
        return update_note(database, project_id, note_id, text=text)
    if action == "remove":
        return remove_note(database, project_id, note_id)
    raise ValueError(f"不认识的动作：{action}")


COMMANDS = [{
    "name": "view_note",
    "summary": "读写视图工具的批注：给人或 AI 留意见、说明、待办，每条用关联指向它说的对象、层或一段时间",
    "entrypoint": "layerweave.tool.builtin.view.note:note",
    "cli": "python -m layerweave.tool.builtin.view.note",
    "read_only": False,
    "context": ["database", "project_id"],
    "parameters": {
        "action": {"type": "string", "description": "list、add、done、reopen、edit 或 remove", "default": "list"},
        "text": {"type": "string", "description": "add、edit 时的批注正文"},
        "to": {"type": "array", "description": "add 时指向的东西：object:编号、layer:编号，或跨项目的 object:项目:编号；可以多个"},
        "span": {"type": "array", "description": "add 时指向层的一段空白时间 [起点, 终点]，用那个层的单位；要和 layer:编号 一起用"},
        "author": {"type": "string", "description": "谁写的，例如 用户、Claude"},
        "note_id": {"type": "integer", "description": "done、reopen、edit、remove 时的批注编号"},
        "status": {"type": "string", "description": "list 时只看 open（待处理）或 done（已处理）"},
    },
    "returns": "list：notes（顺序、正文、状态、作者、span、指向及其是否还在）和 text；写入：批注编号和 operation_id。",
    "examples": [
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 add \"球应该落在桌子下面\" --to object:16 --author 用户"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 add \"这两秒太空\" --to layer:1 --span 6 8"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 done 40"},
    ],
    "notes": ["批注层第一次写入时自动创建：项目里的一个根层，类型 note，轴的单位是“条”，默认在视图里收起。",
              "写入进改动日志，可以用撤销工具撤回；回复一条批注就是 --to object:那条批注的编号。",
              "批注层、批注对象的配置随视图工具包分发（notes/layers/note.toml、notes/objects/note.toml）。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图工具的批注", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="list", choices=("list", "add", "done", "reopen", "edit", "remove"))
    p.add_argument("args", nargs="*", help="add：正文；done/reopen/remove：编号；edit：编号 正文")
    p.add_argument("--to", action="append", help="指向：object:编号、layer:编号、object:项目:编号；可以写多次")
    p.add_argument("--span", type=float, nargs=2, metavar=("起点", "终点"))
    p.add_argument("--author"); p.add_argument("--status", choices=tuple(STATUS)); p.add_argument("--json", action="store_true")
    a = p.parse_args()
    try:
        text = note_id = None
        if a.action == "add":
            text = " ".join(a.args)
        elif a.action in ("done", "reopen", "remove", "edit"):
            if not a.args or not a.args[0].isdigit():
                raise ValueError(f"{a.action} 后面要跟批注编号")
            note_id = int(a.args[0])
            text = " ".join(a.args[1:]) if a.action == "edit" else None
        result = note(a.database, a.project_id, a.action, text=text, to=a.to, span=a.span, author=a.author,
                      note_id=note_id, status=a.status)
    except (ValueError, OSError) as error:
        print(f"批注失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json or "text" not in result else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
