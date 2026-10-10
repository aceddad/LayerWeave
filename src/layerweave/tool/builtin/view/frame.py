"""某一刻的画面：取视频对象在某个时间的那一帧，存成 JPEG。需要 ffmpeg（PATH 里，或环境变量 FFMPEG）。

python -m layerweave.tool.builtin.view.frame DATABASE PROJECT_ID OBJECT_ID 输出.jpg (--at 全片秒数 | --offset 片内秒数 | --last) [--width 960]
--at 用时间轴上的全局位置（和视图、播放头一致）；--offset 用这个视频自己的时间；--last 取视频文件的最后一帧。
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sys

from layerweave.support.api import read_record

from .data import extract_frame, media_path, open_readonly


def grab(database, project_id, object_id, output, *, at=None, offset=None, last=False, width=960):
    if (at is not None) + (offset is not None) + bool(last) != 1:
        raise ValueError("--at、--offset、--last 三选一")
    with closing(open_readonly(database)) as connection:
        row = read_record(connection, "object", project_id=project_id, id=object_id)
        if row is None:
            raise ValueError(f"对象 ({project_id}, {object_id}) 不存在")
        path = media_path(connection, database, project_id, object_id)
    if path is None:
        raise ValueError(f"对象 {object_id} 没有可读取的视频文件（information.source）")
    seconds = "end" if last else offset if offset is not None else at - row["begin"]
    if seconds != "end" and seconds < 0:
        raise ValueError(f"{at} 早于这个对象的开始位置 {row['begin']}")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(extract_frame(path, seconds, width=width))
    return {"output": str(output.resolve()), "object": object_id, "source": str(path),
            "offset": "end" if seconds == "end" else round(seconds, 3)}


COMMANDS = [{
    "name": "view_frame",
    "summary": "取视频对象在某一刻的画面（JPEG），可按时间轴的全局时间、视频自身时间，或取最后一帧",
    "entrypoint": "layerweave.tool.builtin.view.frame:grab",
    "cli": "python -m layerweave.tool.builtin.view.frame",
    "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "object_id": {"type": "integer", "required": True, "description": "视频对象编号"},
        "output": {"type": "string", "required": True, "description": "由 AI 指定的 JPEG 输出路径"},
        "at": {"type": "number", "description": "时间轴上的全局位置；与 offset、last 三选一"},
        "offset": {"type": "number", "description": "视频自身的秒数；与 at、last 三选一"},
        "last": {"type": "boolean", "description": "取视频文件的最后一帧；与 at、offset 三选一", "default": False},
        "width": {"type": "integer", "default": 960},
    },
    "returns": "output、object、source、offset（实际取帧的片内秒数；取最后一帧时为 end）。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.frame DATABASE 1 16 frames/ball_3s.jpg --at 3.75"},
                 {"cli": "python -m layerweave.tool.builtin.view.frame DATABASE 1 16 frames/ball_last.jpg --last"}],
    "notes": ["需要 ffmpeg；超出视频长度时取最后一帧。", "查前后两段是否接得上，可以先看视图的接缝页（view_screenshot --view cuts）。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="取视频对象某一刻的画面", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int); p.add_argument("object_id", type=int)
    p.add_argument("output", type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--at", type=float); group.add_argument("--offset", type=float)
    group.add_argument("--last", action="store_true", help="取最后一帧")
    p.add_argument("--width", type=int, default=960)
    a = p.parse_args()
    try:
        result = grab(a.database, a.project_id, a.object_id, a.output, at=a.at, offset=a.offset, last=a.last, width=a.width)
    except (ValueError, OSError, RuntimeError) as error:
        print(f"取帧失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
