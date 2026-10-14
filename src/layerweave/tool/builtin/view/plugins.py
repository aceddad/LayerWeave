"""视图插件：工具包在自己的 component.toml 里登记，视图服务找出来交给页面加载。

    [[view_plugins]]
    name = "cuts"                       # 页面名，也是地址里的 view=cuts；小写字母、数字、- 和 _
    entry = "plugins/cuts/plugin.js"    # 编译好的 ES 模块，相对这个 component.toml 所在的目录

插件只在页面里运行，默认导出一个函数 (host) => ViewPlugin（接口见 frontend/view/src/plugin/host.ts，做法见 developer/TOOL_TYPES.md）。
这里只读 TOML、确认文件在包目录里面，不导入、不运行任何东西。现在只找包里内置的工具包（support.paths.BUILTIN_ROOT）；
装在包外面的工具包怎么找，跟着 LayerWeave 以后定的做法走。
"""
import os
from pathlib import Path
import re
import tomllib

from layerweave.support.paths import BUILTIN_ROOT

NAME = re.compile(r"[a-z][a-z0-9_-]{0,39}")
RESERVED = {"canvas", "assets"}        # 视图自己的页面


def find_plugins(roots=None):
    """{"plugins": [{name, path, component}], "issues": [...]}。同名的只留路径排在前面的那个，其余记一条问题。"""
    roots = [Path(r) for r in (roots or [BUILTIN_ROOT])]
    plugins, issues, seen = [], [], {}
    files = []
    for root in roots:
        if root.is_file() and root.name == "component.toml":
            files.append(root)
            continue
        for directory, names, filenames in os.walk(root):
            names[:] = sorted(n for n in names if n not in ("__pycache__", "node_modules"))
            if "component.toml" in filenames:
                files.append(Path(directory) / "component.toml")
    for file in sorted(files):
        try:
            data = tomllib.loads(file.read_text(encoding="utf-8-sig"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            issues.append({"source": str(file), "message": f"读不了：{error}"})
            continue
        declared = data.get("view_plugins", [])
        if not isinstance(declared, list):
            issues.append({"source": str(file), "message": "view_plugins 要写成 [[view_plugins]] 表数组"})
            continue
        base = file.parent.resolve()
        for item in declared:
            name, entry = (item.get("name"), item.get("entry")) if isinstance(item, dict) else (None, None)
            if not isinstance(name, str) or not NAME.fullmatch(name) or name in RESERVED:
                issues.append({"source": str(file), "message": f"插件名 {name!r} 不合规矩：小写字母开头，字母、数字、- 和 _，不能叫 canvas、assets"})
                continue
            path = (base / str(entry or "")).resolve()
            if not entry or not path.is_relative_to(base) or path.suffix != ".js" or not path.is_file():
                issues.append({"source": str(file), "message": f"插件 {name} 的入口 {entry!r} 要是这个目录里一个存在的 .js 文件"})
                continue
            if name in seen:
                issues.append({"source": str(file), "message": f"插件名 {name} 和 {seen[name]} 里的重了，用前面那个"})
                continue
            seen[name] = str(file)
            plugins.append({"name": name, "path": path, "component": data.get("name", "")})
    return {"plugins": plugins, "issues": issues}
