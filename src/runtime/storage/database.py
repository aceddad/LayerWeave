"""初始化 SQLite 业务表及日志表，并提供项目内共用的发号方法。"""

from contextlib import closing
from pathlib import Path
import sqlite3

from ..feedback import InputError, target


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def open_database(path: str | Path) -> sqlite3.Connection:
    """打开连接并启用外键；调用方负责提交事务和关闭连接。"""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(path: str | Path) -> Path:
    """创建缺失表，升级所属层、关联发号及日志列；保留数据与日志。"""
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(open_database(path)) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        require_object_layer(connection)
        upgrade_history(connection)
    return path


def require_object_layer(connection):
    """一次性升级已知旧结构；没有所属层的旧对象必须先由调用方明确归属。"""
    column = next(row for row in connection.execute('PRAGMA table_info("objects")') if row["name"] == "layer")
    if column["notnull"]:
        return
    if connection.in_transaction:
        raise ValueError("结构迁移需要没有待提交操作的连接")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        unowned = connection.execute("SELECT project_id, id FROM objects WHERE layer IS NULL").fetchall()
        if unowned:
            raise ValueError(f"旧对象缺少所属层，请先明确归属再迁移：{[(row['project_id'], row['id']) for row in unowned]}")
        definitions = [row[0] for row in connection.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name = 'objects' AND type IN ('index', 'trigger') AND sql IS NOT NULL"
        )]
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        create = schema[schema.index("CREATE TABLE IF NOT EXISTS objects ("):].split(";", 1)[0]
        connection.execute(create.replace("CREATE TABLE IF NOT EXISTS objects", "CREATE TABLE objects_required"))
        columns = 'project_id, id, name, config_ref, layer, "begin", "end", information, tips'
        connection.execute(f"INSERT INTO objects_required ({columns}) SELECT {columns} FROM objects")
        connection.execute("DROP TABLE objects")
        connection.execute("ALTER TABLE objects_required RENAME TO objects")
        for definition in definitions:
            connection.execute(definition)


def upgrade_history(connection):
    """保留旧记录/日志/附加索引，升级关联持久发号和撤销来源字段。"""
    if connection.in_transaction:
        raise ValueError("结构迁移需要没有待提交操作的连接")
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(changes)")}
        if "undo_of" not in columns:
            connection.execute("ALTER TABLE changes ADD COLUMN undo_of TEXT")
        sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='binds'").fetchone()[0]
        if "AUTOINCREMENT" not in sql.upper():
            definitions = [row[0] for row in connection.execute(
                "SELECT sql FROM sqlite_master WHERE tbl_name='binds' AND type IN ('index','trigger') AND sql IS NOT NULL")]
            schema = SCHEMA_PATH.read_text(encoding="utf-8")
            create = schema[schema.index("CREATE TABLE IF NOT EXISTS binds ("):].split(";", 1)[0]
            connection.execute(create.replace("CREATE TABLE IF NOT EXISTS binds", "CREATE TABLE binds_numbered"))
            connection.execute("INSERT INTO binds_numbered SELECT * FROM binds")
            connection.execute("DROP TABLE binds")
            connection.execute("ALTER TABLE binds_numbered RENAME TO binds")
            for definition in definitions:
                connection.execute(definition)
        # 已删除的历史编号也保留；重复初始化不能降低已有持久序列。
        maximum = connection.execute("SELECT MAX(n) FROM (SELECT MAX(id) n FROM binds UNION ALL "
                                     "SELECT MAX(target_id) FROM changes WHERE kind='bind')").fetchone()[0] or 0
        row = connection.execute("SELECT seq FROM sqlite_sequence WHERE name='binds'").fetchone()
        if row is None:
            connection.execute("INSERT INTO sqlite_sequence(name,seq) VALUES ('binds',?)", (maximum,))
        elif maximum > row[0]:
            connection.execute("UPDATE sqlite_sequence SET seq=? WHERE name='binds'", (maximum,))


def allocate_id(connection: sqlite3.Connection, project_id: int) -> int:
    """申请项目内的下一个层/对象编号；不提交，由调用方与实体写入一起提交。"""
    row = connection.execute(
        "UPDATE projects SET max_id = max_id + 1 WHERE id = ? RETURNING max_id",
        (project_id,),
    ).fetchone()
    if row is None:
        raise InputError(f"项目 {project_id} 不存在", code="missing_reference", field="project_id",
                         reference=target("project", None, project_id))
    return row[0]
