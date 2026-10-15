// 对象编号稳定，素材地址仍可改变；请求 URL 同时标明 source，避免解码和浏览器缓存复用旧素材。
// source 不变时 URL 不变；这不是文件内容或修改时间的版本，也不改变服务端的对象路由。
export function mediaUrl(url: string, source?: string): string {
  if (!source) return url;
  const at = url.indexOf('#'), path = at < 0 ? url : url.slice(0, at), fragment = at < 0 ? '' : url.slice(at);
  return path + (path.includes('?') ? '&' : '?') + 'lw_source=' + encodeURIComponent(source) + fragment;
}
