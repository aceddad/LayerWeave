import {AbsoluteFill} from 'remotion';
import {beat, clamp, ease, prog} from '../time';
import {GlyphWord, Panes, Warp, impact} from '../ui/GlyphWord';
import arial from './arial.json';
import cjk from './cjk.json';

// 示例场景（放进 remotion-animate 模板的 src/scenes/，并在 Film.tsx 的段落表里登记）。
// arial.json、cjk.json 用 scripts/build_glyph_shapes.py 导出：
//   python scripts/build_glyph_shapes.py 某粗体.ttf src/scenes/arial.json EXECUTION
//   python scripts/build_glyph_shapes.py 某中文字体.ttf src/scenes/cjk.json 执行 --height em
// 时间线：①第 28 拍受力（右端钉住，压力从右往左传）；②第 30 拍沿斜线切开、上下分离；③第 32 拍斜向窗格碎裂。
export const GlyphStudy: React.FC<{t: number}> = ({t}) => {
  const hitAt = beat(28), age = t - hitAt;
  const pressWarp: Warp = (x, y, i) => {
    const local = impact(age - (8 - i) * 0.009);                       // 每个字晚一点受力
    const across = clamp((x - 160) / 1600);
    return [x + (1760 - x) * local * 0.1, 540 + (y - 540) * (1 + local * 0.24 * across) + Math.sin(across * Math.PI) * local * 26];
  };
  const open = ease(prog(t, beat(30), beat(30.6))) * 140;
  const breakAt = beat(32);
  const piece = (j: number) => {
    const age2 = t - (breakAt + j * 0.06);
    const release = prog(age2, 0, 0.45);
    const side = j < 4 ? -1 : 1;
    return {x: side * release * release * 530, y: release * release * 1260, z: release * 220,
      rotateY: side * Math.pow(release, 1.3) * 78, rotateZ: side * release * 13, gone: release >= 1};
  };
  const scene = (
    <AbsoluteFill style={{background: '#f4eddf'}}>
      <svg viewBox="0 0 1920 1080" width="100%" height="100%">
        {t < beat(30) ? (
          <GlyphWord data={arial} word="EXECUTION" x={160} y={430} w={1600} h={220} fill="#1d2025" warp={pressWarp}/>
        ) : (
          <>
            <GlyphWord data={arial} word="EXECUTION" x={160} y={430} w={1600} h={220} fill="#1d2025"
              cut={{x: 960, y: 541, angle: -6, keep: 'above'}} warp={(x, y) => [x - open * 0.2, y - open]}/>
            <GlyphWord data={arial} word="EXECUTION" x={160} y={430} w={1600} h={220} fill="#1d2025"
              cut={{x: 960, y: 541, angle: -6, keep: 'below'}} warp={(x, y) => [x + open * 0.2, y + open]}/>
          </>
        )}
        <GlyphWord data={cjk} word="执行" x={830} y={800} w={260} h={130} fill="#e74739"/>
      </svg>
    </AbsoluteFill>
  );
  return t < breakAt ? scene : (
    <AbsoluteFill style={{background: '#1d2025', overflow: 'hidden'}}>
      <Panes count={9} piece={piece}>{scene}</Panes>
    </AbsoluteFill>
  );
};
