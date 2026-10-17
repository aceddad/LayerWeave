"""批注：视图工具自带的批注层（notes/）的读写入口。给人和 AI 留意见、说明、待办，每条用关联指向它说的东西。
批注层是项目里的一个根层（类型 note，轴的单位是"条"，第 n 条占 [n, n+1)），第一次写批注时自动创建。
写入走 support 的写会话：进改动日志，可以用撤销工具撤回。视图网页写批注也走这里，这是视图唯一会写入的地方。

python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID                       按楼列出待处理的批注（--status done 看已处理的，all 看全部）
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID --waiting Claude      只列在等 Claude 的楼：没处理、最后一句不是 Claude 说的、Claude 也没标已读
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID read 41 --author Claude  这一楼 Claude 看过了，不再算"等 Claude"（unread 取消）
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID reply 41 "回复正文" [--author Claude]
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID add "正文" [--to object:16] [--to layer:1 --span 3 5] [--author Claude]
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID done 40               标记已处理（reopen 40 重新打开）
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID edit 40 "新正文"
python -m layerweave.tool.builtin.view.note DATABASE PROJECT_ID remove 40             删除这条批注和它发出的关联
"""
from .i18n import ViewError

import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import open_database, read_record, register_tables, run_operation

from .data import open_readonly
from .notes import AXIS, LAYER_REF, OBJECT_REF
from .notes.reads import READ_KIND, READ_TABLE, parse_reads, read_reads

STATUS = {"open": "待处理", "done": "已处理"}
LIST_STATUS = (*STATUS, "all")


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
    """按顺序列出批注：正文、状态、作者、空白时间段，以及它指向的东西（含是否还在）。
    reply_to 是它回复的那条批注；thread 是它所在的楼（楼主的编号）。status 过滤按楼主的状态，整楼一起留下或去掉。"""
    layers = [l for l in read_record(connection, "layer", project_id=project_id) if is_note_layer(l)]
    binds = read_record(connection, "bind", filters={"source_project_id": project_id, "source_kind": "object"})
    notes = []
    for layer in layers:
        for row in read_record(connection, "object", project_id=project_id, filters={"layer": layer["id"]}):
            info = row["information"] if isinstance(row["information"], dict) else {}
            state = info.get("status") if info.get("status") in STATUS else "open"
            targets = []
            for bind in (b for b in binds if b["source_id"] == row["id"]):
                label, exists = _label(connection, project_id, bind["target_kind"], bind["target_project_id"], bind["target_id"])
                targets.append({"kind": bind["target_kind"], "project": bind["target_project_id"], "id": bind["target_id"],
                                "label": label, "exists": exists, "tips": bind["tips"]})
            notes.append({"id": row["id"], "layer": layer["id"], "index": row["begin"], "text": info.get("text", ""),
                          "status": state, "author": info.get("author", ""), "span": info.get("span"), "targets": targets})
    notes.sort(key=lambda n: (n["index"], n["id"]))
    ids = {n["id"]: n for n in notes}
    for n in notes:
        n["reply_to"] = next((t["id"] for t in n["targets"] if t["kind"] == "object" and t["project"] == project_id
                              and t["id"] in ids), None)
    for n in notes:                                       # 顺着回复往上找到楼主
        top, seen = n, set()
        while top["reply_to"] is not None and top["id"] not in seen:
            seen.add(top["id"])
            top = ids[top["reply_to"]]
        n["thread"] = top["id"]
    if status:
        notes = [n for n in notes if ids[n["thread"]]["status"] == status]
    return notes


def threads(notes):
    """按楼分组：[(楼主, [回复…])]，楼的顺序按楼主的位置，回复按写的先后。"""
    groups = {}
    for n in notes:
        groups.setdefault(n["thread"], []).append(n)
    return [(next(n for n in group if n["id"] == key), [n for n in group if n["id"] != key])
            for key, group in groups.items() if any(n["id"] == key for n in group)]


def waiting_for(notes, name, reads=None):
    """在等 name 的楼：还没处理、最后一句不是 name 说的，name 也没有在最后一条之后标过已读。
    reads 是 read_reads 的结果；楼里后来又有人写了新的一条，就又算没读。"""
    reads = reads or {}
    return [n for top, replies in threads(notes)
            if top["status"] == "open" and [top, *replies][-1]["author"] != name
            and reads.get(top["id"], {}).get(name, 0) < max(m["id"] for m in [top, *replies])
            for n in [top, *replies]]


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


def _span(span, targets):
    """span 只和指向层的关联一起用；起止写反了就换过来。"""
    if span is None:
        return None
    begin, end = span
    if not any(kind == "layer" for kind, _, _ in targets):
        raise ViewError("noteError.span")
    return {"begin": float(begin), "end": float(end)} if end >= begin else {"begin": float(end), "end": float(begin)}


def _check_targets(write, project_id, targets):
    for kind, target_project, target_id in targets:
        if target_project == project_id and write.read(kind, project_id=project_id, id=target_id) is None:
            raise ViewError("noteError.targetLayerMissing" if kind == "layer" else "noteError.targetObjectMissing", {"project": project_id, "id": target_id})


def add_note(database, project_id, text, *, targets=(), span=None, author=None):
    """写一条批注，接在最后。targets 是 (kind, project, id) 列表；span 只和指向层的关联一起用。"""
    if not isinstance(text, str) or not text.strip():
        raise ViewError("noteError.empty")
    span = _span(span, targets)

    def work(write):
        _check_targets(write, project_id, targets)
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
        raise ViewError("noteError.notNote", {"value1": note_id})
    return row


def update_note(database, project_id, note_id, *, text=None, status=None):
    """改正文或状态（open / done）；information 里的其他内容保留。"""
    if status is not None and status not in STATUS:
        raise ViewError("noteError.status")
    if text is not None and not text.strip():
        raise ViewError("noteError.empty")

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


def retarget_note(database, project_id, note_id, targets, span=None):
    """改楼主指着的东西：换掉它发出的关联，楼号、正文、回复、已读都不动；一次写完，可以撤销。
    targets 为空就是改成写给整个项目。回复不能改：它指着楼主，改了就不是这一楼的了。"""
    targets = list(dict.fromkeys(targets))
    span = _span(span, targets)

    def work(write):
        row = _own_note(write, project_id, note_id)
        _check_targets(write, project_id, targets)
        old = write.read("bind", filters={"source_project_id": project_id, "source_kind": "object", "source_id": note_id})
        for bind in old:
            target = bind["target_kind"] == "object" and bind["target_project_id"] == project_id \
                and write.read("object", project_id=project_id, id=bind["target_id"])
            layer = target and write.read("layer", project_id=project_id, id=target["layer"])
            if layer and is_note_layer(layer):
                raise ViewError("noteError.replyTarget", {"value1": note_id, "value2": bind['target_id']})
        for bind in old:
            write.delete("bind", bind["id"])
        for kind, target_project, target_id in targets:
            write.create("bind", {"source_kind": "object", "source_project_id": project_id, "source_id": note_id,
                                  "target_kind": kind, "target_project_id": target_project, "target_id": target_id, "tips": ""})
        information = dict(row["information"]) if isinstance(row["information"], dict) else {}
        information.pop("span", None)
        if span:
            information["span"] = span
        write.update("object", note_id, {"information": information}, project_id=project_id)
        return {"note": note_id, "targets": [f"{k}:{i}" if p == project_id else f"{k}:{p}:{i}" for k, p, i in targets]}
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


def set_read(database, project_id, note_id, reader, read=True):
    """reader 把 note_id 所在的这一楼标成已读（记下现在最后一条的编号），read=False 取消。写视图自己的表 view_note。"""
    reader = (reader or "").strip()
    if not reader:
        raise ViewError("noteError.author")
    with closing(open_database(database)) as connection:
        notes = list_notes(connection, project_id)
        note = next((n for n in notes if n["id"] == note_id), None)
        if note is None:
            raise ViewError("noteError.notNote", {"value1": note_id})
        thread = note["thread"]
        last = max(n["id"] for n in notes if n["thread"] == thread)
        register_tables(connection, READ_TABLE)   # 相同声明重复登记什么也不做

        def work(write):
            row = write.read(READ_KIND, project_id=project_id, id=thread)
            reads = parse_reads(row["reads"]) if row else {}
            want = {**reads, reader: last} if read else {k: v for k, v in reads.items() if k != reader}
            if want != reads:
                value = json.dumps(want, ensure_ascii=False, sort_keys=True)
                if row is None:
                    write.create(READ_KIND, {"id": thread, "reads": value}, project_id=project_id)
                else:
                    write.update(READ_KIND, thread, {"reads": value}, project_id=project_id)
            return {"thread": thread, "reader": reader, "read": read, "last": last}

        result = run_operation(connection, work)
    if not result["ok"]:
        error = result.get("error") or {}
        raise ValueError(error.get("message") or str(error))
    return {**(result["data"] or {}), "operation_id": result["operation_id"]}


def describe(notes, numbers=None):
    """numbers：{楼主编号: 第几楼}，按全部楼排的号（和网页一致）；只列一部分楼时也用全部的号，免得同一楼两边叫法不一样。"""
    if not notes:
        return "没有批注。"
    lines = []
    for index, (top, replies) in enumerate(threads(notes), 1):
        number = (numbers or {}).get(top["id"], index)
        where = "；".join(t["label"] + (f" 的 {top['span']['begin']:g}–{top['span']['end']:g}" if top["span"] and t["kind"] == "layer" else "")
                         for t in top["targets"]) or "整个项目"
        lines.append(f"第 {number} 楼 #{top['id']} [{STATUS[top['status']]}] {top['author'] or '（未署名）'}：{top['text']}")
        lines.append(f"    → {where}")
        floors = {top["id"]: 1}
        for floor, reply in enumerate(replies, 2):
            floors[reply["id"]] = floor
            to = f"（回复 {floors[reply['reply_to']]} 楼）" if reply["reply_to"] != top["id"] and reply["reply_to"] in floors else ""
            lines.append(f"    {floor} 楼 #{reply['id']} {reply['author'] or '（未署名）'}{to}：{reply['text']}")
    return "\n".join(lines)


def note(database, project_id, action="list", *, text=None, to=None, span=None, author=None, note_id=None, status="open",
         waiting=None):
    """批注的统一入口。action：list（默认只列待处理的楼；status="done" 已处理、"all" 全部；可按 waiting 过滤）、
    add、reply、done、reopen、edit、remove、read / unread（author 这个人标已读、取消已读）。"""
    if action == "list":
        if status not in (None, *LIST_STATUS):
            raise ValueError(f"status 只能是 {'、'.join(LIST_STATUS)}")
        with closing(open_readonly(database)) as connection:
            every = list_notes(connection, project_id)
            reads = read_reads(connection, project_id)
        numbers = {top["id"]: number for number, (top, _) in enumerate(threads(every), 1)}   # 第几楼按全部楼数
        tops = {n["id"]: n for n in every}
        notes = every if status in (None, "all") else [n for n in every if tops[n["thread"]]["status"] == status]
        if waiting:
            notes = waiting_for(notes, waiting, reads)
        return {"notes": notes, "text": describe(notes, numbers)}
    if action == "reply":
        if note_id is None:
            raise ValueError("reply 需要被回复的批注编号")
        with closing(open_readonly(database)) as connection:
            if note_id not in {n["id"] for n in list_notes(connection, project_id)}:
                raise ViewError("noteError.notNote", {"value1": note_id})
        return add_note(database, project_id, text, targets=[("object", project_id, note_id)], author=author)
    if action == "add":
        targets = [parse_target(item, project_id) for item in (to or [])]
        return add_note(database, project_id, text, targets=targets, span=span, author=author)
    if note_id is None:
        raise ValueError(f"{action} 需要批注编号")
    if action in ("done", "reopen"):
        return update_note(database, project_id, note_id, status="done" if action == "done" else "open")
    if action == "edit":
        if to is not None:                                  # --to：改指向（可以同时改正文）
            result = retarget_note(database, project_id, note_id, [parse_target(item, project_id) for item in to], span=span)
            if text:
                result = {**result, **update_note(database, project_id, note_id, text=text)}
            return result
        return update_note(database, project_id, note_id, text=text)
    if action == "remove":
        return remove_note(database, project_id, note_id)
    if action in ("read", "unread"):
        return set_read(database, project_id, note_id, author, read=action == "read")
    raise ValueError(f"不认识的动作：{action}")


COMMANDS = [{
    "name": "view_note",
    "summary": "读写视图工具的批注：给人或 AI 留意见、说明、待办，每条用关联指向它说的对象、层或一段时间",
    "entrypoint": "layerweave.tool.builtin.view.note:note",
    "cli": "python -m layerweave.tool.builtin.view.note",
    "read_only": False,
    "context": ["database", "project_id"],
    "parameters": {
        "action": {"type": "string", "description": "list、add、reply、done、reopen、edit、remove、read 或 unread", "default": "list"},
        "text": {"type": "string", "description": "add、reply、edit 时的批注正文"},
        "to": {"type": "array", "description": "add 时指向的东西：object:编号、layer:编号，或跨项目的 object:项目:编号；可以多个。edit 带 to 就是改指向（只有楼主能改，回复不能）；给空列表改成写给整个项目"},
        "span": {"type": "array", "description": "add 时指向层的一段空白时间 [起点, 终点]，用那个层的单位；要和 layer:编号 一起用"},
        "author": {"type": "string", "description": "谁写的，例如 用户、Claude；read、unread 时是谁标已读"},
        "note_id": {"type": "integer", "description": "reply（被回复的那条）、done、reopen、edit、remove、read、unread 时的批注编号（read 按它所在的楼）"},
        "status": {"type": "string", "description": "list 时看哪些楼：open（待处理，默认）、done（已处理）或 all（全部）", "default": "open"},
        "waiting": {"type": "string", "description": "list 时只看在等这个人的楼：没处理、最后一句不是他说的，他也没在最后一条之后标已读"},
    },
    "returns": "list：notes（顺序、正文、状态、作者、span、指向及其是否还在、reply_to、thread）和按楼排的 text；写入：批注编号和 operation_id。",
    "examples": [
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 add \"球应该落在桌子下面\" --to object:16 --author 用户"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 add \"这两秒太空\" --to layer:1 --span 6 8"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 --waiting Claude"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 reply 41 \"已经改了\" --author Claude"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 done 40"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 edit 40 --to object:18"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 read 40 --author Claude"},
        {"cli": "python -m layerweave.tool.builtin.view.note DATABASE 1 --status done"},
    ],
    "notes": ["批注层第一次写入时自动创建：项目里的一个根层，类型 note，轴的单位是“条”，默认在视图里收起。",
              "写入进改动日志，可以用撤销工具撤回。回复就是一条关联到另一条批注的批注，按楼显示；楼主的状态代表整楼。",
              "开工前先看 --waiting 自己的名字：用户在网页上回复的问题都在那里。",
              "默认只列待处理的楼；已处理的要 --status done 才看得到（网页上也一样，在“已处理”里）。",
              "已读和已处理是两回事：已读（read）只是“我看过了，别再提醒我”，每个人各记各的，存在视图自己的表 view_note；之后有人再写一条，就又算没读。",
              "批注层、批注对象由视图工具登记：配置在 configs/layers/note.toml、configs/objects/note.toml（requires 本工具包），类在 notes/models.py。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图工具的批注", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int)
    p.add_argument("action", nargs="?", default="list",
                   choices=("list", "add", "reply", "done", "reopen", "edit", "remove", "read", "unread"))
    p.add_argument("args", nargs="*", help="add：正文；done/reopen/remove/read/unread：编号；edit、reply：编号 正文")
    p.add_argument("--to", action="append", help="指向：object:编号、layer:编号、object:项目:编号；可以写多次")
    p.add_argument("--span", type=float, nargs=2, metavar=("起点", "终点"))
    p.add_argument("--author"); p.add_argument("--json", action="store_true")
    p.add_argument("--status", choices=LIST_STATUS, default="open", help="list 时看哪些楼：open（默认）、done、all")
    p.add_argument("--waiting", metavar="名字", help="只列在等这个人回复的楼")
    a = p.parse_args()
    try:
        text = note_id = None
        if a.action == "add":
            text = " ".join(a.args)
        elif a.action in ("done", "reopen", "remove", "edit", "reply", "read", "unread"):
            if not a.args or not a.args[0].isdigit():
                raise ValueError(f"{a.action} 后面要跟批注编号")
            note_id = int(a.args[0])
            text = " ".join(a.args[1:]) if a.action in ("edit", "reply") else None
        result = note(a.database, a.project_id, a.action, text=text, to=a.to, span=a.span, author=a.author,
                      note_id=note_id, status=a.status, waiting=a.waiting)
    except (ValueError, OSError) as error:
        print(f"批注失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json or "text" not in result else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
