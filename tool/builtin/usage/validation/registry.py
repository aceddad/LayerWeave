"""普通登记表：函数路径、触发字段、检查范围；不在这里导入规则模块。"""

# fields=None 表示任意字段；config_ref 变化和新建会触发该种类的全部相关规则。
# scope：self 当前记录，layer 相关旧/新层，binds 关联自身或被删除实体的关联。
RULES = {
    "layer_type": {
        "function": "tool.builtin.usage.validation.rules.layers:layer_type",
        "triggers": {"layer": ("type",)}, "scope": "self",
    },
    "fields": {
        "function": "tool.builtin.usage.validation.rules.fields:check",
        "triggers": {"layer": None, "object": None}, "scope": "self",
    },
    "no_cycle": {
        "function": "tool.builtin.usage.validation.rules.layers:no_cycle",
        "triggers": {"layer": ("father",)}, "scope": "self",
        "setting": ("rules", "no_cycle"),
    },
    "axis_only_on_root": {
        "function": "tool.builtin.usage.validation.rules.layers:axis_only_on_root",
        "triggers": {"layer": ("axis", "father")}, "scope": "self",
        "setting": ("options", "axis_only_on_root"),
    },
    "accepts_objects": {
        "function": "tool.builtin.usage.validation.rules.layers:accepts_objects",
        "triggers": {"layer": ("config_ref",), "object": ("layer", "config_ref")}, "scope": "layer",
    },
    "overlap": {
        "function": "tool.builtin.usage.validation.rules.layers:overlap",
        "triggers": {"layer": ("config_ref",), "object": ("layer", "begin", "end")}, "scope": "layer",
        "setting": ("constraint", "overlap"), "enabled": False,
    },
    "begin_le_end": {
        "function": "tool.builtin.usage.validation.rules.objects:begin_le_end",
        "triggers": {"object": ("begin", "end")}, "scope": "self",
        "setting": ("rules", "begin_le_end"),
    },
    "duration": {
        "function": "tool.builtin.usage.validation.rules.objects:duration",
        "triggers": {"object": ("begin", "end")}, "scope": "self",
        "setting": ("constraint", "duration"), "values": ("any", "positive", "zero"), "disabled": "any",
    },
    "bind_endpoints": {
        "function": "tool.builtin.usage.validation.rules.binds:check",
        "triggers": {
            "bind": ("source_kind", "source_project_id", "source_id", "target_kind", "target_project_id", "target_id"),
            "layer": (), "object": (),
        }, "scope": "binds", "config": False,
    },
}
