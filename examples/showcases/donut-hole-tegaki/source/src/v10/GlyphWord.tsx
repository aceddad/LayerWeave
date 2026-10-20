// 可变形的字：用真实字体轮廓（build_glyph_shapes.py 导出的 JSON）在 SVG 里逐点绘制。
// 变形可以连续地穿过整个单词；也可以先沿一条直线把轮廓切开，再分别弯曲，切口是真切口。
// 复制到 Remotion 工程（例如 src/ui/GlyphWord.tsx）后使用；只依赖 React。
import type {CSSProperties, ReactNode} from 'react';

export type Point = [number, number];
/** 逐点变形：输入画布坐标和字形序号（第几个字），返回新坐标 */
export type Warp = (x: number, y: number, glyph: number) => Point;
export type Shape = {width: number; height: number; glyphs: {char: string; x: number; width: number; contours: number[][][]}[]};
export type ShapeData = {words: Record<string, Shape>};
/** 切线：画布上经过 (x, y)、倾角 angle 度的直线；keep 选保留哪一侧 */
export type Cut = {x: number; y: number; angle: number; keep: 'above' | 'below'};

const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

/** 先切后弯：用半平面裁剪闭合轮廓，交点处插入新点，保留真实切口 */
export const cutContour = (points: Point[], cut: Cut): Point[] => {
  const rad = (cut.angle * Math.PI) / 180;
  const nx = -Math.sin(rad), ny = Math.cos(rad);                   // 直线的法向（指向"下方"）
  const sign = cut.keep === 'above' ? 1 : -1;
  const distance = (p: Point) => ((p[0] - cut.x) * nx + (p[1] - cut.y) * ny) * sign;
  const result: Point[] = [];
  for (let i = 0; i < points.length; i++) {
    const a = points[(i + points.length - 1) % points.length], b = points[i];
    const da = distance(a), db = distance(b);
    if ((da <= 0) !== (db <= 0)) {
      const r = da / (da - db);
      result.push([lerp(a[0], b[0], r), lerp(a[1], b[1], r)]);
    }
    if (db <= 0) result.push(b);
  }
  return result;
};

/** 一个单词：放进 (x, y, w, h) 的框里（h 对应参考高度 1000），可选切开、逐点变形 */
export const GlyphWord: React.FC<{
  data: ShapeData; word: string; x: number; y: number; w: number; h: number;
  fill?: string; stroke?: string; strokeWidth?: number; opacity?: number; warp?: Warp; cut?: Cut;
}> = ({data, word, x, y, w, h, fill = '#fff', stroke, strokeWidth = 1, opacity = 1, warp, cut}) => {
  const shape = data.words[word];
  if (!shape) throw new Error(`字形数据里没有 "${word}"，请用 build_glyph_shapes.py 导出`);
  return (
    <g opacity={opacity} fill={fill} stroke={stroke} strokeWidth={strokeWidth} strokeLinejoin="round" fillRule="evenodd">
      {shape.glyphs.map((g, i) => (
        <path key={i} d={g.contours.map((contour) => {
          let points: Point[] = contour.map((pt) => [x + ((g.x + pt[0]) / shape.width) * w, y + (pt[1] / shape.height) * h]);
          if (cut) points = cutContour(points, cut);
          if (points.length < 3) return '';
          return points.map((pt, j) => {
            const p = warp ? warp(pt[0], pt[1], i) : pt;
            return `${j ? 'L' : 'M'}${p[0].toFixed(2)},${p[1].toFixed(2)}`;
          }).join(' ') + 'Z';
        }).join(' ')}/>
      ))}
    </g>
  );
};

/** 定格式的受力：到达（0–0.12 s）→ 峰值 → 回弹（0.12–0.2 s）→ 回到静止（0.38 s 后为 0）。
 *  只在受力的那一下动，不让字一直晃。age = 当前秒数 − 受力时刻。 */
export const impact = (age: number) => {
  const smooth = (p: number) => { const q = Math.max(0, Math.min(1, p)); return q * q * (3 - 2 * q); };
  if (age < 0) return 0;
  if (age < 0.12) return Math.pow(age / 0.12, 2);
  if (age < 0.2) return lerp(1, -0.12, smooth((age - 0.12) / 0.08));
  if (age < 0.38) return lerp(-0.12, 0, smooth((age - 0.2) / 0.18));
  return 0;
};

/** 斜向窗格碎裂：把同一份画面（children）按斜向窗格裁开，每格各自带透视飞走；原来的接缝留在原处。
 *  piece(j) 返回第 j 格当前的 { x, y, z, rotateY, rotateZ, gone }。 */
export const Panes: React.FC<{
  count: number; width?: number; slope?: number; offset?: number; height?: number;
  piece: (j: number) => {x: number; y: number; z: number; rotateY: number; rotateZ: number; gone?: boolean};
  children: ReactNode; style?: CSSProperties;
}> = ({count, width = 300, slope = 0.32, offset = -330, height = 1080, piece, children, style}) => {
  const edgeX = (j: number, y: number) => offset + j * width + slope * y;
  const polygon = (j: number) =>
    `polygon(${edgeX(j, -80)}px -80px,${edgeX(j + 1, -80)}px -80px,${edgeX(j + 1, height + 80)}px ${height + 80}px,${edgeX(j, height + 80)}px ${height + 80}px)`;
  return (
    <>
      {Array.from({length: count}, (_, j) => {
        const p = piece(j);
        return (
          <div key={j} style={{
            position: 'absolute', inset: 0, clipPath: polygon(j), ...style,
            transformOrigin: `${edgeX(j, height / 2) + width / 2}px ${height / 2}px`,
            transform: `perspective(850px) translate3d(${p.x}px,${p.y}px,${p.z}px) rotateY(${p.rotateY}deg) rotateZ(${p.rotateZ}deg)`,
            visibility: p.gone ? 'hidden' : undefined,
          }}>{children}</div>
        );
      })}
    </>
  );
};
