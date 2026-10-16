// 插件的栏位：出错保护——插件的组件出错只在它自己那块写一句
import {Component} from 'react';
import type {ReactNode} from 'react';
import {getState, setState} from '../store';
import {toast} from '../sync';
import {CAPTURE} from '../params';

// 插件出错：记进「插件」小窗（同一个插件只记一次、只提示一次），不影响视图和别的插件
const reported = new Set<string>();
export function pluginFailed(name: string, error: unknown) {
  const text = '出错了：' + ((error as Error)?.message || String(error));
  if (CAPTURE && [getState().view, getState().side].includes(name)) {
    window.__layerweaveError = `插件 ${name} ${text}`;
    window.__layerweaveReady = false;
  }
  console.warn(`插件「${name}」`, error);
  if (reported.has(name + text)) return;
  reported.add(name + text);
  setState({pluginErrors: {...getState().pluginErrors, [name]: text}});
  toast(`插件「${name}」${text}`, 6000);
}

export class PluginBoundary extends Component<{name: string; children: ReactNode}, {error: string | null}> {
  state = {error: null as string | null};
  static getDerivedStateFromError(error: Error) { return {error: error?.message || String(error)}; }
  componentDidCatch(error: Error) { pluginFailed(this.props.name, error); }
  render() {
    if (this.state.error) return <p className="plugin-crash">插件「{this.props.name}」出错了：{this.state.error}</p>;
    return this.props.children;
  }
}
