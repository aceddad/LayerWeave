import {tr, useI18n, currentLocale, renderMessage} from './i18n';
// 本机管理与市场共用 view_plugin；查看目录不会安装，官方插件也按用户选择安装。
import {useEffect, useRef, useState} from 'react';
import {useShallow} from 'zustand/react/shallow';
import {api, ViewApiError} from './api';
import type {Localizations, UiMessage} from './i18n/types';
import {pluginApplies, refreshPlugins} from './plugin/registry';
import {useModel, useStore} from './store';
import type {MarketItem, PluginRow, PluginResult} from './types';

export function PluginManager({onClose}: {onClose: () => void}) {
  useI18n();
  const model = useModel();
  const {list, plugins, errors} = useStore(useShallow((s) => ({list: s.pluginList, plugins: s.plugins, errors: s.pluginErrors})));
  const [target, setTarget] = useState(''), [name, setName] = useState('');
  const [catalog, setCatalog] = useState(list?.catalog ?? '');
  const [market, setMarket] = useState<MarketItem[]>([]), [marketError, setMarketError] = useState<string | UiMessage>('');
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | UiMessage>(''), [details, setDetails] = useState<PluginResult | null>(null);
  const box = useRef<HTMLDivElement>(null);

  const browse = async (source?: string) => {
    setMarketError('');
    try {
      const result = await api.plugin({action: 'market', catalog: source || undefined});
      if (result.recorded === false) return;
      setMarket(result.items ?? []); setCatalog(result.catalog);
      if (result.issues?.length) setMarketError(result.issues.map((i) => i.message).join('；'));
    } catch (e) { setMarketError(e instanceof ViewApiError ? e.ui ?? e.message : String(e)); }
  };
  useEffect(() => { refreshPlugins(); browse(list?.catalog); }, []);
  useEffect(() => {
    const away = (e: MouseEvent) => {
      const el = e.target as Element;
      if (!box.current?.contains(el) && !el.closest?.('.plugin-toggle, .language')) onClose();
    };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', away); document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', away); document.removeEventListener('keydown', esc); };
  }, [onClose]);

  const act = async (action: string, what?: string, extra: {name?: string; catalog?: string; version?: string; files?: boolean} = {}) => {
    setBusy(true); setError('');
    try {
      const result = await api.plugin({action, target: what, ...extra});
      if (result.recorded === false) { setError(tr("plugins.captureReadOnly")); return false; }
      if (action === 'info' || result.status === 'failed' || result.status === 'migrated' || result.issues?.length) setDetails(result);
      await refreshPlugins();
      if (['install', 'update', 'remove'].includes(action)) await browse(catalog);
      return result.status !== 'failed';
    } catch (e) { setError(e instanceof ViewApiError ? e.ui ?? e.message : String(e)); return false; }
    finally { setBusy(false); }
  };

  const status = (row: PluginRow): [string, string] => {
    if (row.problem) return ['bad', row.problem_ui ? renderMessage(row.problem_ui) : row.problem];
    if (!row.on) return ['off', tr("plugins.installedDisabled")];
    if (errors[row.name]) return ['bad', tr("plugins.installedFailed") + errors[row.name]];
    const p = plugins.find((x) => x.name === row.name);
    if (!p) return ['wait', tr("plugins.loading")];
    if (!pluginApplies(p, model)) return ['idle', tr("plugins.noMatchingObjects")];
    return ['ok', tr("plugins.loaded")];
  };
  const available: MarketItem[] = market.length ? market : (list?.recommended ?? []).map((r) => ({...r, version: '', supported: true, compatible: false, problem: tr("plugins.awaitCatalog")}));

  return (
    <div className="plugins-box" ref={box}>
      <div className="plugins-head"><b>{tr("plugins.title")}</b><span className="hint">{tr("plugins.optional")}</span></div>
      {list?.problem && <p className="plugins-error">{list.problem}</p>}
      {list?.migration_issues.map((issue, i) => <p key={i} className="plugins-error">{tr("plugins.legacyIssue")}{issue.problem}</p>)}
      {list?.migration_pending && <p className="plugins-error">{tr("plugins.migrationHint")}
        <button disabled={busy} onClick={() => act('migrate')}>{tr("plugins.migrate")}</button></p>}
      <ul className="plugins-list">
        {(list?.plugins ?? []).map((row) => {
          const [cls, text] = status(row);
          return <li key={row.name} className={`plugin-row ${cls}`}>
            <span className="dot" title={text} />
            <div className="what"><div><b>{displayOf(row).label ?? row.label}</b> <code>{row.name}</code> {row.version}</div>
              <small className="where" title={row.path}>{row.source === 'managed' ? tr("plugins.package") : tr("plugins.devLink")} · {row.path}</small>
              {row.about && <small>{displayOf(row).description ?? row.about}</small>}
              {row.language_warnings?.map((warning) => <small key={warning}>{tr("plugins.languageWarning")}: {warning}</small>)}<small className="state">{text}</small>
              <button disabled={busy} onClick={() => act('info', row.name)}>{tr("plugins.help")}</button>
              {row.source === 'managed' && <button disabled={busy} onClick={() => act('update', row.name)}>{tr("plugins.update")}</button>}
              <button disabled={busy} title={tr("plugins.removeHint")} onClick={() => act('remove', row.name)}>{tr("plugins.remove")}</button>
              {row.source === 'managed' && <button disabled={busy} title={tr("plugins.uninstallHint")} onClick={() => act('remove', row.name, {files: true})}>{tr("plugins.uninstall")}</button>}
            </div>
            <label className="toggle"><input type="checkbox" checked={row.on} disabled={busy} onChange={() => act(row.on ? 'off' : 'on', row.name)} />  {tr("plugins.enabled")}</label>
          </li>;
        })}
        {!list?.plugins.length && <li className="hint">{tr("plugins.empty")}</li>}
      </ul>
      <h4>{tr("plugins.available")}</h4>
      <form className="plugins-add" onSubmit={(e) => { e.preventDefault(); browse(catalog); }}>
        <input aria-label={tr("plugins.catalog")} value={catalog} onChange={(e) => setCatalog(e.target.value)} placeholder={tr("plugins.catalogPlaceholder")} />
        <button disabled={busy}>{tr("plugins.query")}</button>
      </form>
      <small className="where">{tr("plugins.source")}{catalog || list?.catalog}</small>
      {marketError && <p className="plugins-error">{tr("plugins.catalogUnavailable")}{renderMessage(marketError)}{tr("plugins.installedStillWork")}</p>}
      <ul className="plugins-list">
        {available.map((item) => <li key={item.id} className="plugin-row">
          <div className="what"><div><b>{displayOf(item).label ?? item.label}</b> <code>{item.id}</code> {item.version}</div><small>{displayOf(item).description ?? item.description}</small>
            {item.problem && <small>{item.problem}</small>}</div>
          <button disabled={busy || !item.version || !item.supported} onClick={() => act('info', item.id, {catalog, version: item.version})}>{tr("plugins.details")}</button>
          <button disabled={busy || !item.compatible || !!list?.plugins.some((p) => p.id === item.id)}
                  onClick={() => act('install', item.id, {catalog, version: item.version})}>{list?.plugins.some((p) => p.id === item.id) ? tr("plugins.installed") : tr("plugins.install")}</button>
        </li>)}
      </ul>
      <details><summary>{tr("plugins.addDev")}</summary>
        <form className="plugins-add" onSubmit={async (e) => { e.preventDefault(); if (await act('add', target.trim(), {name: name.trim() || undefined})) { setTarget(''); setName(''); } }}>
          <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder={tr("plugins.pathPlaceholder")} />
          <input className="as" value={name} onChange={(e) => setName(e.target.value)} placeholder={tr("plugins.namePlaceholder")} />
          <button disabled={busy || !target.trim()}>{tr("plugins.addLink")}</button>
        </form>
      </details>
      {error && <p className="plugins-error">{renderMessage(error)}</p>}
      {details && <details open><summary>{tr("plugins.result")} <button onClick={() => setDetails(null)}>{tr("common.collapse")}</button></summary><PluginDetails result={details} /></details>}
      <p className="hint plugins-note">{tr("plugins.trustHint")}{list && <>{tr("plugins.listFile")}<code>{list.file}</code></>}</p>
    </div>
  );
}

function displayOf(value: {localizations?: Localizations}) {
  return {...value.localizations?.zh?.display, ...value.localizations?.[currentLocale()]?.display};
}

function PluginDetails({result}: {result: PluginResult}) {
  const {locale} = useI18n();
  const meta = result.manifest, display = displayOf(result);
  const usage = result.localizations?.[locale]?.usage_text ?? result.localizations?.zh?.usage_text ?? result.usage;
  const statusKey = 'plugins.status.' + result.status;
  const status = tr(statusKey) === statusKey ? result.status : tr(statusKey);
  return <div className="plugin-info">
    {status && <p>{tr('plugins.resultStatus', {status})}</p>}
    {meta && <>
      <h4>{display.label ?? meta.label} <code>{meta.id}</code> {meta.version}</h4>
      <p>{display.description ?? meta.description}</p>
      <p>{tr('plugins.requirements')}: <code>{JSON.stringify(meta.requires)}</code></p>
      <h4>{tr('plugins.parameters')}</h4>
      <dl>{Object.entries(meta.params ?? {}).map(([name, spec]) => <div key={name}>
        <dt><code>{name}</code> · {spec.type}{spec.required ? ' *' : ''}{'default' in spec ? ' = ' + JSON.stringify(spec.default) : ''}</dt>
        <dd>{display.params?.[name] ?? spec.description}</dd>
      </div>)}</dl>
    </>}
    {result.issues?.map((issue, i) => <p key={i}>{tr('error.request')} {issue.message}</p>)}
    {result.language_warnings?.map((warning) => <p key={warning}>{tr('plugins.languageWarning')}: {warning}</p>)}
    {usage && <><h4>{tr('plugins.usage')}</h4><pre>{meta === null ? tr('plugins.noManifest') : usage}</pre></>}
  </div>;
}
