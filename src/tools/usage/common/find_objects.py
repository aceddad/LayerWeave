"""对象检索：结构条件交给核心查询，内容子串匹配只读取 JSON 中的字符串值。"""

from runtime.api import query_objects


def _contains_text(value, text):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and text in item:
            return True
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False


def find_objects(connection, project_id, *, layer_id=None, name=None, content=None, begin=None, end=None):
    """条件之间为 AND；name/content 区分大小写、按字面匹配，返回原始对象记录列表。"""
    records = query_objects(connection, project_id, layer_id=layer_id, name=name, begin=begin, end=end)
    if content is None:
        return records
    return [record for record in records if _contains_text(record["information"], content)]


def main():
    from tools.shared._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 对象检索（只读，输出 JSON）", commands=COMMANDS)
    parser.add_argument("--layer-id", type=int, help="仅查指定层直接装载的对象")
    parser.add_argument("--name", help="名字中的字面子串")
    parser.add_argument("--content", help="information 字符串值中的字面子串")
    parser.add_argument("--begin", type=float, help="位置范围起点")
    parser.add_argument("--end", type=float, help="位置范围终点；与起点相同时查询该点")
    return run_cli(parser, lambda connection, args: find_objects(
        connection, args.project_id, layer_id=args.layer_id, name=args.name, content=args.content,
        begin=args.begin, end=args.end,
    ))



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'find_objects',
  'summary': '按层、名称、内容字符串或位置查询对象',
  'entrypoint': 'tools.usage.common.find_objects:find_objects',
  'cli': 'python -m tools.usage.common.find_objects',
  'read_only': True,
  'context': ['database', 'project_id'],
  'parameters': {'layer_id': {'type': 'integer', 'description': '该项目内的层编号，仅直属对象'},
                 'name': {'type': 'string', 'description': '名字字面子串'},
                 'content': {'type': 'string', 'description': 'information 中字符串值的字面子串'},
                 'begin': {'type': 'number', 'description': '轴上的数值位置，不换算单位'},
                 'end': {'type': 'number', 'description': '轴上的数值位置，不换算单位'}},
  'returns': '匹配的对象记录列表；不修改内容。',
  'examples': [{'cli': 'python -m tools.usage.common.find_objects DATABASE 1 --layer-id 4 --content 歌词'}],
  'aliases': ['tools.common.find_objects:find_objects']}]


if __name__ == "__main__":
    raise SystemExit(main())
