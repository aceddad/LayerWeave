"""按位置顺序汇集一层中的 text 及其派生对象，保留来源编号，不合并或修改原对象。"""

from runtime.api import Loader, query_objects, read_record, read_snapshot, diagnostic_report


def collect_text(connection, project_id, layer_id, *, separator="\n", begin=None, end=None, config_root=None):
    """返回 text/items/skipped_count/issues；缺少层返回 None，配置或内容错误逐项报告。"""
    with read_snapshot(connection):
        if read_record(connection, "layer", project_id=project_id, id=layer_id) is None:
            return None
        records = query_objects(connection, project_id, layer_id=layer_id, begin=begin, end=end)
    result = {"project_id": project_id, "layer_id": layer_id, "status": "completed",
              "text": "", "items": [], "skipped_count": 0, "issues": []}
    if not records:
        return result
    loader = Loader() if config_root is None else Loader(config_root)
    references = {row["id"]: row["config_ref"] for row in records}

    def issue(kind, id, field, message, code="field_type", details=None):
        ref = references.get(id) if kind == "object" else None
        result["issues"].append({"rule": "collect_text", "code": code, "config_ref": ref,
                                 "target": {"kind": kind, "project_id": project_id, "id": id},
                                 "field": field, "message": message, **(details or {})})

    def finish():
        # 汇集是否完整取决于提取结果，不因为静音诊断而改成完整。
        if result["issues"]:
            result["status"] = "partial"
        result["issues"] = diagnostic_report(result["issues"], config_root=config_root)["issues"]
        return result

    try:
        expected = loader.object_config("text")
    except (ValueError, OSError) as error:
        issue("layer", layer_id, "config_ref", f"文字基准配置不可用，未汇集本层文本：{error}", code="configuration", details=getattr(error, "details", {}))
        result.update(status="partial", skipped_count=len(records))
        return finish()

    for record in records:
        try:
            config = loader.load(record["config_ref"], "object")
        except (ValueError, OSError) as error:
            issue("object", record["id"], "config_ref", f"无法判断对象是否为文字类型：{error}", code="configuration", details=getattr(error, "details", {}))
            continue
        if expected["_ref"] not in config["_lineage"]:
            continue
        information = record["information"]
        if not isinstance(information, dict):
            issue("object", record["id"], "information", "内容不是字典，无法提取文字")
            continue
        if "text" not in information:
            if not config.get("information", {}).get("text", {}).get("optional", False):
                issue("object", record["id"], "information.text", "未填写配置声明的文字字段，请检查是否漏填或字段名写错", code="missing_field")
            continue
        if not isinstance(information["text"], str):
            issue("object", record["id"], "information.text", "文字不是字符串，未将它自动转成文本")
            continue
        result["items"].append({**{key: record[key] for key in ("project_id", "id", "layer", "name", "config_ref", "begin", "end")},
                                "text": information["text"]})
    result["text"] = separator.join(item["text"] for item in result["items"])
    result["skipped_count"] = len(records) - len(result["items"])
    return finish()


def main():
    from tools.shared._cli import parser_for, run_cli

    parser = parser_for("LayerWeave 文本汇集（只读）", commands=COMMANDS)
    parser.add_argument("layer_id", type=int, help="仅汇集该层直接装载的文字对象")
    parser.add_argument("--separator", default="\n", help="文本间分隔符，默认换行")
    parser.add_argument("--begin", type=float, help="位置范围起点")
    parser.add_argument("--end", type=float, help="位置范围终点")
    parser.add_argument("--config-root", help="自定义配置目录")
    return run_cli(parser, lambda connection, args: collect_text(
        connection, args.project_id, args.layer_id, separator=args.separator,
        begin=args.begin, end=args.end, config_root=args.config_root,
    ), formatter=lambda result: "层不存在。" if result is None else result["text"])



# 命令目录和 --help 共用的只读接口说明。
COMMANDS = [{'name': 'collect_text',
  'summary': '汇集某层的文字及派生文字对象，保留来源',
  'entrypoint': 'tools.usage.text.collect:collect_text',
  'cli': 'python -m tools.usage.text.collect',
  'read_only': True,
  'context': ['database', 'project_id'],
  'parameters': {'layer_id': {'type': 'integer', 'description': '仅汇集该层直属对象', 'required': True},
                 'separator': {'type': 'string', 'description': '文本分隔符', 'default': '\n'},
                 'begin': {'type': 'number', 'description': '轴上的数值位置，不换算单位'},
                 'end': {'type': 'number', 'description': '轴上的数值位置，不换算单位'},
                 'config_root': {'type': 'string', 'description': '检查或配置查询采用的配置根目录；省略使用项目 configs'}},
  'returns': 'text、来源 items、skipped_count、status 和逐条 issues。',
  'examples': [{'cli': 'python -m tools.usage.text.collect DATABASE 1 4 --json'}]}]


if __name__ == "__main__":
    raise SystemExit(main())
