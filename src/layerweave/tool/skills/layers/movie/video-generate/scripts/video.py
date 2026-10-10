"""MiniMax 视频生成 V2 接口（官方或转发站）：首尾帧补中间、首帧生成、文生视频、参考图／参考视频生成。

连接：--base-url 或环境变量 MINIMAX_BASE_URL（必须提供，写到 .../v2 这一级）；
      KEY 从 --key-env 指定的环境变量读取，默认 MINIMAX_API_KEY。不打印、不写文件。

python scripts/video.py ping                                   # 用不存在的任务号探测连接，明确的“任务不存在”是预期响应
python scripts/video.py submit 输出.mp4 提示词.txt --first 首帧.png --last 尾帧.png [--duration 4] [--resolution 768P] [--model MiniMax-H3]
python scripts/video.py submit 输出.mp4 提示词.txt --ref-image 角色.png [--ref-video 动作.mp4] [--ratio 16:9]
python scripts/video.py wait <task_id> 输出.mp4                # 已提交的任务：继续等待并下载
"""
import argparse
import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_KEY_ENV = "MINIMAX_API_KEY"


class Connection:
    def __init__(self, base_url, key_env):
        self.base_url = (base_url or os.environ.get("MINIMAX_BASE_URL") or "").rstrip("/")
        if not self.base_url:
            sys.exit("缺少接口地址：用 --base-url 指定，或设置环境变量 MINIMAX_BASE_URL（写到 .../v2 这一级）")
        self.key_env = key_env

    def key(self):
        value = os.environ.get(self.key_env)
        if not value:
            sys.exit(f"未找到环境变量 {self.key_env}：请把 KEY 放进这个变量，或用 --key-env 指定别的变量名")
        return value

    def call(self, method, path, body=None, timeout=120):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.key(), "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raw = error.read()
            try:
                return error.code, json.loads(raw)
            except ValueError:
                return error.code, {"raw": raw[:300].decode("utf-8", "replace")}


def image_data_url(path):
    """图片转成 JPEG data URL，减小请求体。需要 Pillow。"""
    try:
        from PIL import Image
    except ImportError:
        sys.exit("传图片需要 Pillow：pip install Pillow")
    image = Image.open(path).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=93)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def require_success(status, result, action):
    if not 200 <= status < 300 or result.get("type") == "error":
        sys.exit(f"{action}失败：HTTP {status} {json.dumps(result, ensure_ascii=False)[:300]}")


def task_not_found(result):
    error = result.get("error") or result.get("base_resp") or result
    if isinstance(error, dict):
        message = next((str(error[name]) for name in ("message", "status_msg", "msg", "raw") if error.get(name)), "")
    else:
        message = str(error)
    message = message.lower()
    return "任务不存在" in message or ("task" in message and any(
        phrase in message for phrase in ("not found", "does not exist", "not exist", "no such task")))


def wait(connection, task_id, output, every=10, limit=1800):
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    started = time.time()
    failures = 0
    while time.time() - started < limit:
        failure = None
        try:
            status, result = connection.call("GET", "/query/video_generation/" + task_id)
        except (urllib.error.URLError, OSError) as error:
            failure = f"{type(error).__name__}: {str(error)[:300]}"
        else:
            if 500 <= status < 600:
                failure = f"HTTP {status} {json.dumps(result, ensure_ascii=False)[:300]}"
            else:
                require_success(status, result, f"查询任务 {task_id}")
        if failure is not None:
            failures += 1
            if failures >= 4:
                sys.exit(f"查询任务 {task_id} 连续 4 次失败：{failure}；"
                         f'稍后可用 wait {task_id} "{output}" 继续，不要重新 submit。')
            print(f"查询任务 {task_id} 暂时失败（{failures}/4）：{failure}；{every} 秒后重试", file=sys.stderr, flush=True)
            time.sleep(every)
            continue
        failures = 0
        task = result.get("task", result)
        state = str(task.get("status", "")).lower()
        print(f"[{time.time() - started:4.0f}s] HTTP {status} {state}", file=sys.stderr, flush=True)
        if state in ("succeeded", "success", "completed"):
            url = (task.get("content") or {}).get("url")
            with urllib.request.urlopen(url, timeout=600) as response:
                video = response.read()
            with open(output, "wb") as handle:
                handle.write(video)
            meta = {name: task.get(name) for name in ("id", "model", "resolution", "duration", "ratio", "usage")}
            with open(output + ".json", "w", encoding="utf-8") as handle:
                json.dump(meta, handle, ensure_ascii=False, indent=1)
            print(json.dumps({"output": output, **meta}, ensure_ascii=False))
            return
        if state in ("failed", "failure", "cancelled"):
            sys.exit(f"任务 {state}：{json.dumps(task.get('error'), ensure_ascii=False)[:300]}")
        time.sleep(every)
    sys.exit(f"等待超时；稍后可用 wait {task_id} {output} 继续")


def main():
    parser = argparse.ArgumentParser(description="MiniMax 视频生成 V2（官方或转发站）")
    parser.add_argument("--base-url", default=None, help="接口地址，写到 .../v2 这一级；省略时读 MINIMAX_BASE_URL")
    parser.add_argument("--key-env", default=DEFAULT_KEY_ENV, help=f"存放 KEY 的环境变量名，默认 {DEFAULT_KEY_ENV}")
    commands = parser.add_subparsers(dest="command", required=True)
    submit = commands.add_parser("submit", help="提交生成并等待下载")
    submit.add_argument("output", help="由调用 AI 指定的输出文件路径，包含目录和文件名")
    submit.add_argument("prompt_file", help="提示词文本文件（UTF-8）")
    submit.add_argument("--first", help="首帧图片")
    submit.add_argument("--last", help="尾帧图片")
    submit.add_argument("--ref-image", nargs="*", default=[], help="参考图（不能和首尾帧同时用）")
    submit.add_argument("--ref-video", help="参考视频（不能和首尾帧同时用）")
    submit.add_argument("--duration", type=int, default=4, help="秒数")
    submit.add_argument("--resolution", default="768P")
    submit.add_argument("--model", default="MiniMax-H3")
    submit.add_argument("--ratio", default="16:9", help="文生和参考生成时的画面比例；首尾帧模式由图片决定")
    waiting = commands.add_parser("wait", help="继续等待已提交的任务并下载")
    waiting.add_argument("task_id")
    waiting.add_argument("output", help="由调用 AI 指定的下载文件路径，可以与提交时不同")
    commands.add_parser("ping", help="探测连接，不生成；400/404 且明确任务不存在视为正常")
    args = parser.parse_args()
    connection = Connection(args.base_url, args.key_env)

    if args.command == "ping":
        status, result = connection.call("GET", "/query/video_generation/000000000000000")
        if status in (401, 403):
            require_success(status, result, "连接探测鉴权")
        if status in (400, 404) and task_not_found(result):
            print(f"连接正常：HTTP {status}，任务不存在是本次探测的预期响应；{json.dumps(result, ensure_ascii=False)[:300]}")
            return
        require_success(status, result, "连接探测")
        print("连接正常：HTTP", status, json.dumps(result, ensure_ascii=False)[:300])
        return
    if args.command == "wait":
        wait(connection, args.task_id, args.output)
        return

    if (args.ref_image or args.ref_video) and (args.first or args.last):
        sys.exit("参考图／参考视频不能和首尾帧同时用")
    with open(args.prompt_file, encoding="utf-8-sig") as handle:
        content = [{"type": "text", "text": handle.read().strip()}]
    if args.first:
        content.append({"type": "image_url", "role": "first_frame", "image_url": {"url": image_data_url(args.first)}})
    if args.last:
        content.append({"type": "image_url", "role": "last_frame", "image_url": {"url": image_data_url(args.last)}})
    for path in args.ref_image:
        content.append({"type": "image_url", "role": "reference_image", "image_url": {"url": image_data_url(path)}})
    if args.ref_video:
        with open(args.ref_video, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode()
        content.append({"type": "video_url", "role": "reference_video", "video_url": {"url": "data:video/mp4;base64," + encoded}})
    body = {"model": args.model, "content": content, "resolution": args.resolution, "duration": args.duration}
    if not (args.first or args.last):
        body["ratio"] = args.ratio
    # 目录由调用方选择；在可能产生费用的提交前准备，不设置固定的项目输出位置。
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    status, result = connection.call("POST", "/video_generation", body, timeout=300)
    require_success(status, result, "提交")
    task_id = result.get("task_id") or (result.get("task") or {}).get("id")
    if not task_id:
        sys.exit(f"提交失败：HTTP {status} {json.dumps(result, ensure_ascii=False)[:300]}")
    print(f"已提交：task_id {task_id}", file=sys.stderr, flush=True)
    try:
        with open(args.output + ".task", "w", encoding="utf-8") as handle:
            handle.write(str(task_id))  # 中断后可用 wait 接着等
    except OSError as error:
        sys.exit(f"任务 {task_id} 已提交，但任务号文件保存失败：{error}。"
                 f'请用 wait {task_id} "{args.output}" 继续，不要重新 submit。')
    wait(connection, str(task_id), args.output)


if __name__ == "__main__":
    main()
