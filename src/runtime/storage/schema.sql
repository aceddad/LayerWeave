-- SQLite 表结构。重复执行只初始化缺失的表；旧版列结构由 database.py 显式迁移。
-- 外键须在每个连接上启用；本脚本应在没有待提交业务操作的连接上执行。
PRAGMA foreign_keys = ON;

BEGIN;

CREATE TABLE IF NOT EXISTS projects (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL DEFAULT '',
    max_id  INTEGER NOT NULL DEFAULT 0, -- 历史上已发放的最大层/对象编号，不随删除回退
    tips    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS layers (
    project_id  INTEGER NOT NULL,
    id          INTEGER NOT NULL,      -- 项目内编号，由项目级发号方法提供
    name        TEXT NOT NULL DEFAULT '',
    type        TEXT NOT NULL,         -- 保存配置中的类型标识，例如 Layer、text、image
    config_ref  TEXT NOT NULL,         -- 相对于 configs/，例如 layers/image.toml
    father      INTEGER,               -- 同项目的父层编号；NULL 表示模块根
    axis        TEXT,                  -- JSON；没有轴说明时为 SQL NULL
    tips        TEXT NOT NULL DEFAULT '',

    PRIMARY KEY (project_id, id),
    FOREIGN KEY (project_id) REFERENCES projects (id),
    FOREIGN KEY (project_id, father) REFERENCES layers (project_id, id)
);

CREATE TABLE IF NOT EXISTS objects (
    project_id  INTEGER NOT NULL,
    id          INTEGER NOT NULL,      -- 与本项目的层共用发号方法
    name        TEXT NOT NULL DEFAULT '',
    config_ref  TEXT NOT NULL,         -- 相对于 configs/，例如 objects/image.toml
    layer       INTEGER NOT NULL,      -- 同项目的所属层编号；对象必须有实际归属
    "begin"     REAL NOT NULL DEFAULT 0.0,
    "end"       REAL NOT NULL DEFAULT 0.0,
    information TEXT NOT NULL DEFAULT '{}', -- JSON 内容，原样保存扩展键
    tips        TEXT NOT NULL DEFAULT '',

    PRIMARY KEY (project_id, id),
    FOREIGN KEY (project_id) REFERENCES projects (id),
    FOREIGN KEY (project_id, layer) REFERENCES layers (project_id, id)
);

-- 两端都是普通引用，不建立指向实体的外键。
-- 目标消失时保留关联，后续检测通道可据此报告失效引用。
CREATE TABLE IF NOT EXISTS binds (
    id                  INTEGER PRIMARY KEY, -- 关联记录的内部行号，不占 projects.max_id
    source_kind         TEXT NOT NULL,       -- layer / object
    source_project_id   INTEGER NOT NULL,
    source_id           INTEGER NOT NULL,
    target_kind         TEXT NOT NULL,       -- layer / object
    target_project_id   INTEGER NOT NULL,
    target_id           INTEGER NOT NULL,
    tips                TEXT NOT NULL DEFAULT ''
);

-- 改动日志由 CRUD 与目标记录在同一事务中写入，不引用实体外键。
-- 一次分流调用（或整个批次）共用一个由入口生成的 UUID operation_id。
CREATE TABLE IF NOT EXISTS changes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id    TEXT NOT NULL,
    created_at      TEXT NOT NULL,  -- UTC ISO 8601
    kind            TEXT NOT NULL,  -- 被修改记录的种类
    project_id      INTEGER,        -- 日志查询用的项目上下文，不是目标主键的一部分
    target_id       INTEGER NOT NULL,
    action          TEXT NOT NULL,
    before_data     TEXT,           -- JSON；创建时为 NULL
    after_data      TEXT            -- JSON；删除时为 NULL
);

CREATE INDEX IF NOT EXISTS layers_by_father
    ON layers (project_id, father, id);

CREATE INDEX IF NOT EXISTS objects_by_layer_time
    ON objects (project_id, layer, "begin", "end", id);

CREATE INDEX IF NOT EXISTS binds_by_source
    ON binds (source_project_id, source_kind, source_id);

CREATE INDEX IF NOT EXISTS binds_by_target
    ON binds (target_project_id, target_kind, target_id);

CREATE INDEX IF NOT EXISTS changes_by_operation
    ON changes (operation_id, id);

CREATE INDEX IF NOT EXISTS changes_by_target
    ON changes (kind, project_id, target_id, id);

COMMIT;

-- layers.objects 由 objects.layer 反查并装载；两类的 bind 由 binds 反查。
-- 本结构只提供主外键和存储列，不执行时间、轴、环、资源或封装约束检查。
-- 没有级联删除/更新，也没有自动发号或维护 max_id 的触发器。
