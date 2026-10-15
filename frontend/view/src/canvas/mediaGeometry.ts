import type {MediaRect} from './mediaQueue';

export const SOURCE_WIDTHS = [160, 320, 640, 1280, 2048] as const;
export function sourceWidth(width: number, height: number, aspect: number, scale: number) {
  const need = Math.ceil(Math.max(width, height * aspect) * scale);
  return SOURCE_WIDTHS.find((size) => size >= need) ?? SOURCE_WIDTHS[SOURCE_WIDTHS.length - 1];
}
export function coverCrop(sourceWidth: number, sourceHeight: number, width: number, height: number) {
  const ir = sourceWidth / Math.max(1, sourceHeight), cr = width / height;
  let w = sourceWidth, h = sourceHeight, x = 0, y = 0;
  if (ir > cr) { w = h * cr; x = (sourceWidth - w) / 2; }
  else { h = w / cr; y = (sourceHeight - h) / 2; }
  return {x, y, w, h};
}
export function videoEnds(width: number, height: number): MediaRect[] {
  return [{x: 1, y: 1, w: 64, h: Math.max(1, height - 2)},
    {x: width - 65, y: 1, w: 64, h: Math.max(1, height - 2)}];
}
export function endCoverage(rect: MediaRect): MediaRect[] {
  return [{x: rect.x, y: rect.y, w: 65, h: rect.h},
    {x: rect.x + rect.w - 65, y: rect.y, w: 65, h: rect.h}];
}
