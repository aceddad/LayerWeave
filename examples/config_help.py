"""python -X utf8 -B examples/config_help.py：查看文字层与其对象类的联合说明。"""

from layerweave.tool.builtin.shared.help.config_help import config_help, format_help


def create_example():
    # 所有调用只读配置，不需要初始化数据库、创建项目或导入封装类。
    return {
        "overview": config_help(),
        "layers": config_help("layers", ["text", "image"]),
        "objects": config_help("objects", ["Text", "Title", "objects/model.toml"]),
        "combined": config_help("combined", ["TextLayer"]),
        "developer": config_help("objects", ["model", "Title"], audience="developer"),
    }


if __name__ == "__main__":
    print(format_help(create_example()["combined"]))
