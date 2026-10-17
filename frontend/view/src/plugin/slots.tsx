import {ui, tr, useI18n} from '../i18n';
// 插件的栏位：出错保护——插件的组件出错只在它自己那块写一句
import {Component} from 'react';
import type {ReactNode} from 'react';
import {getState, setState} from '../store';
import {toast} from '../sync';
import {CAPTURE} from '../params';

// 插件出错：记进「插件」小窗（同一个插件只记一次、只提示一次），不影响视图和别的插件
const reported = new Set<string>();
export function pluginFailed(name: string, error: unknown) {
  const text = tr("plugin.errorPrefix") + ((error as Error)?.message || String(error));
  if (CAPTURE && [getState().view, getState().side].includes(name)) {
    window.__layerweaveError = tr("plugin.problem.variant", {value1: name, value2: text});
    window.__layerweaveReady = false;
  }
  console.warn(tr("plugin.name", {value1: name}), error);
  if (reported.has(name + text)) return;
  reported.add(name + text);
  setState({pluginErrors: {...getState().pluginErrors, [name]: text}});
  toast(ui("plugin.problem", {value1: name, value2: text}), 6000);
}

export class PluginBoundary extends Component<{name: string; children: ReactNode}, {error: string | null}> {
  state = {error: null as string | null};
  static getDerivedStateFromError(error: Error) { return {error: error?.message || String(error)}; }
  componentDidCatch(error: Error) { pluginFailed(this.props.name, error); }
  render() {
    if (this.state.error) return <PluginCrash name={this.props.name} error={this.state.error} />;
    return this.props.children;
  }
}

function PluginCrash({name, error}: {name: string; error: string}) {
  useI18n();
  return <p className="plugin-crash">{tr("plugin.problem", {value1: name, value2: error})}</p>;
}
