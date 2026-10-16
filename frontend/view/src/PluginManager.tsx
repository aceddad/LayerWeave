// 本机管理与市场共用 view_plugin；查看目录不会安装，官方插件也按用户选择安装。
import {useEffect, useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {api} from './api';
import {pluginApplies, refreshPlugins} from './plugin/registry';
import {useModel, useStore} from './store';
import type {MarketItem, PluginRow} from './types';

export function PluginManager({onClose}: {onClose: () => void}) {
  const model = useModel();
  const {list, plugins, errors} = useStore(useShallow((s) => ({list: s.pluginList, plugins: s.plugins, errors: s.pluginErrors})));
  const [target, setTarget] = useState(''), [name, setName] = useState('');
  const [catalog, setCatalog] = useState(list?.catalog ?? '');
  const [market, setMarket] = useState<MarketItem[]>([]), [marketError, setMarketError] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [details, setDetails] = useState('');
  const box = useRef<HTMLDivElement>(null);

  const browse = async (source?: string) => {
    setMarketError('');
    try {
      const result = await api.plugin({action: 'market', catalog: source || undefined});
      if (result.recorded === false) return;
      setMarket(result.items ?? []); setCatalog(result.catalog);
      if (result.issues?.length) setMarketError(result.issues.map((i) => i.message).join('；'));
    } catch (e) { setMarketError((e as Error).message); }
  };
  useEffect(() => { refreshPlugins(); browse(list?.catalog); }, []);
  useEffect(() => {
    const away = (e: MouseEvent) => {
      const el = e.target as Element;
      if (!box.current?.contains(el) && !el.closest?.('.plugin-toggle')) onClose();
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', away); document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc); };
  }, [onClose]);

  const act = async (action: string, what?: string, extra: {name?: string; catalog?: string; version?: string; files?: boolean} = {}) => {
    setBusy(true); setError('');
    try {
      const result = await api.plugin({action, target: what, ...extra});
      if (result.recorded === false) { setError('截图页面不修改插件清单'); return false; }
      if (action === 'info' || result.status === 'failed' || result.status === 'migrated' || result.issues?.length) setDetails(result.text);
      await refreshPlugins();
      if (['install', 'update', 'remove'].includes(action)) await browse(catalog);
      return result.status !== 'failed';
    } catch (e) { setError((e as Error).message); return false; }
    finally { setBusy(false); }
  };

  const status = (row: PluginRow): [string, string] => {
    if (row.problem) return ['bad', row.problem];
    if (!row.on) return ['off', '已安装，已关闭'];
    if (errors[row.name]) return ['bad', '已安装；页面加载失败：' + errors[row.name]];
    const p = plugins.find((x) => x.name === row.name);
    if (!p) return ['wait', '已安装，正在载入'];
    if (!pluginApplies(p, model)) return ['idle', '已载入；这个项目没有它管的对象'];
    return ['ok', '已载入'];
  };
  const available = market.length ? market : (list?.recommended ?? []).map((r) => ({...r, version: '', supported: true, compatible: false, problem: '等待目录查询'}));

  return (
    <div className="plugins-box" ref={box}>
      <div className="plugins-head"><b>插件</b><span className="hint">按需安装；画布无需插件</span></div>
      {list?.problem && <p className="plugins-error">{list.problem}</p>}
      {list?.migration_issues.map((issue, i) => <p key={i} className="plugins-error">旧记录已保留，需处理：{issue.problem}</p>)}
      {list?.migration_pending && <p className="plugins-error">当前仅预览旧清单；迁移会保留备份和开关偏好，不自动安装。
        <button disabled={busy} onClick={() => act('migrate')}>迁移旧清单</button></p>}
      <ul className="plugins-list">
        {(list?.plugins ?? []).map((row) => {
          const [cls, text] = status(row);
          return <li key={row.name} className={`plugin-row ${cls}`}>
            <span className="dot" title={text} />
            <div className="what"><div><b>{row.label}</b> <code>{row.name}</code> {row.version}</div>
              <small className="where" title={row.path}>{row.source === 'managed' ? '选装包' : '开发链接'} · {row.path}</small>
              {row.about && <small>{row.about}</small>}<small className="state">{text}</small>
              <button disabled={busy} onClick={() => act('info', row.name)}>说明</button>
              {row.source === 'managed' && <button disabled={busy} onClick={() => act('update', row.name)}>更新</button>}
              <button disabled={busy} title="解除登记，保留文件" onClick={() => act('remove', row.name)}>去掉</button>
              {row.source === 'managed' && <button disabled={busy} title="解除登记，把安装器拥有的文件移到可恢复目录" onClick={() => act('remove', row.name, {files: true})}>卸载并回收</button>}
            </div>
            <label className="toggle"><input type="checkbox" checked={row.on} disabled={busy} onChange={() => act(row.on ? 'off' : 'on', row.name)} /> 开</label>
          </li>;
        })}
        {!list?.plugins.length && <li className="hint">还没有安装插件。可从下面选择官方插件，也可以添加自己的。</li>}
      </ul>
      <h4>可以安装</h4>
      <form className="plugins-add" onSubmit={(e) => { e.preventDefault(); browse(catalog); }}>
        <input aria-label="插件目录" value={catalog} onChange={(e) => setCatalog(e.target.value)} placeholder="目录 URL 或本机 index.json" />
        <button disabled={busy}>查询目录</button>
      </form>
      <small className="where">安装来源：{catalog || list?.catalog}</small>
      {marketError && <p className="plugins-error">目录暂不可用：{marketError}；已安装的插件仍可使用。</p>}
      <ul className="plugins-list">
        {available.map((item) => <li key={item.id} className="plugin-row">
          <div className="what"><div><b>{item.label}</b> <code>{item.id}</code> {item.version}</div><small>{item.description}</small>
            {item.problem && <small>{item.problem}</small>}</div>
          <button disabled={busy || !item.version || !item.supported} onClick={() => act('info', item.id, {catalog, version: item.version})}>详情</button>
          <button disabled={busy || !item.compatible || !!list?.plugins.some((p) => p.id === item.id)}
                  onClick={() => act('install', item.id, {catalog, version: item.version})}>{list?.plugins.some((p) => p.id === item.id) ? '已安装' : '安装'}</button>
        </li>)}
      </ul>
      <details><summary>开发：添加本地插件链接</summary>
        <form className="plugins-add" onSubmit={async (e) => { e.preventDefault(); if (await act('add', target.trim(), {name: name.trim() || undefined})) { setTarget(''); setName(''); } }}>
          <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="JS 文件或含 plugin.json 的插件目录" />
          <input className="as" value={name} onChange={(e) => setName(e.target.value)} placeholder="无 manifest 时可取名" />
          <button disabled={busy || !target.trim()}>添加链接</button>
        </form>
      </details>
      {error && <p className="plugins-error">{error}</p>}
      {details && <details open><summary>操作结果 / 使用说明 <button onClick={() => setDetails('')}>收起</button></summary><pre className="plugin-info">{details}</pre></details>}
      <p className="hint plugins-note">插件在当前页面运行；选择你信任的来源。{list && <>清单：<code>{list.file}</code></>}</p>
    </div>
  );
}
