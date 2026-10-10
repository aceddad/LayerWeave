import {Composition} from 'remotion';
import {Film} from './Film';
import {FILM_FRAMES, FPS, HEIGHT, WIDTH} from './time';

// 同一条片子开几个入口：正片、带时间码的审阅版、用占位字检查字幕排版的版本、带真字幕的版本。
export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Film" component={Film} durationInFrames={FILM_FRAMES} fps={FPS} width={WIDTH} height={HEIGHT}
      defaultProps={{music: true, timecode: false, subtitles: 'off' as const}}/>
    <Composition id="Film-Review" component={Film} durationInFrames={FILM_FRAMES} fps={FPS} width={WIDTH} height={HEIGHT}
      defaultProps={{music: true, timecode: true, subtitles: 'off' as const}}/>
    <Composition id="Film-Layout" component={Film} durationInFrames={FILM_FRAMES} fps={FPS} width={WIDTH} height={HEIGHT}
      defaultProps={{music: true, timecode: true, subtitles: 'placeholder' as const}}/>
    <Composition id="Film-Subtitled" component={Film} durationInFrames={FILM_FRAMES} fps={FPS} width={WIDTH} height={HEIGHT}
      defaultProps={{music: true, timecode: false, subtitles: 'on' as const}}/>
  </>
);
