"""用户正在看哪儿：视图把当前项目、当前画板、可见的时间范围、播放头和选中的对象记在本机用户目录，AI 读它就知道"这里"指哪里。
不写业务数据库。每个数据库一份状态文件：~/.layerweave/view/<数据库路径的散列>.json

python -m layerweave.tool.builtin.view.state DATABASE [--json]
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile

FIELDS = {"lang": str, "project": int, "view": str, "board": dict, "range": list, "playhead": (int, float), "playhead_at": list,
          "selected": dict, "selection": dict, "boards": list, "layers": list, "folded": list}


def state_path(database, root=None):
    key = hashlib.sha1(str(Path(database).resolve()).lower().encode("utf-8")).hexdigest()[:16]
    return Path(root or Path.home() / ".layerweave" / "view") / f"{key}.json"


def write_state(database, payload, root=None):
    data = {name: payload[name] for name, kind in FIELDS.items() if isinstance(payload.get(name), kind)}
    data["database"] = str(Path(database).resolve())
    data["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = state_path(database, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False)
    os.replace(temp, path)
    return data


def read_state(database, root=None):
    path = state_path(database, root)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = datetime.fromisoformat(data["updated_at"])
    data["age_seconds"] = round((datetime.now(timezone.utc) - updated).total_seconds())
    return data


def describe(state):
    if state is None:
        return "视图还没有记录过状态：用户可能还没打开视图。"
    view = {"canvas": "画布", "timeline": "画布", "assets": "一览"}.get(state.get("view"), state.get("view", "?"))
    lines = [f"项目 {state.get('project')} · {view}视图 · {state['age_seconds']} 秒前更新"]
    board = state.get("board") or {}
    unit = board.get("unit") or ""
    rows = board.get("rows") or [[r] for r in board.get("roots", [])]
    names = board.get("names") or [[""] * len(row) for row in rows]
    if rows:
        if names and not isinstance(names[0], list):   # 旧格式：一列根
            names = [[n] for n in names]
        text = " ＋ ".join(" → ".join(f"{n or '层'}（{r}）" for n, r in zip(row_names, row)) for row_names, row in zip(names, rows))
        lines.append(f"当前画板：{text}，单位 {unit or '没有单位'}（＋ 是上下拼、同时；→ 是左右接、接续）")
    if state.get("range"):
        lines.append(f"当前画板的可见范围：{state['range'][0]:g} – {state['range'][1]:g} {unit}".rstrip())
    if state.get("playhead") is not None:
        lines.append(f"播放头（在当前画板上）：{state['playhead']:g} {unit}".rstrip())
        for at in state.get("playhead_at") or []:
            lines.append(f"  对应 {at.get('name') or '根'}（{at.get('root')}）自己的 {at.get('local'):g} {unit}".rstrip())
    if state.get("selected"):
        s = state["selected"]
        lines.append(f"选中：对象 {s.get('id')}（层 {s.get('layer')}）{s.get('name') or ''}")
    if state.get("selection"):
        s = state["selection"]
        lines.append(f"圈出的一段：{s.get('name') or '根'}（{s.get('root')}）自己的 {s.get('begin'):g} – {s.get('end'):g} {unit}".rstrip()
                     + "（写批注时用 --to layer:根编号 --span 起点 终点）")
    if state.get("boards"):
        lines.append("屏幕上的画板（按根层编号）：" + "；".join("、".join(str(r) for r in roots) for roots in state["boards"]))
    if state.get("layers"):
        lines.append("可见的层：" + ", ".join(str(i) for i in state["layers"]))
    if state.get("folded"):
        lines.append("用户折叠的层（用户现在不关注；内容照常要检查，view_fold 查看两边的折叠）：" + ", ".join(str(i) for i in state["folded"]))
    return "\n".join(lines)


COMMANDS = [{'name': 'view_state',
  'summary': '读取用户在视图里正在看的位置：项目、当前画板、可见范围、播放头、选中的对象',
  'entrypoint': 'layerweave.tool.builtin.view.state:read_state',
  'cli': 'python -m layerweave.tool.builtin.view.state',
  'read_only': True,
  'context': ['database'],
  'returns': '状态字典（含 age_seconds，表示多少秒前更新）；视图从未打开过时为 None。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.view.state DATABASE --json'}],
  'notes': ['用户说「这里」「这段」时先读它；age_seconds 很大说明用户可能已经离开视图。',
            'range 和 playhead 用当前画板（board）的单位；不同画板的单位可能不同。',
            '左右接续的画板上，playhead 是连续时间；playhead_at 给出它落在哪个根、是那个根自己的第几秒（或帧）。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'}},
                   'additionalProperties': False,
                   'required': ['database']},
  'mcp': {'route': 'query', 'group': 'view', 'database': 'path', 'paths': []},
  'cli_only': ['json']}]


def main():
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(description="用户正在视图里看哪儿", formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=help_examples(COMMANDS))
    parser.add_argument("database", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    state = read_state(args.database)
    print(json.dumps(state, ensure_ascii=False, indent=2) if args.json else describe(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
