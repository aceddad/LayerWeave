"""真实扫描自带组件并登记到临时数据库；不写用户项目数据库。"""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from layerweave.support.api import initialize_database, open_database
from layerweave.tool.builtin.developer.versions import manage_versions


def main():
    with TemporaryDirectory(prefix="layerweave-versions-") as folder:
        database = initialize_database(Path(folder) / "versions.sqlite3")
        with closing(open_database(database)) as connection:
            result = manage_versions(connection)
            assert result["ok"] and result["data"]["status"] == "completed", result
            for row in result["data"]["items"]:
                print(f"{row['name']}  {row['version']}  {row['status']}")
            own = manage_versions(connection, "read", name="layerweave.versions")
            assert own["data"]["items"][0]["status"] == "online", own
            print(f"已登记 {len(result['data']['items'])} 个组件，包含版本工具自身。")


if __name__ == "__main__":
    main()
