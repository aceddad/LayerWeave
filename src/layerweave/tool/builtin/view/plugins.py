"""视图插件管理：静态目录、ZIP 选装和本地开发链接。见 PLUGINS.md。"""
from .i18n import ViewError

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from layerweave.support.paths import PACKAGE_ROOT
from . import plugin_store as store
from .plugin_manifest import PART, compatibility, inside, read_manifest, valid_id

home, list_path = store.home, store.list_path
ASSETS = {".js", ".mjs", ".css", ".json", ".map", ".wasm", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".woff", ".woff2"}


def list_serial(root=None):
    path = list_path(root)
    return path.stat().st_mtime_ns if path.is_file() else 0


def _entry(row):
    if not valid_id(row.get("id")):
        raise ValueError(f"插件 ID 不合规：{row.get('id')!r}，需要 publisher.name")
    if row.get("mode") not in ("link", "managed"):
        raise ValueError("插件 mode 需要 link 或 managed")
    folder = Path(row["root"]).expanduser().resolve()
    path = inside(folder, row["entry"])
    if not path.is_file():
        raise ViewError("pluginError.fileMissing", {"value1": path})
    if path.suffix not in (".js", ".mjs"):
        raise ViewError("pluginError.notJs", {"value1": path})
    if path.is_relative_to(PACKAGE_ROOT.resolve()):
        raise ViewError("pluginError.insideHost")
    return folder, path


def list_plugins(root=None, *, languages=False):
    try:
        data, broken = store.read(root), None
    except ValueError as error:
        data, broken = store.empty(), str(error)
    items, seen = [], set()
    for row in data["plugins"]:
        identity = row.get("id", "?")
        item = {**row, "name": identity, "source": row.get("mode", "link"), "path": "", "on": row.get("on") is not False,
                "label": identity, "about": "", "problem": None, "compatibility": "undeclared"}
        try:
            if identity in seen:
                raise ViewError("pluginError.duplicate", {"value1": identity})
            seen.add(identity)
            folder, path = _entry(row)
            item["path"] = str(path)
            if row["mode"] == "managed" or (folder / "plugin.json").is_file():
                meta = read_manifest(folder)
                if meta["id"] != identity or meta["entry"] != row["entry"]:
                    raise ViewError("pluginError.identityChanged")
                if row["mode"] == "managed" and meta["version"] != row.get("version"):
                    raise ViewError("pluginError.versionMismatch")
                item.update(label=meta["label"], about=meta["description"], version=meta["version"], requires=meta["requires"],
                            slots=meta.get("slots"), compatibility="compatible")
                if languages:
                    from .i18n import read_localizations
                    item["localizations"], item["language_warnings"] = read_localizations(folder, meta)
                if problem := compatibility(meta["requires"]):
                    item["compatibility"] = "incompatible"
                    raise ValueError(problem)
            revision = row.get("origin", {}).get("sha256") if row["mode"] == "managed" else None
            item["revision"] = revision or hashlib.sha256(f"{path}:{path.stat().st_mtime_ns}".encode()).hexdigest()[:24]
        except (KeyError, TypeError, OSError, ValueError) as error:
            item["problem"] = str(error)
            if hasattr(error, "ui"):
                item["problem_ui"] = error.ui
        items.append(item)
    return {"plugins": items, "file": str(list_path(root)), "folder": str(home(root) / "plugins"), "problem": broken,
            "catalog": data.get("catalog") or store.DEFAULT_CATALOG, "recommended": store.RECOMMENDED,
            "migration_pending": data.get("migration_pending", False), "migration_issues": data.get("unresolved_legacy", []),
            "aliases": {**data.get("aliases", {}), **{k: "layerweave." + k for k in store.LEGACY}}}


def loadable(root=None):
    return [p for p in list_plugins(root)["plugins"] if p["on"] and not p["problem"]]


def plugin_file(name, relative, root=None, *, revision=None):
    found = next((p for p in loadable(root) if p["id"] == name), None)
    if not found or (revision is not None and revision != found["revision"]):
        return None
    try:
        path = inside(found["root"], relative)
        return path if path.is_file() and path.suffix.lower() in ASSETS else None
    except ValueError:
        return None


def add_plugin(target, *, name=None, root=None):
    target = str(target or "").strip()
    if not target:
        raise ViewError("pluginError.pathRequired")
    bare = not re.search(r"[\\/:]", target) and not target.endswith((".js", ".mjs")) and not Path(target).is_dir()
    path = (home(root) / "plugins" / target) if bare else Path(target).expanduser().resolve()
    folder = path if path.is_dir() or bare else path.parent
    meta = read_manifest(folder) if (folder / "plugin.json").is_file() else None
    if meta:
        if name:
            raise ViewError("pluginError.nameOverride")
        identity, entry = meta["id"], meta["entry"]
    else:
        entry = "plugin.js" if path.is_dir() or bare else path.name
        stem = folder.name if Path(entry).stem in ("plugin", "index", "main") else Path(entry).stem
        short = (name or stem.lower()).strip()
        if not PART.fullmatch(short):
            raise ViewError("pluginError.name")
        identity = "local." + short
    row = {"id": identity, "kind": "view-plugin", "mode": "link", "root": str(folder.resolve()), "entry": entry,
           "on": True, "version": meta["version"] if meta else None}
    try:
        _, file = _entry(row)
    except ValueError as error:
        if not bare:
            raise
        raise ValueError(str(error) + (f"（只写名字时找默认文件夹 {home(root) / 'plugins'}）" if bare else "")) from error
    with store.locked(root):
        data = store.writable(root)
        for previous in data["plugins"]:
            if previous.get("id") == identity:
                raise ViewError("pluginError.exists", {"value1": identity})
            if previous.get("root") and previous.get("entry") and inside(previous["root"], previous["entry"]) == file:
                raise ViewError("pluginError.fileRegistered", {"value1": previous['id']})
        data["plugins"].append(row)
        store.write(data, root)
    return {"added": identity, "status": "linked", "path": str(file)}


def switch_plugin(name, on, *, root=None):
    with store.locked(root):
        data = store.writable(root)
        row = next((r for r in data["plugins"] if r.get("id") == name), None)
        if row is None:
            raise ViewError("pluginError.notInstalled", {"value1": name})
        row["on"] = bool(on)
        store.write(data, root)
    return {"switched": name, "on": bool(on), "status": "switched"}


def remove_plugin(name, *, files=False, root=None):
    from .plugin_market import remove
    return remove(name, files=files, root=root)


def require_plugin(identity, *, slot=None, root=None):
    identity = store.canonical(identity, root)
    found = next((r for r in list_plugins(root)["plugins"] if r["id"] == identity), None)
    if found is None:
        raise ValueError(f"插件 {identity} 未安装；用 view_plugin market/info 查看，再明确 install 或 add")
    if not found["on"]:
        raise ValueError(f"插件 {identity} 已关闭；用 view_plugin on {identity} 开启")
    if found["problem"]:
        raise ValueError(f"插件 {identity} 不可加载：{found['problem']}")
    if slot and found.get("slots") is not None and slot not in found["slots"]:
        raise ValueError(f"插件 {identity} 没有声明 {slot} 栏位")
    return found


def describe(result):
    lines = []
    for key in ("message", "backup", "recycled"):
        if result.get(key):
            lines.append(f"{key}: {result[key]}")
    if "manifest" in result:
        meta = result["manifest"]
        if meta:
            lines.extend([f"{meta['id']} {meta['version']} · {meta['label']}", meta["description"], f"需要：{meta['requires']}", "参数："])
            for name, spec in meta["params"].items():
                optional = "必填" if spec.get("required") else "选填"
                default = f"；默认 {json.dumps(spec['default'], ensure_ascii=False)}" if "default" in spec else ""
                lines.append(f"  {name}: {spec['type']}（{optional}{default}） {spec['description']}")
        lines.extend(["", result.get("usage", "")])
        return "\n".join(lines)
    if "items" in result:
        for item in result["items"]:
            lines.append(f"{item['id']} {item.get('version', '?')} · {item.get('label', '')} · {'可安装' if item['compatible'] else item.get('problem')} · 已装 {item.get('installed_version') or '无'}")
            lines.append("  " + (item.get("description") or ""))
            for version in item.get("versions", []):
                lines.append(f"  {version.get('version', '?')}：{version.get('problem') or '兼容'}；{version.get('requires', {})}")
        lines.append(f"目录：{result['catalog']}")
    elif "results" in result:
        lines.extend(f"{r['id']} [{r['status']}] {r.get('message', '')}" for r in result["results"])
    else:
        for row in result["plugins"]:
            state = row["problem"] or ("开" if row["on"] else "关")
            lines.append(f"{row['id']} {row.get('version') or '开发链接'} [{state}] {row['label']} · {row['source']}")
        if not result["plugins"]:
            lines.append("未安装插件；画布可直接使用。view_plugin market 查看可选插件。")
        lines.append(f"清单：{result['file']}")
    for issue in result.get("issues", result.get("migration_issues", [])):
        lines.append(f"[{issue.get('severity', 'warn')}] {issue.get('message', issue.get('problem', issue))}")
    if result.get("problem"):
        lines.append("清单问题：" + result["problem"])
    if result.get("migration_pending"):
        lines.append("旧清单仅作只读预览。确认迁移请执行 view_plugin migrate；保留备份，不自动下载。")
    return "\n".join(lines)


def plugin(action="list", target=None, *, name=None, root=None, catalog=None, version=None, file=None, files=False):
    from . import plugin_market as market
    if action in ("remove", "on", "off", "info", "update") and target:
        target = store.canonical(target, root)
    if action == "list":
        result = {}
    elif action == "add":
        result = add_plugin(target, name=name, root=root)
    elif action == "migrate":
        result = store.migrate(root)
    elif action == "market":
        result = market.market(target, catalog=catalog, root=root)
    elif action == "info":
        if not target:
            raise ValueError("info 需要完整插件 ID")
        result = market.info(target, catalog=catalog, version=version, root=root)
    elif action == "install":
        result = market.install(identity=target, version=version, catalog=catalog, file=file, root=root)
    elif action == "update":
        result = market.update(target, root=root)
    elif action in ("remove", "on", "off"):
        if not target:
            raise ValueError(f"{action} 需要完整插件 ID")
        result = remove_plugin(target, files=files, root=root) if action == "remove" else switch_plugin(target, action == "on", root=root)
    else:
        raise ValueError("未知动作；可选 list、market、info、install、update、add、remove、on、off、migrate")
    result = {**list_plugins(root), **result}
    return {**result, "text": describe(result)}


COMMANDS = [{'name': 'view_plugin',
  'summary': '视图插件：查询市场/说明、安装版本 ZIP、更新、开发链接、开关和卸载；零插件也可使用画布',
  'entrypoint': 'layerweave.tool.builtin.view.plugins:plugin',
  'cli': 'python -m layerweave.tool.builtin.view.plugins',
  'read_only': False,
  'context': [],
  'returns': 'text；本机 plugins（完整 id/name、version、source、on、problem）；market 的 items；info 的 '
             'manifest/usage；安装状态与页面加载状态分开。',
  'examples': [{'cli': 'python -m layerweave.tool.builtin.view.plugins market', 'arguments': {'action': 'list'}},
               {'cli': 'python -m layerweave.tool.builtin.view.plugins info layerweave.preview'},
               {'cli': 'python -m layerweave.tool.builtin.view.plugins install layerweave.preview'},
               {'cli': 'python -m layerweave.tool.builtin.view.plugins install --file preview-1.0.0.zip'},
               {'cli': 'python -m layerweave.tool.builtin.view.plugins add D:/tools/my-plugin'}],
  'notes': ['显式安装/更新才下载并登记，不因打开项目自动安装。',
            '插件是页面内执行的代码；哈希验证包内容，不是作者认证。',
            '接口和声明见 view/PLUGINS.md；Python 组件本版只预留种类。'],
  'input_schema': {'type': 'object',
                   'properties': {'action': {'type': 'string',
                                             'default': 'list',
                                             'description': 'list 本机；market 目录；info 参数/说明；install 安装；update '
                                                            '更新；add 开发链接；remove 解除登记；on/off 开关；migrate 显式迁移旧清单',
                                             'enum': ['list',
                                                      'market',
                                                      'info',
                                                      'install',
                                                      'update',
                                                      'add',
                                                      'remove',
                                                      'on',
                                                      'off',
                                                      'migrate']},
                                  'target': {'type': ['string', 'null'],
                                             'description': '完整 ID，例如 layerweave.preview；add 时是 JS 文件或插件目录路径'},
                                  'name': {'type': ['string', 'null'],
                                           'description': '仅为无 manifest 的开发链接指定短名，最终 ID 为 local.短名'},
                                  'catalog': {'type': ['string', 'null'],
                                              'description': '本次目录 URL/本机 index.json，不改变已有插件的更新来源'},
                                  'version': {'type': ['string', 'null'],
                                              'description': 'info/install 指定版本；install 可用它明确切回旧版本'},
                                  'file': {'type': ['string', 'null'],
                                           'description': 'install 的本地 ZIP，不能同时给 ID、catalog 或 version'},
                                  'files': {'type': 'boolean',
                                            'default': False,
                                            'description': 'remove 时将安装器拥有的文件移至可恢复目录；不删除开发链接源码'},
                                  'root': {'type': ['string', 'null'],
                                           'description': '可选本机状态目录；测试使用临时目录，CLI 对应 --state-root'}},
                   'additionalProperties': False,
                   'required': []},
  'mcp': {'route': 'admin',
          'group': 'view',
          'paths': ['file', 'root'],
          'route_by': 'action',
          'action_routes': {'list': 'query',
                            'market': 'query',
                            'info': 'query',
                            'install': 'admin',
                            'update': 'admin',
                            'add': 'admin',
                            'remove': 'admin',
                            'on': 'admin',
                            'off': 'admin',
                            'migrate': 'admin'},
          'action_paths': {'add': ['target']},
          'uri_paths': ['catalog']},
  'cli_mapping': {'root': ['state_root']},
  'cli_only': ['json']}]


def main():
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(description="视图插件管理", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=help_examples(COMMANDS))
    parser.add_argument("action", nargs="?", default="list", choices=COMMANDS[0]["input_schema"]["properties"]["action"]["enum"])
    parser.add_argument("target", nargs="?", help="完整插件 ID；add 时为路径")
    parser.add_argument("--name"); parser.add_argument("--catalog"); parser.add_argument("--version"); parser.add_argument("--file", type=Path)
    parser.add_argument("--files", action="store_true"); parser.add_argument("--state-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = plugin(args.action, args.target, name=args.name, root=args.state_root, catalog=args.catalog, version=args.version, file=args.file, files=args.files)
    except (ValueError, OSError) as error:
        print(f"没有做成：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["text"])
    return 1 if result.get("status") == "failed" or result.get("problem") else 0


if __name__ == "__main__":
    raise SystemExit(main())
