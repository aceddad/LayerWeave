// Record the actual production bundle's dependencies, using installed license files.
import {readFileSync, writeFileSync, existsSync, readdirSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const destination = fileURLToPath(new URL('../../../THIRD_PARTY_NOTICES.md', import.meta.url));

export default function thirdPartyNotices() {
  return {
    name: 'third-party-notices',
    apply: 'build',
    generateBundle(_options, bundle) {
      const packages = new Map();
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== 'chunk') continue;
        for (const id of Object.keys(chunk.modules)) {
          if (!id.replaceAll('\\', '/').includes('/node_modules/')) continue;
          let folder = dirname(resolve(id.split('?')[0].replace(/^\0/, '')));
          while (dirname(folder) !== folder) {
            const manifest = join(folder, 'package.json');
            if (existsSync(manifest)) {
              const meta = JSON.parse(readFileSync(manifest, 'utf8'));
              if (meta.name && meta.version) {
                packages.set(`${meta.name}@${meta.version}`, {folder, meta});
                break;
              }
            }
            folder = dirname(folder);
          }
        }
      }
      const sections = ['# Third-party notices', '',
        'Generated from the packages included in the view production bundle by `npm run build`.',
        'The following components retain their own licenses. This notice does not relicense them.',
        'Python optional dependencies and separately installed plugins/skills retain their respective notices.', ''];
      for (const [name, {folder, meta}] of [...packages].sort(([a], [b]) => a.localeCompare(b))) {
        const files = readdirSync(folder).filter(name => /^(licen[sc]e|copying|notice)(\..*)?$/i.test(name)).sort();
        if (!files.length) throw new Error(`No license text found for bundled ${name}`);
        sections.push(`## ${name}`, '', `Declared license: ${typeof meta.license === 'string' ? meta.license : JSON.stringify(meta.license)}`, '');
        for (const file of files) sections.push(`### ${file}`, '', '```text', readFileSync(join(folder, file), 'utf8').trim(), '```', '');
      }
      if (!packages.size) throw new Error('No production dependencies found for third-party notices');
      writeFileSync(destination, sections.join('\n').replace(/\r\n?/g, '\n'));
      this.info(`Recorded third-party license texts for ${packages.size} bundled packages`);
    },
  };
}
