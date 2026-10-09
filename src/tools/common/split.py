"""按显式内容分割对象，支持单点或多点，不推测媒体切片。"""

import json
from pathlib import Path
from runtime.api import split_object, format_feedback


def format_split(result):
    lines = [f"分割操作：{result['operation_id']}", format_feedback(result)]
    if result["ok"]:
        for segment in result["data"]["segments"]:
            lines.append(f"对象 {segment['id']}：[{segment['begin']}, {segment['end']})")
        lines.append("实际切点：" + json.dumps(result["data"]["cuts"], ensure_ascii=False))
    return "\n".join(lines)


def main():
    from tools._cli import parser_for, run_cli
    parser = parser_for("LayerWeave 分割：数据文件提供 first_information 与 cuts")
    parser.add_argument("object_id", type=int)
    parser.add_argument("--data-file", type=Path, required=True)
    parser.add_argument("--config-root")
    def execute(connection, args):
        payload = json.loads(args.data_file.read_text(encoding="utf-8-sig"))
        return split_object(connection, args.project_id, args.object_id, **payload,
                            **({"config_root": args.config_root} if args.config_root is not None else {}))
    return run_cli(parser, execute, formatter=format_split)


if __name__ == "__main__":
    raise SystemExit(main())
