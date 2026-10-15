"""Bench validity and scheduling tests; no browser/GPU work in this module."""
import json
import shutil
import subprocess
import unittest
from unittest.mock import patch

from layerweave.tool.builtin.view import bench as b


def scene(*, x=0, y=0, node_x=0, objects=5, images=2, plugins=2):
    return {"格子": objects, "图": images, "插件画的格子": plugins, "failed_media": 0,
            "viewport": {"x": x, "y": y, "zoom": 1},
            "nodes": [{"id": "b1", "x": node_x, "y": 0}]}


def motion(*, pan=False):
    return {"before": scene(), "after": scene(x=40) if pan else scene(node_x=40),
            "input_displacement": [40, 0], "ready": {"ok": True}, "cdp_errors": [],
            "active": {"sample_count": 3}, "actual_pointer_events": 5}


class BenchValidityTests(unittest.TestCase):
    def test_empty_scene_and_missing_plugin_are_invalid(self):
        self.assertIsNotNone(b._scene_issue(scene(objects=0)))
        self.assertIsNotNone(b._scene_issue(scene(plugins=0), plugin=True))
        self.assertIsNotNone(b._scene_issue(scene(images=0), images=True))
        self.assertIsNone(b._scene_issue(scene(), images=True, plugin=True))

    def test_failed_media_is_not_ready(self):
        value = scene()
        value["failed_media"] = 1
        self.assertIsNotNone(b._scene_issue(value))

    def test_motion_checks_expected_target_and_displacement(self):
        value = motion()
        self.assertIsNone(b._motion_issue(value, board_id="b1"))
        self.assertEqual(value["actual_displacement"], [40, 0])
        value["after"]["nodes"][0]["x"] = 0
        self.assertIsNotNone(b._motion_issue(value, board_id="b1"))
        self.assertIsNone(b._motion_issue(motion(pan=True)))

    def test_autopan_and_accidental_board_drag_are_not_comparable(self):
        value = motion()
        value["after"]["viewport"]["y"] = 5
        self.assertIn("自动平移", b._motion_issue(value, board_id="b1"))
        self.assertIsNotNone(b._motion_issue(motion()))

    def test_no_frames_or_cdp_errors_do_not_pass(self):
        value = motion()
        value["active"]["sample_count"] = 0
        self.assertIsNotNone(b._motion_issue(value, board_id="b1"))
        value = motion()
        value["cdp_errors"] = [{"error": {"message": "rejected"}}]
        self.assertIsNotNone(b._motion_issue(value, board_id="b1"))

    def test_summary_preserves_keys_and_cannot_hide_an_invalid_round(self):
        good = dict.fromkeys(b.GATES, 1)
        bad = {**good, "diagnostics": {"zoom_pan_plugin": {"valid": False, "reason": "插件没有画出"}}}
        rows = {r["key"]: r for r in b.summarize([good, bad])}
        self.assertEqual(set(rows), set(b.GATES))
        self.assertEqual(rows["zoom_pan_plugin"]["rounds"], [1, None])
        self.assertFalse(rows["zoom_pan_plugin"]["ok"])
        self.assertEqual(rows["zoom_pan_plugin"]["status"], "invalid")
        self.assertEqual(rows["zoom_pan_plugin"]["issues"], ["插件没有画出"])
        self.assertTrue(rows["click"]["ok"])

    def test_summary_exposes_samples_and_max_without_changing_gate(self):
        run = dict.fromkeys(b.GATES, 1)
        run["diagnostics"] = {"board_drag": {"active": b._frame_stats([7, 14, 250])}}
        row = next(r for r in b.summarize([run]) if r["key"] == "board_drag")
        self.assertEqual((row["gate"], row["max_ms"], row["sample_counts"]), (33, [250], [3]))
        self.assertEqual(b._frame_stats([]), {"p95_ms": None, "max_ms": None, "sample_count": 0, "over_33_ms": 0})

    def test_balanced_order_and_existing_single_build(self):
        self.assertEqual(b._run_order(["A", "B"], 3), ["A", "B", "B", "A", "A", "B"])
        self.assertEqual(b._run_order(["A"], 3), ["A", "A", "A"])

    def test_focus_preserves_normal_mode_and_existing_url_parameters(self):
        result = b._focus_url("http://localhost:8765/?project=4&record=0&focus=8", 12)
        self.assertIn("project=4", result)
        self.assertIn("record=0", result)
        self.assertIn("focus=12", result)
        self.assertNotIn("capture", result)

    def test_focus_reveals_sticky_covered_target_then_continues(self):
        hidden = {"point": None, "width": 6, "height": 70, "reveal_delta": [300, -10]}
        shown = {"point": [800, 300], "width": 9, "height": 90, "reveal_delta": None}
        with patch.object(b, "_anchor", return_value="42"), \
                patch.object(b, "_open", return_value={"ready": {"ok": True}}), \
                patch.object(b, "_target", side_effect=[hidden, shown]), \
                patch.object(b, "_pan") as pan, \
                patch.object(b, "_ev", side_effect=[{"缩放": 3}, {"ok": True}]):
            chosen, ready = b._focus(object(), "http://localhost/?project=1")
        self.assertEqual(chosen, "42")
        self.assertTrue(ready["ok"])
        pan.assert_called_once()
        self.assertEqual(pan.call_args.args[1], [300, -10])

    def test_input_schedule_does_not_wait_for_browser_acknowledgement(self):
        class Clock:
            now = 0

            def read(self):
                return self.now

            def sleep(self, delay):
                self.now += delay

        class Tab:
            sent = []

            def send(self, method, **params):
                self.sent.append((method, params))

            def call(self, *args, **kwargs):
                raise AssertionError("No per-move acknowledgement is allowed")

        clock, tab = Clock(), Tab()
        with patch.object(b.time, "perf_counter", clock.read), patch.object(b.time, "sleep", clock.sleep):
            sent = b._send_moves(tab, (10, 20), (2, 0), 120)
        self.assertEqual(len(sent), 120)
        self.assertAlmostEqual(sent[-1], 2000)
        self.assertEqual(tab.sent[-1][1]["x"], 250)

    def test_pan_uses_middle_button_for_press_move_and_release(self):
        class Tab:
            errors = []

            def __init__(self):
                self.calls = []

            def call(self, method, **params):
                self.calls.append((method, params))

        tab = Tab()
        recorded = {"frames": [7, 14], "start": 0, "end": 140, "pointers": [[1, 1, 4, 0]]}
        with patch.object(b, "_ev", side_effect=[scene(), True, True, recorded,
                                                {"ok": True}, scene(x=40)]), \
                patch.object(b, "_send_moves", return_value=[16, 133]) as send:
            value = b._measure_drag(tab, (10, 20), (5, 0), 8, pan=True)
        self.assertEqual(value["button"], "middle")
        self.assertEqual(send.call_args.kwargs, {"button": "middle", "buttons": 4})
        press = next(params for _, params in tab.calls if params.get("type") == "mousePressed")
        release = next(params for _, params in tab.calls if params.get("type") == "mouseReleased")
        self.assertEqual((press["button"], press["buttons"], release["button"]), ("middle", 4, "middle"))
        self.assertFalse(any(method == "Input.dispatchKeyEvent" for method, _ in tab.calls))

    def test_board_activation_keeps_the_final_input_position(self):
        class Tab:
            errors = []

            def __init__(self):
                self.calls = []

            def call(self, method, **params):
                self.calls.append((method, params))

        tab = Tab()
        recorded = {"frames": [7, 14], "start": 0, "end": 140, "pointers": [[1, 1, 4, 0]]}
        with patch.object(b, "_ev", side_effect=[scene(), True, True, True, recorded,
                                                {"ok": True}, scene(node_x=396)]), \
                patch.object(b, "_send_moves", return_value=[16, 133]) as send:
            value = b._measure_drag(tab, (10, 20), (50, 0), 8)
        self.assertEqual(value["input_displacement"], [400, 0])
        self.assertEqual(value["activation_displacement"], [4, 0])
        self.assertEqual(send.call_args.args[1:], ([14, 20], [49.5, 0], 8))
        release = next(params for _, params in tab.calls if params.get("type") == "mouseReleased")
        self.assertEqual((release["x"], release["y"]), (410, 20))

    @unittest.skipUnless(shutil.which("node"), "Node is optional; browser smoke also parses these scripts")
    def test_page_expressions_are_valid_javascript(self):
        expressions = [b.FIRST_OBJ, b.MEASURE_INIT, b.DRAG_ON, b.DRAG_OFF, b.EVENTS_ON, b.EVENT_TOP,
                       b.VISIBLE_OBJ % .5, b.BOARD_TITLE, b.BOARD_ANCHOR, b.PANE, b.FLOW_CENTER,
                       b.SCENE, b.READY, b.GPU, b._target_expression("42")]
        result = subprocess.run([shutil.which("node"), "-e",
                                 "for(const x of JSON.parse(process.argv[1]))new Function(x);",
                                 json.dumps(expressions)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is optional; browser smoke also executes initialization")
    def test_combined_initialization_registers_and_records_real_listeners(self):
        program = """
          const assert=require('node:assert/strict'), listeners=new Map();
          global.window=global;
          global.document={querySelector:()=>({})};
          global.MutationObserver=class {observe(){} disconnect(){}};
          global.addEventListener=(name,fn)=>listeners.set(name,fn);
          new Function(process.argv[1])();
          for(const name of ['pointerdown','pointermove','pointerup','pointercancel'])
            assert.equal(typeof listeners.get(name),'function',name);
          window.__benchDrag={armed:true,active:false,pointers:[]};
          listeners.get('pointerdown')({clientX:10,clientY:20});
          listeners.get('pointermove')({clientX:30,clientY:20,timeStamp:performance.now()});
          listeners.get('pointerup')({clientX:30,clientY:20});
          const measured=window.__benchDrag;
          assert.equal(measured.active,false);
          assert.equal(measured.pointers.length,1);
          assert.deepEqual(measured.down,[10,20]);
          assert.deepEqual(measured.up,[30,20]);
          assert.ok(measured.end>=measured.start);
        """
        result = subprocess.run([shutil.which("node"), "-e", program,
                                 b.FIRST_OBJ + "\n;\n" + b.MEASURE_INIT], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is optional; browser smoke also executes hit testing")
    def test_hit_point_uses_exposed_edge_and_never_another_object(self):
        program = """
          const assert=require('node:assert/strict');
          const bounds={left:0,top:0,right:100,bottom:100};
          const rect={left:10,top:20,right:13,bottom:30,width:3,height:10};
          const el={getBoundingClientRect:()=>rect,contains:hit=>hit===child};
          const child={},neighbor={},seen=[];
          global.document={
            querySelector:()=>({getBoundingClientRect:()=>bounds}),
            elementFromPoint:(x,y)=>{seen.push([x,y]);return x<10.7?child:neighbor;}
          };
          const locate=new Function('el',process.argv[1]+'return point(el);');
          const exposed=locate(el);
          assert.ok(exposed[0]>=10&&exposed[0]<10.7);
          assert.ok(exposed[1]>20&&exposed[1]<30);
          assert.ok(seen.some(([x])=>x>=10.7),'center was tried first');
          document.elementFromPoint=()=>neighbor;
          assert.equal(locate(el),null,'fully covered target must not click its neighbor');
          rect.left=-2;rect.right=1;rect.width=3;
          document.elementFromPoint=(x,y)=>{assert.ok(x>0&&x<1);return el;};
          assert.ok(locate(el),'clipped target can use its visible strip');
        """
        result = subprocess.run([shutil.which("node"), "-e", program, b.DOM_HELPERS],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is optional; browser smoke also checks sticky-column targeting")
    def test_target_proposes_real_pan_past_sticky_column(self):
        program = """
          const assert=require('node:assert/strict');
          const bounds={left:0,top:40,right:1200,bottom:760,width:1200,height:720};
          const rect={left:398,top:280,right:404.6,bottom:360,width:6.6,height:80};
          const names={getBoundingClientRect:()=>({left:0,right:450,top:0,bottom:760})};
          const node={querySelectorAll:()=>[names]};
          const el={getBoundingClientRect:()=>rect,contains:()=>false,closest:()=>node};
          let blocked=true;
          global.document={querySelector:s=>s==='.flow'?{getBoundingClientRect:()=>bounds}:el,
            elementFromPoint:()=>blocked?names:el};
          const locate=new Function('return '+process.argv[1]);
          const hidden=locate();
          assert.equal(hidden.point,null);
          assert.ok(hidden.reveal_delta[0]>0);
          const revealedX=rect.left+rect.width/2+hidden.reveal_delta[0];
          assert.ok(revealedX>490&&revealedX<1100);
          rect.left+=hidden.reveal_delta[0];rect.right+=hidden.reveal_delta[0];
          blocked=false;
          const shown=locate();
          assert.ok(shown.point);
          assert.equal(shown.reveal_delta,null);
        """
        result = subprocess.run([shutil.which("node"), "-e", program, b._target_expression("42")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
