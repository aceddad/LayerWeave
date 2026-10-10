"""视图服务：本机网页，只读查看项目——画布上每个根一块时间轴画板，另有素材预览。只监听 127.0.0.1，以只读方式打开数据库。

python -m layerweave.tool.builtin.view.server DATABASE [--port 8765] [--project ID]
然后用浏览器打开打印出来的地址。数据库被工具修改后，页面会在两秒内自动刷新。
"""
import argparse
from contextlib import closing
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, urlparse

from .data import extract_frame, find_ffmpeg, list_projects, media_path, open_readonly, project_roots, project_view
from .layout import layout_serial, load_layout, reconcile, save_layout
from .state import read_state, write_state

WEB_ROOT = Path(__file__).with_name("web")
FRAMES = {}   # 抽出来的视频帧缓存：(文件, 修改时间, 秒) → JPEG
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("video/mp4", ".mp4")


class ViewHandler(SimpleHTTPRequestHandler):
    """静态网页 + 只读 JSON 接口 + 素材文件（支持 Range，视频可以拖动）。"""

    def __init__(self, *args, database, version, state_root, record_state, **kwargs):
        self.database, self.version, self.state_root, self.record_state = database, version, state_root, record_state
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass   # 浏览器主动断开：换页、拖动视频、截图结束时都会有

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path == "/api/projects":
                with closing(open_readonly(self.database)) as connection:
                    return self.send_json(list_projects(connection))
            if match := re.fullmatch(r"/api/project/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    data = project_view(connection, self.database, int(match[1]))
                return self.send_json(data) if data else self.send_json({"error": "项目不存在"}, HTTPStatus.NOT_FOUND)
            if url.path == "/api/version":
                return self.send_json({"version": self.version(), "layout": layout_serial(self.database, self.state_root)})
            if match := re.fullmatch(r"/api/layout/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    roots = project_roots(connection, int(match[1]))
                return self.send_json({"boards": load_layout(self.database, int(match[1]), roots, self.state_root),
                                       "serial": layout_serial(self.database, self.state_root)})
            if url.path == "/api/state":
                return self.send_json(read_state(self.database, self.state_root))
            if url.path == "/api/capabilities":
                return self.send_json({"frames": find_ffmpeg() is not None})
            if match := re.fullmatch(r"/frame/(\d+)/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    path = media_path(connection, self.database, int(match[1]), int(match[2]))
                if not path:
                    return self.send_json({"error": "没有这个素材"}, HTTPStatus.NOT_FOUND)
                seconds = round(float(parse_qs(url.query).get("t", ["0"])[0]), 2)
                key = (str(path), path.stat().st_mtime_ns, seconds)
                if key not in FRAMES:
                    if len(FRAMES) > 400:
                        FRAMES.clear()
                    FRAMES[key] = extract_frame(path, seconds)
                body = FRAMES[key]
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if match := re.fullmatch(r"/media/(\d+)/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    path = media_path(connection, self.database, int(match[1]), int(match[2]))
                return self.send_file(path) if path else self.send_json({"error": "没有这个素材"}, HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except (ValueError, OSError, RuntimeError) as error:
            return self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
        if url.path == "/":
            self.path = "/index.html" + (("?" + url.query) if url.query else "")
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        layout = re.fullmatch(r"/api/layout/(\d+)", path)
        if path != "/api/state" and not layout:
            return self.send_json({"error": "只支持 /api/state 和 /api/layout/<项目>"}, HTTPStatus.NOT_FOUND)
        length = int(self.headers.get("Content-Length", 0))
        if length > 65536:
            return self.send_json({"error": "内容过大"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json({"error": "不是 JSON"}, HTTPStatus.BAD_REQUEST)
        if not self.record_state:
            return self.send_json({"recorded": False})
        if layout:
            # 网页传来整套画板；按数据库里现有的根校正后再存（单位不同的拼接会被拆开）
            project_id = int(layout[1])
            with closing(open_readonly(self.database)) as connection:
                roots = project_roots(connection, project_id)
            boards = save_layout(self.database, project_id, reconcile(roots, payload.get("boards")), self.state_root)
            return self.send_json({"boards": boards, "serial": layout_serial(self.database, self.state_root)})
        return self.send_json(write_state(self.database, payload, self.state_root))

    def send_file(self, path):
        size = path.stat().st_size
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        start, end = 0, size - 1
        if match := re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "")):
            if match[1]:
                start = int(match[1])
                end = int(match[2]) if match[2] else end
            elif match[2]:
                start = max(0, size - int(match[2]))
            end = min(end, size - 1)
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = handle.read(min(1 << 16, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    return   # 浏览器拖动视频时会主动断开旧请求
                remaining -= len(chunk)


class ViewServer(ThreadingHTTPServer):
    daemon_threads = True

    def server_close(self):
        super().server_close()
        self.watcher.close()   # 关掉监视用的只读连接，数据库文件才能被移动或删除


def make_server(database, *, port=0, state_root=None, record_state=True):
    """建好服务但不启动；port=0 时由系统分配。返回 (server, url)。"""
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(f"数据库不存在：{database}")
    watcher = open_readonly(database, threads=True)
    lock = threading.Lock()

    def version():
        # data_version：别的连接提交后会变；只读，不碰业务表
        with lock:
            return watcher.execute("PRAGMA data_version").fetchone()[0]

    handler = partial(ViewHandler, database=database, version=version, state_root=state_root, record_state=record_state)
    server = ViewServer(("127.0.0.1", port), handler)
    server.watcher = watcher
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


COMMANDS = [{
    "name": "view_server",
    "summary": "在本机启动只读视图网页：画布上的时间轴画板、素材预览，数据库变化后自动刷新",
    "entrypoint": "layerweave.tool.builtin.view.server:serve",
    "cli": "python -m layerweave.tool.builtin.view.server",
    "read_only": True,
    "context": ["database"],
    "parameters": {
        "port": {"type": "integer", "description": "端口；省略时用 8765，0 表示由系统分配", "default": 8765},
        "project": {"type": "integer", "description": "打开后直接显示的项目编号"},
    },
    "returns": "持续运行的本机网页服务；打印访问地址。",
    "examples": [{"cli": "python -m layerweave.tool.builtin.view.server DATABASE --project 1"}],
    "notes": ["只监听 127.0.0.1，以只读方式打开数据库；素材只提供数据库里引用过、且存在的本地文件。",
              "相对路径的素材相对于数据库文件所在目录解析。"],
}]


def serve(database, *, port=8765, project=None):
    """启动视图服务并一直运行，直到 Ctrl+C。"""
    server, url = make_server(database, port=port)
    if project is not None:
        url += f"?project={project}"
    print(f"视图已启动：{url}  （Ctrl+C 结束）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(description="LayerWeave 只读视图", formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=help_examples(COMMANDS))
    parser.add_argument("database", type=Path, help="已有的 SQLite 数据库")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project", type=int, help="打开后直接显示的项目")
    args = parser.parse_args()
    serve(args.database, port=args.port, project=args.project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
