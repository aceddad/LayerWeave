// 顶栏「插件」小窗：本机插件清单，和 view_plugin 命令改的是同一份。看哪些载入了、开关、去掉链接、加链接。
// 加链接给人做二次开发用：把自己正在写的插件链接进来，改完再点开这个小窗（或刷新页面）就换成新的
import {useEffect, useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {api} from './api';
import {pluginApplies, refreshPlugins} from './plugin/registry';
import {useModel, useStore} from './store';
import {toast} from './sync';
import type {PluginRow} from './types';

type Action = 'add' | 'remove' | 'on' | 'off';

export function PluginManager({onClose}: {onClose: () => void}) {
  const model = useModel();
  const {list, plugins, errors} = useStore(useShallow((s) => ({list: s.pluginList, plugins: s.plugins, errors: s.pluginErrors})));
  const [target, setTarget] = useState(''), [name, setName] = useState('');
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => { refreshPlugins(); }, []);   // 打开时重读：插件文件改过、命令改过清单，都在这里跟上
  useEffect(() => {
    const away = (e: MouseEvent) => {
      const el = e.target as Element;
      if (!box.current?.contains(el) && !el.closest?.('.plugin-toggle')) onClose();
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc); };
  }, [onClose]);

  const act = async (action: Action, what: string, as?: string) => {
    setBusy(true); setError('');
    try {
      const result = await api.plugin({action, target: what, ...(as ? {name: as} : {})});
      if (result.recorded === false) { toast('这个页面不改插件清单（截图用的页面）'); return false; }
      await refreshPlugins();
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally { setBusy(false); }
  };

  const add = async () => {
    if (await act('add', target.trim(), name.trim() || undefined)) { setTarget(''); setName(''); }
  };

  // 每一行的状态：有问题 > 关着 > 没载入上 > 这个项目用不上 > 载入了
  const status = (row: PluginRow): [string, string] => {
    if (row.problem) return ['bad', row.problem];
    if (!row.on) return ['off', '关着'];
    if (errors[row.name]) return ['bad', errors[row.name]];
    const p = plugins.find((x) => x.name === row.name);
    if (!p) return ['wait', '正在载入'];
    if (!pluginApplies(p, model)) return ['idle', '这个项目里没有它管的对象，所以顶栏上不出现'];
    return ['ok', '载入了'];
  };

  return (
    <div className="plugins-box" ref={box}>
      <div className="plugins-head"><b>插件</b><span className="hint">清单在本机，软件更新不会冲掉</span></div>
      {list?.problem && <p className="plugins-error">{list.problem}</p>}
      <ul className="plugins-list">
        {(list?.plugins ?? []).map((row) => {
          const [cls, text] = status(row), p = plugins.find((x) => x.name === row.name);
          return (
            <li key={row.name} className={`plugin-row ${cls}`}>
              <span className="dot" title={text} />
              <div className="what">
                <div>{p ? <><b>{p.label}</b> <code>{row.name}</code></> : <b>{row.name}</b>}</div>
                <small className="where" title={row.path}>{row.source === 'builtin' ? '内置' : row.path}</small>
                {(row.about || p?.title) && <small>{row.about || p?.title}</small>}
                {cls !== 'ok' && <small className="state">{text}</small>}
              </div>
              <label className="toggle" title={row.on ? '关掉：顶栏和键盘都不再用它' : '开'}>
                <input type="checkbox" checked={row.on} disabled={busy} onChange={() => act(row.on ? 'off' : 'on', row.name)} /> 开
              </label>
              {row.source === 'link'
                ? <button disabled={busy} title="只删清单里的这一行，不删文件" onClick={() => act('remove', row.name)}>去掉</button>
                : <span className="keep" title="内置的去不掉，不想用就关掉">　</span>}
            </li>
          );
        })}
        {list && !list.plugins.length && <li className="hint">还没有插件</li>}
      </ul>
      <form className="plugins-add" onSubmit={(e) => { e.preventDefault(); add(); }}>
        <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="js 文件或文件夹的路径；放在默认文件夹里的只写名字"
               title={list ? `只写名字时，找的是 ${list.folder} 下面的 <名字>/plugin.js` : ''} />
        <input className="as" value={name} onChange={(e) => setName(e.target.value)} placeholder="名字（可不填）"
               title="小写字母开头；省略时用文件夹名或文件名。截图 --view、链接里的 view= 用这个名字" />
        <button disabled={busy || !target.trim()}>加上</button>
      </form>
      {error && <p className="plugins-error">{error}</p>}
      <p className="hint plugins-note">
        插件是在这个页面里运行的代码：能读项目，能写批注和折叠。只加信得过的。<br />
        也可以用命令 <code>view_plugin add 路径</code>，或者告诉 AI。{list && <>清单：<code>{list.file}</code></>}
      </p>
    </div>
  );
}
