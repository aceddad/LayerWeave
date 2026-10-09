"""默认工具包的实例保存：复用基础支撑，按需接入已安装的检测提供者。"""
from support.configuration.loader import DEFAULT_ROOT
from support.providers import DEFAULT_CHECKER, optional_checker
from support.storage import save


def save_layer(connection, project_id, layer, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    return save.save_layer(connection, project_id, layer, config_root=config_root,
                           checker=optional_checker(checker, config_root=config_root))


def save_object(connection, project_id, obj, *, config_root=DEFAULT_ROOT, checker=DEFAULT_CHECKER):
    return save.save_object(connection, project_id, obj, config_root=config_root,
                            checker=optional_checker(checker, config_root=config_root))
