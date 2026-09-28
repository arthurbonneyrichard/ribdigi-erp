const fs = require('fs');
const path = require('path');

function copy(src, dest) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
}

const standalone = path.join('.next', 'standalone');
if (!fs.existsSync(path.join(standalone, 'server.js'))) {
  console.error('prepare-standalone: missing .next/standalone/server.js');
  process.exit(1);
}

copy(path.join('.next', 'static'), path.join(standalone, '.next', 'static'));
copy('public', path.join(standalone, 'public'));
copy('guides', path.join(standalone, 'guides'));
