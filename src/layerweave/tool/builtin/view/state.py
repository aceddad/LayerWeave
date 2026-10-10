"""用户正在看哪儿：视图把当前项目、时间范围、播放头和选中的对象记在本机用户目录，AI 读它就知道"这里"指哪里。
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

FIELDS = {"project": int, "view": str, "range": list, "playhead": (int, float), "selected": dict, "layers": list}


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
    view = {"timeline": "时间轴", "assets": "素材"}.get(state.get("view"), state.get("view", "?"))
    lines = [f"项目 {state.get('project')} · {view}视图 · {state['age_seconds']} 秒前更新"]
    if state.get("range"):
        lines.append(f"可见范围：{state['range'][0]:g} – {state['range'][1]:g}")
    if state.get("playhead") is not None:
        lines.append(f"播放头：{state['playhead']:g}")
    if state.get("selected"):
        s = state["selected"]
        lines.append(f"选中：对象 {s.get('id')}（层 {s.get('layer')}）{s.get('name') or ''}")
    if state.get("layers"):
        lines.append("可见的层：" + ", ".join(str(i) for i in state["layers"]))
    return "\n".join(lines)


COMMANDS = [{
    "name": "view_state",
    "summary": "读取用户在视图里正在看的位置：项目、视图、可见范围、播放头、选中的对象",
    "entrypoint": "layerweave.tool.builtin.view.state:read_state",
    "cli": "python -m layerweave.tool.builtin.view.state",
    "read_only": True,
    "context": ["database"],
    "parameters": {},
    "returns": "状态字典（含 age_seconds，表示多少秒前更新）；视图从未打开过时为 None。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.state DATABASE --json"}],
    "notes": ["用户说「这里」「这段」时先读它；age_seconds 很大说明用户可能已经离开视图。"],
}]


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
