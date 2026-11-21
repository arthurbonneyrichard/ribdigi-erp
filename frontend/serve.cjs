'use strict';
// Production entry point: starts the Next.js standalone server (server.js) with
// less framework disclosure (security control 09).
//
// - Drops headers that only advertise Next.js. x-nextjs-cache is informational.
//   x-nextjs-prerender and x-nextjs-stale-time are read by the client router on
//   RSC navigation fetches, so they are kept there and removed only from full
//   page responses.
// - Refuses TRACE / TRACK with a plain 405 (Next answered them with a 500).
const http = require('http');

const ALWAYS_DROP = ['x-powered-by', 'x-nextjs-cache'];
const PAGE_DROP = ['x-nextjs-prerender', 'x-nextjs-stale-time'];

function isRscRequest(req) {
  if (!req || !req.headers) return false;
  return req.headers.rsc === '1' || 'next-router-prefetch' in req.headers || 'next-router-state-tree' in req.headers;
}

function dropListFor(req) {
  return isRscRequest(req) ? ALWAYS_DROP : ALWAYS_DROP.concat(PAGE_DROP);
}

function filterHeaderArg(arg, drop) {
  if (!arg || typeof arg !== 'object') return arg;
  if (Array.isArray(arg)) {
    if (arg.length && Array.isArray(arg[0])) {
      return arg.filter((pair) => !drop.includes(String(pair[0]).toLowerCase()));
    }
    const out = [];
    for (let i = 0; i + 1 < arg.length; i += 2) {
      if (!drop.includes(String(arg[i]).toLowerCase())) out.push(arg[i], arg[i + 1]);
    }
    return out;
  }
  const out = {};
  for (const key of Object.keys(arg)) {
    if (!drop.includes(key.toLowerCase())) out[key] = arg[key];
  }
  return out;
}

// In CSP report-only mode the proxy hands the old enforced policy over in x-csp-enforced (Next.js
// would otherwise read it instead of the nonce policy). Set it as the real header here, after rendering.
const HANDOFF = 'x-csp-enforced';

const originalWriteHead = http.ServerResponse.prototype.writeHead;
http.ServerResponse.prototype.writeHead = function writeHead(statusCode, ...rest) {
  const drop = dropListFor(this.req);
  if (!this.headersSent) {
    for (const name of drop) this.removeHeader(name);
    const handoff = this.getHeader(HANDOFF);
    if (handoff) {
      this.removeHeader(HANDOFF);
      this.setHeader('Content-Security-Policy', String(handoff));
    }
  }
  if (rest.length) rest[rest.length - 1] = filterHeaderArg(rest[rest.length - 1], drop.concat([HANDOFF]));
  return originalWriteHead.call(this, statusCode, ...rest);
};

const BLOCKED_METHODS = new Set(['TRACE', 'TRACK']);
const originalEmit = http.Server.prototype.emit;
http.Server.prototype.emit = function emit(event, req, res, ...rest) {
  if (event === 'request' && req && res && BLOCKED_METHODS.has(String(req.method).toUpperCase())) {
    const body = 'Method Not Allowed';
    res.writeHead(405, {
      Allow: 'GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS',
      'Content-Type': 'text/plain; charset=utf-8',
      'Content-Length': Buffer.byteLength(body),
    });
    res.end(body);
    return true;
  }
  return originalEmit.call(this, event, req, res, ...rest);
};

require('./server.js');
