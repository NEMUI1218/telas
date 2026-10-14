"""每个用户自己的数据目录。

配置（含账号密码）和登录会话都存在这里，不放在程序旁边：
程序要发给别人用，放在 exe 旁边的话，连同文件夹一起发出去就把自己的账号带给了别人。

不依赖 Qt，services/ 也可以用。
"""
import os
import sys

APP_DIR_NAME = "BlackboardTool"


def data_dir():
    """每个系统的惯例位置。设了环境变量 BB_DATA_DIR 就用它（测试用）。

    Windows: %APPDATA%\\BlackboardTool
    macOS:   ~/Library/Application Support/BlackboardTool
    Linux:   $XDG_CONFIG_HOME/BlackboardTool（默认 ~/.config/BlackboardTool）
    """
    base = os.environ.get("BB_DATA_DIR")
    if not base:
        home = os.path.expanduser("~")
        if sys.platform == "win32":
            root = os.environ.get("APPDATA") or home
        elif sys.platform == "darwin":
            root = os.path.join(home, "Library", "Application Support")
        else:
            root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
        base = os.path.join(root, APP_DIR_NAME)
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        pass
    return base


def data_path(name):
    return os.path.join(data_dir(), name)
