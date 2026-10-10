// 动作参考用的人偶（three.js 胶囊木偶）：关节角度按摄影表插值，节奏由自己定；
// 渲出来的视频可以当作生视频模型的"参考视频"，让模型只负责把人偶画成角色。
// 放进 Remotion 工程（例如 src/puppet/Puppet.tsx）。需要 three：npm install three@0.170 @types/three@0.170
// 渲染时要给浏览器开 WebGL：静帧和导出都加 --gl angle（见 SKILL.md）。
import {useLayoutEffect, useMemo, useRef} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import * as THREE from 'three';

/** 姿势：角度是"解剖学"度数（正 = 向前弯／抬起），x、y 是骨盆位置（米）。人偶面朝 +x（画面右）。 */
export type Pose = {x: number; y: number; spine: number; neck: number; arm: number; elbow: number; thigh: number; knee: number; foot: number};
export type Ease = (u: number) => number;
/** 摄影表的一行：[到达这一帧, 姿势, 从上一行到这一行用的缓动] */
export type Key = [number, Pose, Ease];

export const inOut: Ease = (u) => u * u * (3 - 2 * u);      // 两头慢
export const easeIn: Ease = (u) => u * u * u;               // 越来越快：砸下去
export const easeOut: Ease = (u) => 1 - (1 - u) ** 3;       // 一下子到、慢慢停

/** 几个现成的姿势，可以在它们的基础上改 */
export const POSES = {
  STAND: {x: 0, y: 0.93, spine: 0, neck: 0, arm: 4, elbow: 6, thigh: 0, knee: 0, foot: 0},
  HEAD_DOWN: {x: 0, y: 0.93, spine: 6, neck: 38, arm: 2, elbow: 6, thigh: 0, knee: 0, foot: 0},
  BUCKLE: {x: 0.12, y: 0.78, spine: 14, neck: 42, arm: 10, elbow: 10, thigh: 32, knee: 64, foot: 32},
  KNEEL_HIT: {x: 0.4, y: 0.48, spine: 18, neck: 44, arm: 22, elbow: 14, thigh: 5, knee: 95, foot: -90},
  KNEEL: {x: 0.38, y: 0.46, spine: 24, neck: 48, arm: 16, elbow: 10, thigh: 8, knee: 98, foot: -90},
  SLUMP: {x: 0.15, y: 0.37, spine: 70, neck: 22, arm: 72, elbow: 8, thigh: 40, knee: 130, foot: -90},
} satisfies Record<string, Pose>;

/** 示例摄影表：站着 → 低头 → 膝盖一软 → 砸到地上 → 跪住 → 上身瘫下去（24 fps，共 120 帧） */
export const KNEEL_KEYS: Key[] = [
  [0, POSES.STAND, inOut],
  [14, POSES.STAND, inOut],         // 站着停一下
  [30, POSES.HEAD_DOWN, inOut],     // 低头
  [34, POSES.HEAD_DOWN, inOut],     // 停住
  [44, POSES.BUCKLE, easeIn],       // 膝盖一软
  [50, POSES.KNEEL_HIT, easeIn],    // 砸到地上（加速）
  [56, POSES.KNEEL, easeOut],       // 冲击后的余势
  [68, POSES.KNEEL, inOut],         // 跪着停住
  [92, POSES.SLUMP, inOut],         // 上身慢慢瘫下去，双手撑地
  [120, POSES.SLUMP, inOut],
];

export const poseAt = (keys: Key[], f: number): Pose => {
  if (f <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [f1, p1, ease] = keys[i], [f0, p0] = keys[i - 1];
    if (f <= f1) {
      const u = ease((f - f0) / (f1 - f0));
      const out = {} as Pose;
      (Object.keys(p0) as (keyof Pose)[]).forEach((k) => (out[k] = p0[k] + (p1[k] - p0[k]) * u));
      return out;
    }
  }
  return keys[keys.length - 1][1];
};

const D = Math.PI / 180;

/** 相机：位置和注视点（米）。默认是略高于腰部、斜前方的中景。 */
export type CameraSpec = {fov: number; position: [number, number, number]; lookAt: [number, number, number]};
const DEFAULT_CAMERA: CameraSpec = {fov: 32, position: [0.9, 1.0, 3.9], lookAt: [0.2, 0.78, 0]};

function build(width: number, height: number, cam: CameraSpec) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#0b0d14');
  const body = new THREE.MeshStandardMaterial({color: '#d9dbe0', roughness: 0.55});
  const joint = new THREE.MeshStandardMaterial({color: '#8a8f99', roughness: 0.6});
  const limb = (len: number, r: number, up = false) => {
    const g = new THREE.Group();
    const m = new THREE.Mesh(new THREE.CapsuleGeometry(r, Math.max(0.01, len - 2 * r), 6, 16), body);
    m.position.y = up ? len / 2 : -len / 2; m.castShadow = true; g.add(m);
    const j = new THREE.Mesh(new THREE.SphereGeometry(r * 1.05, 16, 12), joint); j.castShadow = true; g.add(j);
    return g;
  };
  const root = new THREE.Group(); scene.add(root);
  const pelvis = new THREE.Mesh(new THREE.SphereGeometry(0.13, 20, 14), body); pelvis.scale.set(1, 0.7, 1.15); pelvis.castShadow = true; root.add(pelvis);
  const spine = limb(0.5, 0.12, true); spine.position.y = 0.04; root.add(spine);
  const neck = new THREE.Group(); neck.position.y = 0.52; spine.add(neck);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 24, 18), body); head.scale.set(1, 1.15, 1); head.position.y = 0.15; head.castShadow = true; neck.add(head);
  const nose = new THREE.Mesh(new THREE.SphereGeometry(0.025, 8, 6), joint); nose.position.set(0.1, 0.15, 0); neck.add(nose); // 朝向标记
  const arms: THREE.Group[] = [], elbows: THREE.Group[] = [], thighs: THREE.Group[] = [], knees: THREE.Group[] = [], feet: THREE.Group[] = [];
  for (const s of [-1, 1]) {
    const sh = limb(0.28, 0.045); sh.position.set(0, 0.46, s * 0.19); spine.add(sh); arms.push(sh);
    const el = limb(0.26, 0.04); el.position.y = -0.28; sh.add(el); elbows.push(el);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.05, 12, 10), body); hand.position.y = -0.28; el.add(hand);
    const th = limb(0.45, 0.065); th.position.set(0, -0.02, s * 0.1); root.add(th); thighs.push(th);
    const kn = limb(0.43, 0.055); kn.position.y = -0.45; th.add(kn); knees.push(kn);
    const ft = new THREE.Group(); ft.position.y = -0.43; kn.add(ft); feet.push(ft);
    const fm = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.06, 0.09), body); fm.position.set(0.07, -0.02, 0); fm.castShadow = true; ft.add(fm);
  }
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({color: '#151924', roughness: 0.9}));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
  scene.add(new THREE.HemisphereLight('#9fb4ff', '#0b0d14', 0.9));
  const key = new THREE.DirectionalLight('#ffffff', 2.2); key.position.set(2, 4, 3); key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024); Object.assign(key.shadow.camera, {left: -2, right: 2, top: 2, bottom: -2}); scene.add(key);
  const camera = new THREE.PerspectiveCamera(cam.fov, width / height, 0.1, 50);
  camera.position.set(...cam.position); camera.lookAt(...cam.lookAt);
  const apply = (p: Pose) => {
    root.position.set(p.x, p.y, 0);
    spine.rotation.z = -p.spine * D;                       // 向前弯 = 顺时针
    neck.rotation.z = -p.neck * D;
    arms.forEach((a) => (a.rotation.z = p.arm * D));       // 手臂向前抬 = 逆时针
    elbows.forEach((e) => (e.rotation.z = p.elbow * D));
    thighs.forEach((t) => (t.rotation.z = p.thigh * D));  // 大腿向前抬 = 逆时针
    knees.forEach((k) => (k.rotation.z = -p.knee * D));   // 膝盖弯 = 小腿往后
    feet.forEach((f) => (f.rotation.z = p.foot * D));
  };
  return {scene, camera, apply};
}

export const Puppet: React.FC<{keys?: Key[]; camera?: CameraSpec}> = ({keys = KNEEL_KEYS, camera = DEFAULT_CAMERA}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const ref = useRef<HTMLCanvasElement>(null);
  const rig = useMemo(() => build(width, height, camera), [width, height, camera]);
  const renderer = useRef<THREE.WebGLRenderer | null>(null);
  useLayoutEffect(() => {
    if (!ref.current) return;
    if (!renderer.current) {
      renderer.current = new THREE.WebGLRenderer({canvas: ref.current, antialias: true, preserveDrawingBuffer: true});
      renderer.current.setSize(width, height, false);
      renderer.current.shadowMap.enabled = true;
    }
    rig.apply(poseAt(keys, frame));
    renderer.current.render(rig.scene, rig.camera);
  }, [frame, rig, keys, width, height]);
  return (
    <AbsoluteFill>
      <canvas ref={ref} width={width} height={height} style={{width: '100%', height: '100%'}}/>
    </AbsoluteFill>
  );
};
