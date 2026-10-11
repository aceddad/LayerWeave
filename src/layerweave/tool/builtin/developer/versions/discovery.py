"""只读 component.toml；不导入组件，也不推断代码是否可运行。"""
from datetime import datetime, timezone
import os
from pathlib import Path
import tomllib

from layerweave.support.paths import BUILTIN_ROOT, PACKAGE_ROOT


def path_key(path):
    return Path(os.path.normcase(os.path.abspath(Path(path).expanduser()))).as_posix()


def within(path, root):
    return Path(path).is_relative_to(Path(root))


def scan_components(roots=None):
    """扫描目录或单个声明；失败路径单独返回，避免误判成已删除。"""
    if roots is None:
        roots = [PACKAGE_ROOT / "component.toml", BUILTIN_ROOT]
    elif isinstance(roots, (str, Path)):
        roots = [roots]
    roots = sorted(set(path_key(root) for root in roots))
    files, failed, issues = set(), set(), []

    def failure(path, error):
        source = path_key(path)
        failed.add(source)
        issues.append({"code": "component_read", "source": source, "message": str(error)})

    for root in roots:
        try:
            path = Path(root)
            try:
                path.stat()
            except FileNotFoundError:
                continue  # 不存在是完整的空扫描，原登记版本将失效。
            if path.is_dir():
                for directory, _, names in os.walk(path, onerror=lambda error: failure(error.filename or root, error)):
                    if "component.toml" in names:
                        files.add(path_key(Path(directory) / "component.toml"))
            elif path.name == "component.toml":
                files.add(root)
            else:
                raise ValueError("扫描入口应为目录或 component.toml 文件")
        except OSError as error:
            failure(root, error)
        except ValueError as error:
            failure(root, error)

    items = []
    for source in sorted(files):
        try:
            data = tomllib.loads(Path(source).read_text(encoding="utf-8-sig"))
            for field in ("name", "version"):
                if not isinstance(data.get(field), str) or not data[field].strip():
                    raise ValueError(f"{field} 需要非空字符串")
            item = {"name": data["name"], "version": data["version"],
                    "kind": data.get("kind", "tool"), "description": data.get("description", ""),
                    "changes": data.get("changes", "")}
            for field in ("kind", "description", "changes"):
                if not isinstance(item[field], str):
                    raise ValueError(f"{field} 需要字符串")
            items.append({**item, "source": source})
        except FileNotFoundError:
            continue  # 枚举后删除仍按不存在处理。
        except (OSError, ValueError, UnicodeError) as error:
            failure(source, error)
    return {"roots": roots, "items": items, "failed": sorted(failed), "issues": issues,
            "status": "partial" if issues else "completed",
            "checked_at": datetime.now(timezone.utc).isoformat()}
