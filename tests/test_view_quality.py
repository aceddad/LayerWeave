"""Real-browser image quality regression with generated PNGs and prepared frames.

The temporary MP4 is deliberately only a routing placeholder. These tests exercise
the browser's rendering, source selection and incremental replacement, not FFmpeg
or video codecs. No Pillow, scratch fixtures, personal databases or network assets.
Run serially after building frontend/view:
    python -m unittest discover -s tests -p test_view_quality.py -v
"""
from contextlib import closing, contextmanager
import json
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import urlopen
import zlib

from layerweave.support.api import initialize_database, open_database, transaction
from layerweave.tool.builtin.view import server as view_server
from layerweave.tool.builtin.view.bench import _ev
from layerweave.tool.builtin.view.screenshot import DevTools, QUIET, _devtools_port, find_browser


def striped_png(width, *, source_width=2048, stripe=4, tint="red"):
    """Analytically area-sampled vertical bars, encoded with stdlib PNG/zlib.

    Every size represents the same source signal. Small thumbnails therefore
    genuinely lose fine detail, rather than returning a different test pattern.
    """
    height = width * 9 // 16

    def white_area(x):
        period = stripe * 2
        return math.floor(x / period) * stripe + max(0, x % period - stripe)

    row = bytearray()
    for x in range(width):
        left, right = x * source_width / width, (x + 1) * source_width / width
        amount = (white_area(right) - white_area(left)) / (right - left)
        value = round(20 + 220 * amount)
        row.extend({"red": (value, 16, 16), "blue": (16, 16, value),
                    "gray": (value, value, value), "cyan": (16, value, value)}[tint])
    raw = (b"\0" + bytes(row)) * height

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


@contextmanager
def quality_page(*, long_images=False):
    with tempfile.TemporaryDirectory(prefix="lw-view-quality-", ignore_cleanup_errors=True) as folder:
        root = Path(folder)
        red, blue = root / "red.png", root / "blue.png"
        red.write_bytes(striped_png(2048))
        blue.write_bytes(striped_png(2048, tint="blue"))
        movie = root / "prepared-frames.mp4"
        movie.write_bytes(b"SYNTHETIC FRAME ROUTING PLACEHOLDER; NOT A VIDEO CODEC TEST\n")
        images = {(tint, width): striped_png(width, tint=tint)
                  for tint in ("red", "blue") for width in (160, 320, 640, 1280, 2048)}
        first_frame = striped_png(640, source_width=640, stripe=32, tint="gray")
        last_frame = striped_png(640, source_width=640, stripe=32, tint="cyan")
        requests = []

        def thumbnail(path, width, cache_root=None):
            requests.append((Path(path).name, width))
            size = next((n for n in (160, 320, 640, 1280, 2048) if n >= width), 2048)
            return images[("blue" if Path(path).name == blue.name else "red", size)], "image/png"

        def frame(path, seconds):
            return last_frame if seconds == "end" or float(seconds) > 1 else first_frame

        database = initialize_database(root / "quality.sqlite3")
        with closing(open_database(database)) as connection, transaction(connection) as write:
            project = write.create("project", {"name": "Synthetic quality regression"})["id"]
            board = write.create("layer", {"type": "text", "name": "Quality", "config_ref": "layers/text.toml",
                                          "axis": {"unit": "秒", "precision": .001}}, project_id=project)["id"]
            objects = {}
            definitions = [("image", "image", 2000 if long_images else 6, red), ("short", "movie", 2, movie),
                           ("long", "movie", 2000, movie)]
            if long_images:
                definitions.append(("peer", "image", 2000, red))
            for name, kind, end, source in definitions:
                layer = write.create("layer", {"type": kind, "name": name, "father": board,
                                               "config_ref": f"layers/{kind}.toml"}, project_id=project)["id"]
                objects[name] = write.create("object", {"layer": layer, "begin": 0, "end": end,
                    "config_ref": f"objects/{kind}.toml", "name": name,
                    "information": {"source": str(source)}}, project_id=project)["id"]
        # Only this test's server process observes these replacements. Every
        # response is already prepared; first-time transcoding cost is excluded.
        with patch.object(view_server, "find_ffmpeg", return_value="prepared-test-frames"), \
                patch.object(view_server, "thumbnail", side_effect=thumbnail), \
                patch.object(view_server, "extract_frame", side_effect=frame), \
                patch.dict(view_server.FRAMES, {}, clear=True):
            server, url = view_server.make_server(database, state_root=root / "state", record_state=False)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            profile = root / "browser"
            process = subprocess.Popen([find_browser(), "--headless=new", "--hide-scrollbars", "--mute-audio",
                "--no-first-run", "--no-default-browser-check", *QUIET, f"--user-data-dir={profile}",
                "--remote-debugging-port=0", "--window-size=1536,760", "about:blank"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            tab = control = None
            try:
                port, ws = _devtools_port(profile, time.time() + 30)
                control = DevTools(f"ws://127.0.0.1:{port}{ws}")
                with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10) as response:
                    page = next(p for p in json.loads(response.read()) if p.get("type") == "page")
                tab = DevTools(page["webSocketDebuggerUrl"], timeout=45)
                tab.call("Page.enable")
                tab.call("Emulation.setDeviceMetricsOverride", width=1536, height=760, deviceScaleFactor=1.25, mobile=False)
                tab.call("Page.navigate", url=url + f"?project={project}&record=0&tree=0&board={board}&begin=0&end=10")
                yield {"tab": tab, "database": database, "project": project, "objects": objects,
                       "replacement": blue, "requests": requests}
            finally:
                if control:
                    try:
                        control.call("Browser.close")
                    except (RuntimeError, OSError):
                        pass
                    control.close()
                if tab:
                    tab.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                server.shutdown()
                server.server_close()


def samples_expression(object_id, *, edge=None):
    """Read the final displayed media surfaces, not the source image or request."""
    return """(() => {
      const o=document.querySelector('.obj[data-id="%s"]');if(!o)return null;
      const r=o.getBoundingClientRect(),track=o.closest('.track');
      const zoom=new DOMMatrixReadOnly(getComputedStyle(document.querySelector('.react-flow__viewport')).transform).a;
      const edge=%s, span=edge?Math.min(64*zoom,(r.width-2*zoom)/2):r.width-2*zoom;
      const left=edge==='last'?r.right-zoom-span:r.left+zoom,y=r.top+r.height*.55;
      const cs=[...track.querySelectorAll('.media-tile,canvas')],samples=[];
      for(let i=0;i<128;i++){
        const x=left+span*(.04+.92*i/127);let pixel=null;
        for(const c of cs){
          const q=c.getBoundingClientRect();
          if(q.width>0&&q.height>0&&x>=q.left&&x<q.right&&y>=q.top&&y<q.bottom){
            const p=[...c.getContext('2d').getImageData(Math.min(c.width-1,Math.max(0,Math.floor((x-q.left)*c.width/q.width))),
              Math.min(c.height-1,Math.max(0,Math.floor((y-q.top)*c.height/q.height))),1,1).data];
            if(p[3]>0)pixel=p;
          }
        }samples.push(pixel);
      }
      return {samples,rect:{width:r.width,height:r.height},zoom,dpr:devicePixelRatio,state:o.dataset.mediaState,
        canvases:cs.map(c=>{const q=c.getBoundingClientRect();return {width:c.width,height:c.height,displayWidth:q.width,displayHeight:q.height};})};
    })()""" % (object_id, json.dumps(edge))


def channel_summary(sample, channel):
    values = [pixel[channel] for pixel in sample["samples"] if pixel is not None]
    if not values:
        return {"contrast": 0, "transitions": 0, "mean": 0}
    middle = (min(values) + max(values)) / 2
    sides = [value > middle for value in values]
    return {"contrast": max(values) - min(values),
            "transitions": sum(a != b for a, b in zip(sides, sides[1:])),
            "mean": sum(values) / len(values)}


def native_expression(ids):
    """Inspect and sample the actual native fallback image, after it was mounted."""
    return """(() => {
      const ids=%s,images=[],rows=[];
      for(const id of ids){
        const o=document.querySelector('.obj[data-id="'+id+'"]');
        const wrappers=[...document.querySelectorAll('.media-native[data-object-id="'+id+'"]')];
        const wrapper=wrappers[0],img=wrapper?.querySelector('img');
        if(!o||wrappers.length!==1||!img||!img.complete||!img.naturalWidth)return null;
        const rect=img.getBoundingClientRect(),objectRect=o.getBoundingClientRect();
        const c=document.createElement('canvas');c.width=128;c.height=8;
        const ctx=c.getContext('2d');ctx.drawImage(img,0,0,c.width,c.height);
        const data=ctx.getImageData(0,4,128,1).data;let red=0,blue=0;
        for(let x=0;x<128;x++){red+=data[x*4];blue+=data[x*4+2];}
        rows.push({id,state:o.dataset.mediaState,src:img.src,declared:wrapper.dataset.mediaSource,
          sourceMatches:new URL(wrapper.dataset.mediaSource,location.href).href===img.src,
          width:img.naturalWidth,height:img.naturalHeight,displayWidth:rect.width,objectWidth:objectRect.width,
          red:red/128,blue:blue/128,canvasCount:o.closest('.track').querySelectorAll('canvas').length});
        images.push(img);
      }
      return {rows,distinctImages:new Set(images).size,canvasCount:document.querySelectorAll('.flow canvas').length};
    })()""" % json.dumps(ids)


@unittest.skipIf(find_browser() is None, "本机没有 Chrome、Edge 或 Chromium")
class ViewQualityTests(unittest.TestCase):
    def wait(self, tab, expression, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if _ev(tab, "Boolean(" + expression + ")"):
                return
            time.sleep(.05)
        self.fail("页面未达到画质验收条件：" + expression)

    def ready(self, tab, count=3):
        self.wait(tab, f"document.querySelectorAll('.obj').length==={count}&&window.__layerweavePaintIdle")
        done = _ev(tab, """(async()=>{await window.__layerweavePaintIdle();await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
          return window.__layerweavePaintState();})()""")
        self.assertEqual(done["failed"], 0, done)
        self.assertEqual(done["pending"], 0, done)
        self.wait(tab, f"document.querySelectorAll('.obj[data-media-state=ready]').length==={count}")

    def test_long_video_end_frames_keep_local_detail_without_full_span_texture(self):
        with quality_page() as view:
            tab, objects = view["tab"], view["objects"]
            self.ready(tab)
            short = _ev(tab, samples_expression(objects["short"], edge="first"))
            long = _ev(tab, samples_expression(objects["long"], edge="first"))
            tail = _ev(tab, samples_expression(objects["long"], edge="last"))
            self.assertGreater(long["rect"]["width"], 100000, "Fixture must exercise a genuinely long object")
            for name, sample in (("short first", short), ("long first", long), ("long last", tail)):
                self.assertTrue(all(p is not None for p in sample["samples"]), name)
                signal = channel_summary(sample, 1)
                self.assertGreater(signal["contrast"], 130, (name, signal))
                self.assertGreaterEqual(signal["transitions"], 12, (name, signal))
            # Both ends use different prepared frames, not a duplicate first frame.
            self.assertLess(abs(channel_summary(long, 0)["mean"] - channel_summary(long, 2)["mean"]), 20)
            self.assertGreater(channel_summary(tail, 2)["mean"] - channel_summary(tail, 0)["mean"], 50)
            # Only the two local end regions need media pixels. The middle remains
            # a styled object, rather than allocating a tile for its whole duration.
            self.assertLessEqual(len(long["canvases"]), 6, long["canvases"])
            self.assertLess(sum(c["width"] * c["height"] for c in long["canvases"]), 2_000_000)

    def test_image_requests_real_display_resolution_and_source_change_repaints(self):
        with quality_page() as view:
            tab, object_id = view["tab"], view["objects"]["image"]
            self.ready(tab)
            old = _ev(tab, samples_expression(object_id))
            self.assertTrue(all(p is not None for p in old["samples"]))
            needed = math.ceil((old["rect"]["width"] - 2 * old["zoom"]) * old["dpr"])
            self.assertGreater(needed, 640, "Fixture must require more than the old 160/320 source")
            requested = [width for name, width in view["requests"] if name == "red.png"]
            self.assertTrue(requested, view["requests"])
            self.assertGreaterEqual(max(requested), needed, (needed, requested))
            self.assertGreater(channel_summary(old, 0)["contrast"], 70, channel_summary(old, 0))
            self.assertGreater(channel_summary(old, 0)["mean"] - channel_summary(old, 2)["mean"], 50)
            # Keep the object identity and camera; change only the media source.
            with closing(open_database(view["database"])) as connection, transaction(connection) as write:
                write.update("object", object_id, {"information": {"source": str(view["replacement"])}},
                             project_id=view["project"])
            pixels = samples_expression(object_id)
            self.wait(tab, f"""(()=>{{const x={pixels};if(!x||x.state!=='ready'||x.samples.some(p=>!p))return false;
                return x.samples.reduce((n,p)=>n+p[2]-p[0],0)/x.samples.length>50;}})()""")
            updated = _ev(tab, pixels)
            self.assertEqual(updated["rect"], old["rect"])
            self.assertGreater(channel_summary(updated, 2)["contrast"], 70)
            blue_requests = [width for name, width in view["requests"] if name == "blue.png"]
            self.assertGreaterEqual(max(blue_requests, default=0), needed)

    def test_default_tile_density_matches_display_dpr_without_double_quality(self):
        with quality_page() as view:
            tab = view["tab"]
            self.ready(tab)
            self.assertFalse(_ev(tab, "new URLSearchParams(location.search).has('quality')"))
            sample = _ev(tab, samples_expression(view["objects"]["image"]))
            self.assertTrue(sample["canvases"])
            # A second global pixel-density multiplier would make this ratio 2*DPR.
            # This checks actual backing geometry, not merely the absence of a URL flag.
            for canvas in sample["canvases"]:
                self.assertGreater(canvas["displayWidth"], 0)
                self.assertAlmostEqual(canvas["width"] / canvas["displayWidth"], sample["dpr"], delta=.06)
                self.assertAlmostEqual(canvas["height"] / canvas["displayHeight"], sample["dpr"], delta=.06)

    def test_very_long_images_use_decoded_independent_native_fallbacks(self):
        with quality_page(long_images=True) as view:
            tab, object_id, peer_id = view["tab"], view["objects"]["image"], view["objects"]["peer"]
            self.ready(tab, count=4)
            expression = native_expression([object_id, peer_id])
            before = _ev(tab, expression)
            self.assertIsNotNone(before, "Paint idle must include mounting and decoding each final native image")
            self.assertEqual(before["distinctImages"], 2)
            self.assertLessEqual(before["canvasCount"], 10)
            for row in before["rows"]:
                self.assertEqual(row["state"], "ready")
                self.assertTrue(row["sourceMatches"], row)
                self.assertGreater(row["objectWidth"], 100000)
                self.assertGreater(row["displayWidth"], 100000)
                self.assertEqual(row["width"], 2048, "Fallback should retain the largest requested source")
                self.assertLessEqual(row["canvasCount"], 2, row)
                self.assertGreater(row["red"] - row["blue"], 50)
            # Both objects use the same physical image. Changing one must not
            # detach its peer's image node or replace its decoded visible content.
            with closing(open_database(view["database"])) as connection, transaction(connection) as write:
                write.update("object", object_id, {"information": {"source": str(view["replacement"])}},
                             project_id=view["project"])
            self.wait(tab, f"""(()=>{{const s={expression};return s&&s.rows.every(r=>r.state==='ready')&&
                s.rows[0].blue-s.rows[0].red>50&&s.rows[1].red-s.rows[1].blue>50;}})()""")
            self.ready(tab, count=4)
            after = _ev(tab, expression)
            self.assertEqual(after["distinctImages"], 2)
            self.assertNotEqual(after["rows"][0]["src"], before["rows"][0]["src"])
            self.assertEqual(after["rows"][1]["src"], before["rows"][1]["src"])
            self.assertTrue(all(row["sourceMatches"] and row["width"] == 2048 for row in after["rows"]))
            self.assertLessEqual(after["canvasCount"], 10)


if __name__ == "__main__":
    unittest.main()
