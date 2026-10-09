"""外置技能 ZIP 安装：只放置文件并返回路由，不执行技能或修改层配置。"""

import argparse
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import zipfile

from runtime.feedback import InputError, error_detail


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SKILLS_ROOT = PROJECT_ROOT / "tool" / "skills"


def _component(value, field):
    """只限制文件系统路径，不约束技能名或层类型的业务含义。"""
    if (not isinstance(value, str) or not value or value in {".", ".."}
            or any(char in '/\\<>:"|?*' or ord(char) < 32 for char in value)
            or value.endswith((".", " ")) or PureWindowsPath(value).is_reserved()):
        raise InputError(f"{field} 需要一个普通文件或目录名：{value!r}", field=field, code="unsafe_path")
    return value


def _zip_path(value):
    value = value.replace("\\", "/")
    if value.startswith("/"):
        raise InputError(f"ZIP 不允许绝对路径：{value}", code="unsafe_path")
    parts = [part for part in value.split("/") if part not in {"", "."}]
    for part in parts:
        _component(part, "ZIP 路径")
    return PurePosixPath(*parts)


def _entries(archive):
    entries, seen = [], {}
    for info in archive.infolist():
        path = _zip_path(info.orig_filename)
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise InputError(f"ZIP 不支持链接或特殊文件：{info.filename}", code="unsupported_entry")
        directory = info.filename.replace("\\", "/").endswith("/") or kind == stat.S_IFDIR
        if path == PurePosixPath("."):
            if directory:
                continue
            raise InputError("ZIP 文件路径为空", code="unsafe_path")
        key = path.as_posix().casefold()
        if key in seen:
            if directory and seen[key]:
                continue
            raise InputError(f"ZIP 路径重复或冲突：{path}", code="duplicate_path")
        seen[key] = directory
        entries.append((info, path, directory))
    return entries


def _select(entries, source_dir):
    roots = {path.parent for _, path, directory in entries if not directory and path.name == "SKILL.md"}
    # 包内引用资料可以另带 SKILL.md；默认选择最外层的技能包。
    candidates = sorted(path.as_posix() for path in roots if not any(parent in roots for parent in path.parents))
    if source_dir is not None:
        selected = _zip_path(str(source_dir))
        if selected not in roots:
            raise InputError("指定目录下没有 SKILL.md", field="source_dir", code="skill_not_found", candidates=candidates)
        return selected
    if not candidates:
        raise InputError("ZIP 中没有找到 SKILL.md", code="skill_not_found")
    if len(candidates) != 1:
        raise InputError("ZIP 中有多个技能，请用 --source-dir 指定其中一个目录", field="source_dir",
                         code="multiple_skills", candidates=candidates)
    return PurePosixPath(candidates[0])


def _inside(root, target):
    resolved = target.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        raise InputError(f"目标超出技能存放目录：{target}", code="unsafe_path")
    return resolved


def install_skill(archive, *, layer=None, scenario=False, name=None, source_dir=None, skills_root=DEFAULT_SKILLS_ROOT):
    """解包一个技能到指定类别；失败清理本次新目录，同名目标保持原样。"""
    if (layer is not None) + bool(scenario) != 1:
        raise InputError("请选择 --layer 层类型 或 --scenario", code="destination", field="layer/scenario")
    root = Path(skills_root).resolve()
    category = root / "layers" / _component(layer, "layer") if layer is not None else root / "scenarios"
    archive = Path(archive).resolve()
    with zipfile.ZipFile(archive) as package:
        entries = _entries(package)
        selected = _select(entries, source_dir)
        folder = _component(name if name is not None else selected.name or archive.stem, "name")
        target = category / folder
        resolved = _inside(root, target)
        if target.exists() or target.is_symlink():
            raise InputError(f"目标已存在：{target}；可用 --name 另取目录名", code="destination_exists", path=str(target))
        category.mkdir(parents=True, exist_ok=True)
        _inside(root, target)
        try:
            target.mkdir()  # 独占新目录，已有目录绝不合并或覆盖。
        except FileExistsError as error:
            raise InputError(f"目标已存在：{target}", code="destination_exists", path=str(target)) from error
        count = 0
        try:
            for info, path, directory in entries:
                if not path.is_relative_to(selected):
                    continue
                relative = path.relative_to(selected)
                destination = target.joinpath(*relative.parts)
                if relative == PurePosixPath("."):
                    continue
                _inside(resolved, destination)
                if directory:
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(info) as source, destination.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    executable = (info.external_attr >> 16) & 0o111
                    if os.name != "nt" and executable:
                        destination.chmod(destination.stat().st_mode | executable)
                    count += 1
        except BaseException:
            # 只清理由本次 mkdir 创建的目录；删除前再次核对绝对边界。
            if _inside(root, target) != resolved:
                raise InputError("安装目录在写入过程中发生变化，未清理该目录", code="destination_changed")
            shutil.rmtree(target)
            raise
    skill = resolved / "SKILL.md"
    route = skill.relative_to(PROJECT_ROOT).as_posix() if skill.is_relative_to(PROJECT_ROOT) else skill.as_posix()
    return {"ok": True, "name": folder, "path": str(resolved), "route": route,
            "source_dir": selected.as_posix(), "files": count}


def main():
    from tools.shared.catalog import help_examples
    parser = argparse.ArgumentParser(description="从本地 ZIP 安装外置技能，只放置文件并返回 route",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=help_examples(COMMANDS))
    parser.add_argument("archive", type=Path, help="已下载的 ZIP 文件；内容为 ZIP 的 .skill 文件也可用")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--layer", help="放入 layers 下对应的层类型目录，例如 text")
    scope.add_argument("--scenario", action="store_true", help="放入场景补充目录 scenarios")
    parser.add_argument("--name", help="安装目录名；默认包内技能目录名，平铺 ZIP 使用压缩包文件名")
    parser.add_argument("--source-dir", help="ZIP 中包含 SKILL.md 的目录；有多个技能时用此参数选择")
    parser.add_argument("--skills-root", type=Path, default=DEFAULT_SKILLS_ROOT, help="技能存放根目录，默认项目 tool/skills")
    parser.add_argument("--json", action="store_true", help="输出结构化结果或错误")
    args = parser.parse_args()
    try:
        result = install_skill(args.archive, layer=args.layer, scenario=args.scenario, name=args.name,
                               source_dir=args.source_dir, skills_root=args.skills_root)
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, NotImplementedError) as error:
        result = {"ok": False, "error": error_detail(error)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result["ok"]:
        print(f"已安装：{result['path']}\n文件数：{result['files']}\nroute: {result['route']}")
    else:
        print("安装失败：" + result["error"]["message"])
        if result["error"].get("candidates"):
            print("可选目录：" + " / ".join(result["error"]["candidates"]))
    return 0 if result["ok"] else 1


COMMANDS = [{
    "name": "install_skill", "summary": "把本地技能 ZIP 安装到指定层或场景区，返回 route，不自动绑定",
    "entrypoint": "tools.developer.skills:install_skill", "cli": "python -m tools.developer.skills",
    "read_only": False, "context": [],
    "parameters": {
        "archive": {"type": "string", "required": True, "description": "本地 ZIP 路径，按 ZIP 内容读取"},
        "layer": {"type": "string", "description": "目标层类型，与 scenario 二选一"},
        "scenario": {"type": "boolean", "default": False, "description": "安装到场景补充区，与 layer 二选一"},
        "name": {"type": "string", "description": "安装目录名；默认技能所在目录名，平铺包使用 ZIP 文件名去扩展名"},
        "source_dir": {"type": "string", "description": "包内技能目录，多个技能时明确选择；根目录用 ."},
        "skills_root": {"type": "string", "description": "存放根目录，默认项目 tool/skills"}
    },
    "returns": "成功返回 ok/name/path/route/source_dir/files；Python 失败抛出异常，CLI 返回 ok=false 和 error。",
    "examples": [{"cli": "python -m tools.developer.skills SKILL.zip --layer text --json"},
                 {"cli": "python -m tools.developer.skills SKILL.zip --scenario --name lyric-align --json"},
                 {"cli": "python -m tools.developer.skills BUNDLE.zip --layer audio --source-dir bundle/audio-skill --json"}],
    "notes": ["支持根目录 SKILL.md 和外层目录包装；只安装选中的技能目录。",
              "不覆盖同名目录；失败清理本次新建的技能目录。拒绝越界路径、链接和路径冲突。",
              "保留技能正文和附带文件，不检查 frontmatter、不执行脚本、不安装依赖、不修改层 tools。"]
}]


if __name__ == "__main__":
    raise SystemExit(main())
