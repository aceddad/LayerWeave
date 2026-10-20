"""本机视图服务：读取项目，并通过工具入口管理批注、折叠、已读和共享布局。
只监听 127.0.0.1；普通查询使用只读连接，写入通过现有工具的写会话。

python -X utf8 -m layerweave.tool.builtin.view.server DATABASE [--port 8765] [--project ID]
用浏览器打开打印的地址，页面每两秒轮询项目变化。
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
import sqlite3
import threading
from urllib.parse import parse_qs, quote, unquote, urlparse

from .i18n import ViewError, error_payload
from .data import extract_frame, find_ffmpeg, list_projects, media_path, open_readonly, project_roots, project_view, recent_changes, thumbnail, waveform
from .layout import layout_serial, load_layout, reconcile, save_layout
from .fold import set_folds
from .at import read_spans
from .plugins import list_plugins, list_serial, plugin as plugin_action, plugin_file
from .walk import walk_from
from .note import add_note, remove_note, retarget_note, set_read, update_note
from .state import read_state, write_state
from .incremental import project_snapshot, project_delta

WEB_ROOT = Path(__file__).with_name("web")
FRAMES = {}   # 抽出来的视频帧缓存：(文件, 修改时间, 秒) → JPEG
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("video/mp4", ".mp4")


class ViewHandler(SimpleHTTPRequestHandler):
    """静态网页、项目查询、视图状态写入及引用的媒体文件。"""

    def __init__(self, *args, database, version, state_root, record_state, web_root=None, **kwargs):
        self.database, self.version, self.state_root, self.record_state = database, version, state_root, record_state
        super().__init__(*args, directory=str(web_root or WEB_ROOT), **kwargs)

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
                return self.send_json(data) if data else self.send_json(error_payload(ViewError("error.projectMissing")), HTTPStatus.NOT_FOUND)
            if match := re.fullmatch(r"/api/project/(\d+)/(snapshot|delta)", url.path):
                q = parse_qs(url.query)
                with closing(open_readonly(self.database)) as connection:
                    if match[2] == "snapshot":
                        data = project_snapshot(connection, self.database, int(match[1]))
                    else:
                        data = project_delta(connection, self.database, int(match[1]), after=int(q.get("after", ["0"])[0]),
                                             limit=max(1, min(1000, int(q.get("limit", ["100"])[0]))))
                return self.send_json(data)
            if url.path == "/api/version":
                return self.send_json({"version": self.version(), "layout": layout_serial(self.database, self.state_root),
                                       "plugins": list_serial(self.state_root)})
            if match := re.fullmatch(r"/api/changes/(\d+)", url.path):
                limit = max(1, min(100, int(parse_qs(url.query).get("limit", ["10"])[0])))
                with closing(open_readonly(self.database)) as connection:
                    return self.send_json(recent_changes(connection, int(match[1]), limit))
            if match := re.fullmatch(r"/api/at/(\d+)", url.path):
                # 按时刻读（at.py）：span=根:起点:终点，可以给几个；"此刻"面板的"复制文字版"用
                spans = [tuple(float(x) if i else int(x) for i, x in enumerate(item.split(":"))) for item in parse_qs(url.query).get("span", [])]
                if not spans or any(len(s) != 3 for s in spans):
                    return self.send_json(error_payload(ViewError("error.span")), HTTPStatus.BAD_REQUEST)
                with closing(open_readonly(self.database)) as connection:
                    return self.send_json(read_spans(connection, int(match[1]), spans, lang=parse_qs(url.query).get("lang", ["zh"])[0]))
            if match := re.fullmatch(r"/api/walk/(\d+)", url.path):
                # 沿读（walk.py）：侧栏「沿读」按步列出
                q = parse_qs(url.query)
                with closing(open_readonly(self.database)) as connection:
                    return self.send_json(walk_from(connection, int(match[1]), q.get("from", [""])[0],
                                                    direction=q.get("direction", ["both"])[0], depth=int(q.get("depth", ["3"])[0]),
                                                    max_nodes=int(q.get("max", ["60"])[0])))
            if match := re.fullmatch(r"/api/layout/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    roots = project_roots(connection, int(match[1]))
                return self.send_json({"boards": load_layout(self.database, int(match[1]), roots, self.state_root),
                                       "serial": layout_serial(self.database, self.state_root)})
            if url.path == "/api/state":
                return self.send_json(read_state(self.database, self.state_root))
            if url.path == "/api/plugins":
                # 修订号进入路径，相对导入的子模块也随版本换 URL。
                result = list_plugins(self.state_root, languages=True)
                for p in result["plugins"]:
                    if p["on"] and not p["problem"]:
                        p["url"] = f"/plugins/{p['id']}/{p['revision']}/{quote(p['entry'])}"
                return self.send_json(result)
            if match := re.fullmatch(r"/plugins/([a-z][a-z0-9_-]*\.[a-z][a-z0-9_-]*)/([a-f0-9]+)/(.+)", url.path):
                # 插件的入口和它旁边的文件（拆出去的代码、图片、样式），只限这个文件夹里的网页文件
                path = plugin_file(match[1], unquote(match[3]), self.state_root, revision=match[2])
                return self.send_file(path) if path else self.send_json(error_payload(ViewError("error.pluginFile")), HTTPStatus.NOT_FOUND)
            if url.path == "/api/capabilities":
                return self.send_json({"frames": find_ffmpeg() is not None})
            if match := re.fullmatch(r"/frame/(\d+)/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    path = media_path(connection, self.database, int(match[1]), int(match[2]))
                if not path:
                    return self.send_json(error_payload(ViewError("error.file")), HTTPStatus.NOT_FOUND)
                at = parse_qs(url.query).get("t", ["0"])[0]
                seconds = "end" if at == "end" else round(float(at), 2)   # end：最后一帧
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
            if match := re.fullmatch(r"/wave/(\d+)/(\d+)", url.path):
                # 音频波形：服务端算好的 800 段能量；算不了时 404，页面退回自己解码
                with closing(open_readonly(self.database)) as connection:
                    path = media_path(connection, self.database, int(match[1]), int(match[2]))
                values = waveform(path, self.state_root) if path else None
                if values is None:
                    return self.send_json(error_payload(ViewError("error.waveform")), HTTPStatus.NOT_FOUND)
                return self.send_json({"rms": values})
            if match := re.fullmatch(r"/thumb/(\d+)/(\d+)", url.path):
                # 图片缩略图：画布、一览页、接缝页用它；缩不了（没有 ffmpeg、svg、gif、解不开）就送原图
                with closing(open_readonly(self.database)) as connection:
                    path = media_path(connection, self.database, int(match[1]), int(match[2]))
                if not path:
                    return self.send_json(error_payload(ViewError("error.file")), HTTPStatus.NOT_FOUND)
                made = thumbnail(path, int(parse_qs(url.query).get("w", ["320"])[0]), self.state_root)
                if made is None:
                    return self.send_file(path)
                body, kind = made
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            if match := re.fullmatch(r"/media/(\d+)/(\d+)", url.path):
                with closing(open_readonly(self.database)) as connection:
                    path = media_path(connection, self.database, int(match[1]), int(match[2]))
                return self.send_file(path) if path else self.send_json(error_payload(ViewError("error.file")), HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except (ValueError, OSError, RuntimeError) as error:
            return self.send_json(error_payload(error), HTTPStatus.BAD_REQUEST)
        if url.path == "/":
            self.path = "/index.html" + (("?" + url.query) if url.query else "")
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/(layout|notes|folds)/(\d+)", path)
        if match:
            kind, project_id = match[1], int(match[2])
        elif path in ("/api/state", "/api/plugins"):
            kind, project_id = path.rsplit("/", 1)[1], None
        else:
            return self.send_json(error_payload(ViewError("error.route")), HTTPStatus.NOT_FOUND)

        # 所有 POST 共用本机来源规则；无 Origin 的 CLI/本机程序仍可调用，允许本地 Vite 开发。
        if origin := self.headers.get("Origin"):
            try:
                parsed = urlparse(origin)
                local = parsed.scheme in ("http", "https") and parsed.hostname in ("127.0.0.1", "localhost", "::1")
            except ValueError:
                local = False
            if not local:
                return self.send_json(error_payload(ViewError("error.origin")), HTTPStatus.FORBIDDEN)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length < 0:
                raise ValueError()
        except ValueError:
            return self.send_json(error_payload(ViewError("error.length")), HTTPStatus.BAD_REQUEST)
        if length > 65536:
            return self.send_json(error_payload(ViewError("error.tooLarge")), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self.send_json(error_payload(ViewError("error.json")), HTTPStatus.BAD_REQUEST)
        if not isinstance(payload, dict):
            return self.send_json(error_payload(ViewError("error.requestObject")), HTTPStatus.BAD_REQUEST)
        if not self.record_state:
            return self.send_json({"recorded": False})
        try:
            result = self._apply_post(kind, project_id, payload)
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as error:
            return self.send_json(error_payload(error), HTTPStatus.BAD_REQUEST)
        return self.send_json(result)

    def _apply_post(self, kind, project_id, payload):
        """HTTP 只负责请求与反馈转换，实际写入继续复用各工具入口。"""
        if kind == "notes":
            return self.write_note(project_id, payload)
        if kind == "plugins":
            return plugin_action(payload.get("action"), payload.get("target"), name=payload.get("name") or None,
                                 root=self.state_root, catalog=payload.get("catalog") or None,
                                 version=payload.get("version") or None, file=payload.get("file") or None,
                                 files=payload.get("files") is True)
        if kind == "folds":
            action, side = payload.get("action"), payload.get("side", "user")
            if side == "ai" and action != "unfold":
                raise ViewError("error.aiFold")
            layers = [int(layer) for layer in payload.get("layers", [])]
            return set_folds(self.database, project_id, layers, side, action,
                             by=payload.get("by") or "", tips=payload.get("tips"))
        if kind == "layout":
            with closing(open_readonly(self.database)) as connection:
                roots = project_roots(connection, project_id)
            result = save_layout(self.database, project_id, reconcile(roots, payload.get("boards")), self.state_root, with_result=True)
            return {**result, "serial": layout_serial(self.database, self.state_root)}
        return write_state(self.database, payload, self.state_root)

    def write_note(self, project_id, payload):
        """将网页请求交给批注工具；错误统一由 POST 边界转换为 JSON。"""
        action = payload.get("action")
        if action in ("add", "retarget"):
            raw_targets = payload.get("targets", [])
            if not isinstance(raw_targets, list) or not all(isinstance(t, dict) for t in raw_targets):
                raise ViewError("error.targets")
            targets = [(t["kind"], int(t.get("project", project_id)), int(t["id"])) for t in raw_targets
                       if t.get("kind") in ("object", "layer")]
            span = payload.get("span")
            if span is not None and not isinstance(span, dict):
                raise ViewError("error.spanObject")
            span = (span["begin"], span["end"]) if span is not None else None
            if action == "add":
                return add_note(self.database, project_id, payload.get("text", ""), targets=targets,
                                span=span, author=payload.get("author") or None)
            return retarget_note(self.database, project_id, int(payload["note"]), targets, span=span)
        if action in ("done", "reopen"):
            return update_note(self.database, project_id, int(payload["note"]), status="done" if action == "done" else "open")
        if action == "edit":
            return update_note(self.database, project_id, int(payload["note"]), text=payload.get("text"))
        if action == "remove":
            return remove_note(self.database, project_id, int(payload["note"]))
        if action in ("read", "unread"):
            return set_read(self.database, project_id, int(payload["note"]), payload.get("reader") or "", read=action == "read")
        raise ViewError("error.action", {"action": action})

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


def make_server(database, *, port=0, state_root=None, record_state=True, web_root=None):
    """建好服务但不启动；port=0 时由系统分配。返回 (server, url)。web_root：换一份网页（view_bench 拿来和别的构建对比）。"""
    database = Path(database).resolve()
    if not database.is_file():
        raise FileNotFoundError(f"数据库不存在：{database}")
    watcher = open_readonly(database, threads=True)
    lock = threading.Lock()

    def version():
        # data_version：别的连接提交后会变；只读，不碰业务表
        with lock:
            return watcher.execute("PRAGMA data_version").fetchone()[0]

    handler = partial(ViewHandler, database=database, version=version, state_root=state_root, record_state=record_state,
                      web_root=Path(web_root) if web_root else None)
    server = ViewServer(("127.0.0.1", port), handler)
    server.watcher = watcher
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


COMMANDS = [{'name': 'view_server',
  'summary': '在本机启动视图网页：查看画布与插件页面，并支持批注、折叠和已读状态写入',
  'entrypoint': 'layerweave.tool.builtin.view.server:serve',
  'cli': 'python -X utf8 -m layerweave.tool.builtin.view.server',
  'read_only': False,
  'context': ['database'],
  'returns': '持续运行的本机网页服务；打印访问地址。',
  'examples': [{'cli': 'python -X utf8 -m layerweave.tool.builtin.view.server DATABASE --project 1'}],
  'notes': ['只监听 127.0.0.1；查看项目使用只读连接，批注、折叠和已读状态经工具入口写入；文件只提供数据库引用过且存在的本地文件。', '相对路径的文件相对于数据库文件所在目录解析。'],
  'input_schema': {'type': 'object',
                   'properties': {'database': {'type': 'string', 'description': 'SQLite 数据库路径；Python 连接由适配器提供'},
                                  'port': {'type': 'integer',
                                           'description': '端口；省略时用 8765，0 表示由系统分配',
                                           'default': 8765},
                                  'project': {'type': ['integer', 'null'], 'description': '打开后直接显示的项目编号'}},
                   'additionalProperties': False,
                   'required': ['database']},
  'mcp': {'enabled': False, 'group': 'view', 'reason': '驻留服务或开发性能测量请使用现有 CLI'}}]


def serve(database, *, port=8765, project=None):
    """启动视图服务并一直运行，直到 Ctrl+C。"""
    server, url = make_server(database, port=port)
    if project is not None:
        url += f"?project={project}"
    print(f"视图已启动：{url}  （Ctrl+C 结束）", flush=True)
    from .tables import check_tables   # 只读地查一下视图自己的表是不是旧声明；只提示，不替人升级
    if check_tables(database)["upgrade_needed"]:
        print("提示：这个库里视图的表（折叠、已读）是旧声明。要用 JSON 交换复制项目，先跑一次 "
              "python -X utf8 -m layerweave.tool.builtin.view.tables DATABASE --upgrade（只改声明，不改数据）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    from layerweave.support.commands import help_examples
    parser = argparse.ArgumentParser(description="LayerWeave 本机视图", formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=help_examples(COMMANDS))
    parser.add_argument("database", type=Path, help="已有的 SQLite 数据库")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--project", type=int, help="打开后直接显示的项目")
    args = parser.parse_args()
    serve(args.database, port=args.port, project=args.project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
