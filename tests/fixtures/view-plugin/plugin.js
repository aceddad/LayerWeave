// 宿主离线验收专用，不随 wheel 分发。
import {label} from './parts/label.js';
export default function(host) {
  host.addStyle('.fixture-page { padding: 30px; color: var(--text); }');
  function Page() {
    const {model} = host.useView();
    host.React.useEffect(() => { if (model) host.markReady(); }, [model]);
    return host.React.createElement('main', {className: 'fixture-page'}, label + ' ' + (new URLSearchParams(location.search).get('ids') || ''));
  }
  return {label, page: Page, side: Page, objectDetail: Page};
}
