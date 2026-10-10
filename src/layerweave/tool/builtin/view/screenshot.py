"""给 AI 用的视图截图：在后台起一个只读视图服务，用无界面浏览器打开同一个页面，存成 PNG。
AI 看到的就是用户在视图里看到的。截图用的页面不记录"正在看哪儿"，不会覆盖用户的状态。

python -m layerweave.tool.builtin.view.screenshot DATABASE PROJECT_ID 输出.png
       [--view timeline|assets] [--begin 秒 --end 秒] [--layers 1 5] [--playhead 秒] [--select 对象编号]
       [--width 1600 --height 900] [--browser 浏览器路径] [--wait-ms 4000]
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlencode

from .server import make_server

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser(explicit=None):
    """依次找：--browser、环境变量 LAYERWEAVE_BROWSER、REMOTION_BROWSER_EXECUTABLE、常见安装位置、PATH。"""
    for value in (explicit, os.environ.get("LAYERWEAVE_BROWSER"), os.environ.get("REMOTION_BROWSER_EXECUTABLE")):
        if value and Path(value).is_file():
            return value
    for value in CANDIDATES:
        if Path(value).is_file():
            return value
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        if found := shutil.which(name):
            return found
    return None


def capture(database, project_id, output, *, view="timeline", begin=None, end=None, layers=None, playhead=None,
            select=None, width=1600, height=900, browser=None, wait_ms=4000):
    browser = find_browser(browser)
    if browser is None:
        raise FileNotFoundError("找不到 Chrome、Edge 或 Chromium：用 --browser 或环境变量 LAYERWEAVE_BROWSER 指定浏览器路径")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    server, url = make_server(database, record_state=False)
    query = {"project": project_id, "view": view, "record": 0, "capture": 1}
    for key, value in (("begin", begin), ("end", end), ("playhead", playhead), ("select", select)):
        if value is not None:
            query[key] = value
    if layers:
        query["layers"] = ",".join(str(i) for i in layers)
    page = url + "?" + urlencode(query)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if output.exists():
        output.unlink()   # 旧图会让"等截图出现"误判成功；这是调用方指定的输出文件
    try:
        # 独立的浏览器配置，不碰用户正在用的浏览器；Edge 的启动器会先返回，截图稍后才写出，所以要等文件出现
        with tempfile.TemporaryDirectory(prefix="layerweave-shot-", ignore_cleanup_errors=True) as profile:
            command = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                       "--no-first-run", "--no-default-browser-check", f"--user-data-dir={profile}",
                       f"--window-size={width},{height}", f"--virtual-time-budget={wait_ms}",
                       f"--screenshot={output}", page]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            deadline = time.time() + wait_ms / 1000 + 30
            last = -1
            while time.time() < deadline:
                size = output.stat().st_size if output.is_file() else -1
                if size > 0 and size == last:
                    break
                last = size
                time.sleep(0.5)
    finally:
        server.shutdown()
        server.server_close()
    if not output.is_file():
        raise RuntimeError(f"浏览器没有生成截图（退出码 {result.returncode}）：{(result.stderr or '')[-300:]}")
    return {"output": str(output), "page": page, "browser": browser, "size": [width, height]}


COMMANDS = [{
    "name": "view_screenshot",
    "summary": "把视图页面截成 PNG：时间轴或素材网格，可指定时间范围、层、播放头、选中对象",
    "entrypoint": "layerweave.tool.builtin.view.screenshot:capture",
    "cli": "python -m layerweave.tool.builtin.view.screenshot",
    "read_only": True,
    "context": ["database", "project_id"],
    "parameters": {
        "output": {"type": "string", "required": True, "description": "由 AI 指定的 PNG 输出路径"},
        "view": {"type": "string", "description": "timeline 或 assets", "default": "timeline"},
        "begin": {"type": "number", "description": "时间轴显示的起点"},
        "end": {"type": "number", "description": "时间轴显示的终点"},
        "layers": {"type": "array", "description": "只显示这些层"},
        "playhead": {"type": "number", "description": "播放头位置；右侧会列出这一刻每层的内容"},
        "select": {"type": "integer", "description": "选中并展开详情的对象编号"},
        "width": {"type": "integer", "default": 1600}, "height": {"type": "integer", "default": 900},
        "browser": {"type": "string", "description": "浏览器路径；省略时自动查找 Chrome、Edge、Chromium"},
        "wait_ms": {"type": "integer", "description": "给页面加载图片、视频封面、波形的时间", "default": 4000},
    },
    "returns": "output、page（截图用的页面地址）、browser、size。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.screenshot DATABASE 1 shots/t10.png --begin 8 --end 14 --playhead 10"}],
    "notes": ["截图页面不记录状态；用户正在看哪儿请用 view_state。", "只读：起一个只监听本机的临时服务，截完就关。"],
}]


def main():
    from layerweave.support.commands import help_examples
    p = argparse.ArgumentParser(description="视图截图（给 AI 看）", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=help_examples(COMMANDS))
    p.add_argument("database", type=Path); p.add_argument("project_id", type=int); p.add_argument("output", type=Path)
    p.add_argument("--view", choices=("timeline", "assets"), default="timeline")
    p.add_argument("--begin", type=float); p.add_argument("--end", type=float)
    p.add_argument("--layers", type=int, nargs="+"); p.add_argument("--playhead", type=float); p.add_argument("--select", type=int)
    p.add_argument("--width", type=int, default=1600); p.add_argument("--height", type=int, default=900)
    p.add_argument("--browser"); p.add_argument("--wait-ms", type=int, default=4000)
    a = p.parse_args()
    try:
        result = capture(a.database, a.project_id, a.output, view=a.view, begin=a.begin, end=a.end, layers=a.layers,
                         playhead=a.playhead, select=a.select, width=a.width, height=a.height, browser=a.browser, wait_ms=a.wait_ms)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"截图失败：{error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
