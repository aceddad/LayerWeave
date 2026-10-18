"""命令参数的一份结构化来源；说明转换只使用标准库，不执行工具。"""
from copy import deepcopy


CONTEXT = {
    "database": {"type": "string", "description": "SQLite 数据库路径；Python 连接由适配器提供"},
    "project_id": {"type": "integer", "description": "明确的项目编号"},
}


def from_parameters(parameters, context=()):
    """读取原有说明格式；新的命令直接声明 input_schema。"""
    properties = deepcopy({key: CONTEXT[key] for key in context})
    required = list(context)
    for name, item in parameters.items():
        spec = deepcopy(item)
        if spec.pop("required", False) and name not in required:
            required.append(name)
        if "choices" in spec:
            spec["enum"] = spec.pop("choices")
        properties[name] = spec
    result = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        result["required"] = required
    return result


def parameters_from_schema(schema):
    """CLI 文字帮助继续使用熟悉的参数展示，内容从 Schema 派生。"""
    required = schema.get("required", [])
    result = {}
    for name, value in schema.get("properties", {}).items():
        spec = deepcopy(value)
        spec["required"] = name in required
        if "enum" in spec:
            spec["choices"] = spec.pop("enum")
        result[name] = spec
    return result


def command_schema(command):
    if "input_schema" not in command:
        return from_parameters(command.get("parameters", {}), command.get("context", []))
    schema = deepcopy(command["input_schema"])
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError("input_schema 需要 type=object 的 JSON Schema")
    if not isinstance(schema.get("properties", {}), dict):
        raise ValueError("input_schema.properties 需要对象")
    if not isinstance(schema.get("required", []), list):
        raise ValueError("input_schema.required 需要字段名列表")
    return schema


def select_parameters(schema, *, include=None, omit=()):
    """同一业务说明的入口投影，例如看图不接收保存文件的 output。"""
    result = deepcopy(schema)
    properties = result.setdefault("properties", {})
    keep = set(properties if include is None else include) - set(omit)
    result["properties"] = {k: v for k, v in properties.items() if k in keep}
    result["required"] = [k for k in result.get("required", []) if k in keep]
    return result
