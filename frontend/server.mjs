import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';

const root = resolve(process.cwd());
const host = process.env.FRONTEND_HOST || '127.0.0.1';
const port = Number(process.env.FRONTEND_PORT || 5173);
const apiOrigin = (process.env.API_ORIGIN || 'http://127.0.0.1:8000').replace(/\/$/, '');
const contentTypes = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.mjs':'text/javascript; charset=utf-8', '.svg':'image/svg+xml', '.png':'image/png', '.ico':'image/x-icon' };

async function bodyOf(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks);
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || '/', 'http://' + host);
  if (url.pathname === '/api' || url.pathname.startsWith('/api/') || url.pathname === '/health') {
    try {
      const headers = { Accept: req.headers.accept || 'application/json' };
      if (req.headers['content-type']) headers['Content-Type'] = req.headers['content-type'];
      const body = ['GET', 'HEAD'].includes(req.method || 'GET') ? undefined : await bodyOf(req);
      const upstream = await fetch(apiOrigin + url.pathname + url.search, { method: req.method, headers, body });
      res.writeHead(upstream.status, { 'Content-Type': upstream.headers.get('content-type') || 'application/json', 'Cache-Control':'no-store' });
      if (upstream.body) for await (const chunk of upstream.body) res.write(chunk);
      res.end();
    } catch (error) {
      res.writeHead(502, { 'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store' });
      res.end(JSON.stringify({ detail:'Không kết nối được API tại ' + apiOrigin + ': ' + error.message }));
    }
    return;
  }

  let pathname;
  try { pathname = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname); } catch { res.writeHead(400); res.end('Invalid path'); return; }
  const target = resolve(root, '.' + pathname);
  if (target !== root && !target.startsWith(root + sep)) { res.writeHead(403); res.end('Forbidden'); return; }
  try {
    const info = await stat(target);
    if (!info.isFile()) throw new Error('Not a file');
    const data = await readFile(target);
    res.writeHead(200, { 'Content-Type':contentTypes[extname(target)] || 'application/octet-stream', 'Cache-Control':'no-store' });
    res.end(data);
  } catch {
    res.writeHead(404, { 'Content-Type':'text/plain; charset=utf-8' });
    res.end('Not found');
  }
});

server.listen(port, host, () => console.log('La Nhà frontend: http://' + host + ':' + port + ' (API proxy: ' + apiOrigin + ')'));
