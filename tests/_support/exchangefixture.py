"""交换场景的临时数据库、节点查询和工具表夹具。"""
from layerweave.support.api import open_database, transaction, register_tables
from layerweave.support.storage.database import SCHEMA_PATH
from layerweave.tool.builtin.usage.exchange import import_project


class ExchangeFixture:
    def database(self, path=":memory:"):
        c = open_database(path)
        self.addCleanup(c.close)
        c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        return c
    def setUp(self):
        self.c = self.database()
        with transaction(self.c) as w:
            self.p = w.create("project", {"name":"原项目", "tips":"说明"})["id"]
            self.a = w.create("layer", {"name":"故事", "type":"text", "config_ref":"layers/text.toml"}, project_id=self.p)["id"]
            self.child = w.create("layer", {"name":"子层", "type":"text", "config_ref":"layers/text.toml", "father":self.a}, project_id=self.p)["id"]
            self.b = w.create("layer", {"name":"独立根", "type":"text", "config_ref":"layers/text.toml"}, project_id=self.p)["id"]
            self.obj = w.create("object", {"name":"开场", "layer":self.child, "config_ref":"objects/text.toml",
                                          "begin":0, "end":2, "information":{"text":"旧正文"}}, project_id=self.p)["id"]
            self.late = w.create("object", {"name":"后段", "layer":self.child, "config_ref":"objects/text.toml",
                                           "begin":5, "end":8, "information":{"text":"后段"}}, project_id=self.p)["id"]
            self.bind = w.create("bind", {"source_kind":"object","source_project_id":self.p,"source_id":self.obj,
                                         "target_kind":"layer","target_project_id":self.p,"target_id":self.b})["id"]
    def document(self, items, **extra):
        return {"format_version":1,"project_id":self.p,"items":items,**extra}
    def apply(self, doc, **kwargs):
        return import_project(self.c,doc,checker=None,**kwargs)
    def nodes(self, document):
        def visit(items):
            for item in items:
                yield item
                yield from visit(item.get("children",[]))
        return [*visit(document.get("items",[])),*document.get("records",[])]
    def find(self, doc, kind, id):
        return next(node for node in self.nodes(doc) if node["kind"] == kind and node["id"] == id)
    def tools(self):
        register_tables(self.c,{
            "note":{"fields":{"object_id":"INTEGER","text":"TEXT"},
                    "references":[{"fields":["project_id","object_id"],"kind":"object"}]},
            "view_state":{"id_source":"provided","fields":{"collapsed":{"type":"INTEGER","default":0}},
                          "references":[{"fields":["project_id","id"],"kind":"layer"}]},
            "global_note":{"scoped":False,"fields":{"owner":"INTEGER","object_id":"INTEGER","text":"TEXT"},
                           "references":[{"fields":["owner","object_id"],"kind":"object"}]},
            "catalog":{"scoped":False,"fields":{"text":"TEXT"}}
        })
        with transaction(self.c) as w:
            self.note = w.create("note",{"object_id":self.obj,"text":"批注"},project_id=self.p)["id"]
            w.create("view_state",{"id":self.child,"collapsed":1},project_id=self.p)
            w.create("global_note",{"owner":self.p,"object_id":self.obj,"text":"相关全局记录"})
            w.create("catalog",{"text":"不属于某个项目"})
