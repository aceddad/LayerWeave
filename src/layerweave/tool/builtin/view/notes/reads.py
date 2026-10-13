"""批注的已读：每个人各记各的，存在视图自己的表 view_note 里（不写进批注本身）。
一楼一行，身份就是楼主批注的（项目，编号），不另外发号；reads 是 {名字: 读到的最后一条批注编号}。
"已读"和"已处理"是两回事：已处理是这件事办完了，整楼共用；已读只是"我看过了，别再提醒我"。
楼里后来又有人写了新的一条（编号比记下的大），对这个人就又算没读。"""
import json

from layerweave.support.api import read_record, table_specs

READ_KIND = "view_note"
READ_TABLE = {READ_KIND: {
    "id_source": "provided",
    "fields": {"reads": {"type": "TEXT", "nullable": False, "default": "{}"}},
}}


def parse_reads(value):
    try:
        data = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return {}
    return {str(name): int(last) for name, last in data.items() if isinstance(last, (int, float))} if isinstance(data, dict) else {}


def read_reads(connection, project_id):
    """{楼主编号: {名字: 读到的最后一条编号}}。从没标过已读的库里还没有这张表，返回空的；只读连接也能用。"""
    if READ_KIND not in table_specs(connection):
        return {}
    return {row["id"]: reads for row in read_record(connection, READ_KIND, project_id=project_id)
            if (reads := parse_reads(row["reads"]))}
