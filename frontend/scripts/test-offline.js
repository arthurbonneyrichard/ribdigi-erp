/* Compiles the POS offline modules and their node:test suites, then runs them. */
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const root = path.resolve(__dirname, '..');
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'ribdigi-offline-test-'));
const tests = [
  'lib/connectivity.test.ts',
  'lib/formatSession.test.ts',
  'lib/posOffline.test.ts',
  'lib/posOfflineQueue.test.ts',
];

try {
  execFileSync(
    process.execPath,
    [
      require.resolve('typescript/bin/tsc'),
      '--outDir', out,
      '--rootDir', root,
      '--module', 'commonjs',
      '--target', 'es2022',
      '--lib', 'es2022,dom',
      '--types', 'node',
      '--strict',
      '--esModuleInterop',
      '--skipLibCheck',
      ...tests.map((t) => path.join(root, t)),
    ],
    { stdio: 'inherit', cwd: root }
  );
  execFileSync(
    process.execPath,
    ['--test', '--test-concurrency=1', ...tests.map((t) => path.join(out, t.replace(/\.ts$/, '.js')))],
    {
      stdio: 'inherit',
      cwd: out,
      env: { ...process.env, NODE_PATH: path.join(root, 'node_modules'), RIBDIGI_FRONTEND_ROOT: root },
    }
  );
} finally {
  fs.rmSync(out, { recursive: true, force: true });
}
