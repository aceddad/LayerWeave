import {useLayoutEffect, useRef} from 'react';
import {useVideoConfig} from 'remotion';

/** Canvas 图层：成百上千的点、拖尾、粒子用 Canvas 画，比同样数量的 SVG 元素快得多。
 *  draw 只依赖 t：同一个 t 必须画出同一张图（渲染是多进程乱序取帧的，不能依赖上一帧的状态）。 */
export const Layer: React.FC<{draw: (c: CanvasRenderingContext2D, w: number, h: number) => void; t: number; style?: React.CSSProperties}> = ({draw, t, style}) => {
  const {width, height} = useVideoConfig();
  const ref = useRef<HTMLCanvasElement>(null);
  useLayoutEffect(() => {
    const c = ref.current?.getContext('2d');
    if (!c) return;
    c.clearRect(0, 0, width, height);
    draw(c, width, height);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, width, height]);
  return <canvas ref={ref} width={width} height={height} style={{position: 'absolute', inset: 0, ...style}}/>;
};

export const dot = (c: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, alpha = 1, glow = 0) => {
  c.globalAlpha = alpha;
  c.fillStyle = color;
  c.shadowColor = color;
  c.shadowBlur = glow;
  c.beginPath();
  c.arc(x, y, r, 0, Math.PI * 2);
  c.fill();
  c.shadowBlur = 0;
  c.globalAlpha = 1;
};

/** 沿着 pos(t) 往回画一段拖尾；位置突然跳变的地方不连线 */
export const trail = (c: CanvasRenderingContext2D, pos: (t: number) => [number, number], t: number, seconds: number, color: string, width: number, fps = 24) => {
  const n = Math.ceil(seconds * fps);
  c.lineCap = 'round';
  c.strokeStyle = color;
  c.lineWidth = width;
  for (let k = 0; k < n; k++) {
    const [x0, y0] = pos(t - k / fps), [x1, y1] = pos(t - (k + 1) / fps);
    if (Math.hypot(x1 - x0, y1 - y0) > 90) continue;
    c.globalAlpha = 1 - k / n;
    c.beginPath();
    c.moveTo(x0, y0);
    c.lineTo(x1, y1);
    c.stroke();
  }
  c.globalAlpha = 1;
};
