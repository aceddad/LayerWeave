"""视图插件：视图管一份本机清单，清单里有的、开着的才载入。不扫描任何目录。

清单在本机用户目录 ~/.layerweave/view/plugins.json，和排版、"正在看哪儿"放在一起，不在软件的安装目录里，更新不会冲掉：

    {"plugins": [
      {"name": "timeline", "path": "D:/tools/abcd/web/timeline.js", "on": true},
      {"name": "my-page", "path": "my-page/plugin.js", "on": false},   # 相对路径：相对默认文件夹 ~/.layerweave/view/plugins/
      {"name": "cuts", "on": false}                                   # 内置的只记开没开
    ]}

内置插件写在下面的 BUILTIN 里，跟着软件更新。不管多大的工具包，在视图这里都只是一行：名字和一个编译好的 js。
插件是 ES 模块，默认导出 (host) => ViewPlugin（接口见 frontend/view/src/plugin/host.ts，做法见 developer/TOOL_TYPES.md）；
它所在的文件夹里的网页文件（拆出去的代码、图片、样式）也能访问。这里只读写清单、检查文件，不运行插件。

python -m layerweave.tool.builtin.view.plugins [list | add 路径 [--name 名字] | remove 名字 | on 名字 | off 名字]
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys

from layerweave.support.paths import PACKAGE_ROOT

HERE = Path(__file__).resolve().parent
NAME = re.compile(r"[a-z][a-z0-9_-]{0,39}")
RESERVED = {"canvas", "assets"}        # 视图自己的页面
# 视图自带的插件：编译好的 js 在视图包里（frontend/view/plugins 构建出来），清单里只记它开没开
BUILTIN = {
    "cuts": {"path": HERE / "plugins" / "cuts" / "plugin.js", "about": "接缝：同一条轨道里前后相接的画面并排；键盘 [ ] 在接缝之间跳"},
}
# 插件文件夹里能给网页的文件
ASSETS = {".js", ".mjs", ".css", ".json", ".map", ".wasm", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".woff", ".woff2"}


def home(root=None):
    return Path(root or Path.home() / ".layerweave" / "view")


def list_path(root=None):
    return home(root) / "plugins.json"


def list_serial(root=None):
    """清单文件的修改时间，网页靠它发现清单被命令改过（和排版的 layout_serial 一样）。"""
    path = list_path(root)
    return path.stat().st_mtime_ns if path.is_file() else 0


def _read(root):
    """清单里的行；文件不在就是空的。坏了抛 ValueError（写的时候不覆盖坏文件，读的时候报成问题）。"""
    path = list_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"插件清单读不了（{path}）：{error}") from error
    rows = data.get("plugins") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not all(isinstance(r, dict) and isinstance(r.get("name"), str) for r in rows):
        raise ValueError(f"插件清单的格式不对（{path}）：要写成 {{\"plugins\": [{{\"name\": …, \"path\": …, \"on\": true}}]}}")
    return rows


def _write(rows, root):
    path = list_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps({"plugins": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _resolve(path, root):
    path = Path(path).expanduser()
    return (path if path.is_absolute() else home(root) / "plugins" / path).resolve()


def _problem(path):
    if not path.is_file():
        return f"找不到文件：{path}"
    if path.suffix not in (".js", ".mjs"):
        return f"不是 js 文件：{path}"
    if path.is_relative_to(PACKAGE_ROOT.resolve()):
        return "在 LayerWeave 的安装目录里，软件更新时会被换掉；请放到别处再加"
    return None


def list_plugins(root=None):
    """全部插件：内置的在前，然后按清单的顺序。每行 name、source（builtin / link）、path、on、problem（有问题时不载入）、about。"""
    try:
        rows, broken = _read(root), None
    except ValueError as error:
        rows, broken = [], str(error)
    off = {r["name"] for r in rows if r.get("on") is False}
    items = [{"name": name, "source": "builtin", "path": str(spec["path"]), "on": name not in off,
              "problem": None if spec["path"].is_file() else "内置插件的文件不在：视图的网页还没构建（npm run build）", "about": spec["about"]}
             for name, spec in BUILTIN.items()]
    seen = set(BUILTIN)
    for row in rows:
        name = row["name"]
        if name in BUILTIN and "path" not in row:
            continue   # 内置插件的开关
        path = _resolve(str(row.get("path", "")), root)
        if not NAME.fullmatch(name) or name in RESERVED:
            problem = f"名字 {name!r} 不合规矩：小写字母开头，字母、数字、- 和 _，不能叫 canvas、assets"
        elif name in seen:
            problem = f"和{'内置的' if name in BUILTIN else '前面的'} {name} 重名"
        else:
            problem = _problem(path)
        seen.add(name)
        items.append({"name": name, "source": "link", "path": str(path), "on": row.get("on", True) is not False,
                      "problem": problem, "about": ""})
    return {"plugins": items, "file": str(list_path(root)), "folder": str(home(root) / "plugins"), "problem": broken}


def loadable(root=None):
    """开着、没问题的插件，页面按这个顺序载入。"""
    return [p for p in list_plugins(root)["plugins"] if p["on"] and not p["problem"]]


def plugin_file(name, relative, root=None):
    """插件文件夹里的一个网页文件（入口和它旁边的东西）；不在文件夹里、不是网页文件、插件没开都返回 None。"""
    found = next((p for p in loadable(root) if p["name"] == name), None)
    if not found:
        return None
    folder = Path(found["path"]).parent
    path = (folder / relative).resolve()
    if not path.is_relative_to(folder) or path.suffix.lower() not in ASSETS or not path.is_file():
        return None
    return path


def _name_from(path):
    stem = path.parent.name if path.stem in ("plugin", "index", "main") else path.stem
    return stem.lower()


def add_plugin(target, *, name=None, root=None):
    """加一个链接。target 可以是 js 文件、放着 plugin.js 的文件夹，或者只写名字（默认文件夹下面的 <名字>/plugin.js）。
    名字省略时用文件夹名或文件名。检查不过就不写清单。"""
    target = str(target).strip()
    if not target:
        raise ValueError("要给插件的路径")
    bare = not re.search(r"[\\/:]", target) and not target.endswith((".js", ".mjs"))
    stored = f"{target}/plugin.js" if bare else None
    path = _resolve(stored, root) if bare else Path(target).expanduser().resolve()
    if path.is_dir():
        path = path / "plugin.js"
    name = (name or _name_from(path)).strip()
    if not NAME.fullmatch(name) or name in RESERVED:
        raise ValueError(f"名字 {name!r} 不合规矩：小写字母开头，字母、数字、- 和 _，最多 40 个字，不能叫 canvas、assets；用 --name 起一个")
    if problem := _problem(path):
        raise ValueError(problem + ("（只写名字时，找的是默认文件夹 " + str(home(root) / "plugins") + " 下面的 <名字>/plugin.js）" if bare else ""))
    rows = _read(root)
    if name in BUILTIN:
        raise ValueError(f"{name} 是内置插件的名字，用 --name 换一个")
    for row in rows:
        if row["name"] == name:
            raise ValueError(f"已经有叫 {name} 的插件了（{row.get('path')}）；用 --name 换一个，或者先 remove {name}")
        if "path" in row and _resolve(str(row["path"]), root) == path:
            raise ValueError(f"这个文件已经加过了，名字是 {row['name']}")
    plugins_folder = (home(root) / "plugins").resolve()
    stored = path.relative_to(plugins_folder).as_posix() if path.is_relative_to(plugins_folder) else path.as_posix()
    rows.append({"name": name, "path": stored, "on": True})
    _write(rows, root)
    return {"added": name, "path": str(path), **list_plugins(root)}


def remove_plugin(name, *, root=None):
    """去掉一个链接：只删清单里的这一行，不删文件。内置的不能去掉，只能关。"""
    if name in BUILTIN:
        raise ValueError(f"{name} 是内置插件，去不掉；不想用就关掉：view_plugin off {name}")
    rows = _read(root)
    if not any(r["name"] == name for r in rows):
        raise ValueError(f"清单里没有 {name}")
    _write([r for r in rows if r["name"] != name], root)
    return {"removed": name, **list_plugins(root)}


def switch_plugin(name, on, *, root=None):
    """开、关。内置的关掉时记一行 {"name", "on": false}，开回来就删掉这一行。"""
    rows = _read(root)
    if name in BUILTIN:
        rows = [r for r in rows if not (r["name"] == name and "path" not in r)]
        if not on:
            rows.append({"name": name, "on": False})
    elif any(r["name"] == name for r in rows):
        rows = [{**r, "on": on} if r["name"] == name else r for r in rows]
    else:
        raise ValueError(f"没有叫 {name} 的插件")
    _write(rows, root)
    return {"switched": name, "on": on, **list_plugins(root)}


def describe(result):
    lines = []
    for p in result["plugins"]:
        state = "有问题" if p["problem"] else ("开" if p["on"] else "关")
        where = "内置" if p["source"] == "builtin" else p["path"]
        lines.append(f"{p['name']:<14}{state:<4}{where}" + (f"\n{'':<18}{p['problem']}" if p["problem"] else "")
                     + (f"\n{'':<18}{p['about']}" if p["about"] else ""))
    if result.get("problem"):
        lines.append("清单有问题：" + result["problem"])
    lines.append(f"清单：{result['file']}；只写名字的插件放在 {Path(result['folder']) / '<名字>' / 'plugin.js'}")
    lines.append("改了以后视图页面自己会跟上，不用重启视图服务。")
    return "\n".join(lines)


def plugin(action="list", target=None, *, name=None, root=None):
    """list：全部插件；add：加一个链接（target 是路径或名字）；remove / on / off：按名字（target）。"""
    if action == "list":
        result = list_plugins(root)
    elif action == "add":
        result = add_plugin(target or "", name=name, root=root)
    elif action in ("remove", "on", "off"):
        if not target:
            raise ValueError(f"{action} 要给插件的名字")
        result = remove_plugin(target, root=root) if action == "remove" else switch_plugin(target, action == "on", root=root)
    else:
        raise ValueError(f"不认识的动作：{action}（list、add、remove、on、off）")
    return {**result, "text": describe(result)}


COMMANDS = [{
    "name": "view_plugin",
    "summary": "视图插件的清单：列出、加链接、去掉、开、关。清单在本机用户目录，软件更新不会冲掉；视图页面顶栏的「插件」改的是同一份",
    "entrypoint": "layerweave.tool.builtin.view.plugins:plugin",
    "cli": "python -m layerweave.tool.builtin.view.plugins",
    "read_only": False,
    "context": [],
    "parameters": {
        "action": {"type": "string", "default": "list", "choices": ["list", "add", "remove", "on", "off"],
                   "description": "list 列出全部；add 加一个链接；remove 去掉链接（不删文件）；on、off 开关"},
        "target": {"type": "string", "description": "add 时是 js 文件、放着 plugin.js 的文件夹，或者只写名字（默认文件夹下面的 <名字>/plugin.js）；其他动作是插件的名字"},
        "name": {"type": "string", "description": "add 时给插件起的名字（小写字母开头）；省略时用文件夹名或文件名。截图 --view、链接里的 view= 用这个名字"},
    },
    "returns": "plugins（name、source：builtin 内置 / link 链接、path、on、problem、about）、file（清单在哪）、folder（默认文件夹）、text。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.plugins"},
                 {"cli": "python -m layerweave.tool.builtin.view.plugins add D:/tools/abcd/web/timeline.js"},
                 {"cli": "python -m layerweave.tool.builtin.view.plugins off cuts"}],
    "notes": ["插件是在视图页面里运行的代码：能读项目，能写批注和折叠。只加信得过的。",
              "放在 LayerWeave 安装目录里的文件加不进来：软件更新时会被换掉。",
              "去掉只删清单里的一行，不删文件；内置插件不能去掉，只能关。",
              "写插件的做法见 developer/TOOL_TYPES.md 的「视图插件」一节。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图插件的清单", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("action", nargs="?", default="list", choices=("list", "add", "remove", "on", "off"))
    p.add_argument("target", nargs="?", help="add：路径或名字；其他：插件的名字")
    p.add_argument("--name", help="add 时给插件起的名字")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    a = p.parse_args()
    try:
        result = plugin(a.action, a.target, name=a.name)
    except (ValueError, OSError) as error:
        print(f"没有做成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if a.json else result["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
