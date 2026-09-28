"""Local-only dashboard; no account, API key or external services required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import math
import pandas as pd
from allocation import run_case
ROOT = Path(__file__).resolve().parent

class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, kind='application/json; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        if self.path != '/':
            self.reply(404, b'Not found', 'text/plain')
            return
        self.reply(200, (ROOT/'web/index.html').read_bytes(), 'text/html; charset=utf-8')
    def do_POST(self):
        if self.path != '/api/solve':
            self.reply(404, b'{}')
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request size')
            config = json.loads(self.rfile.read(length))
            stock = float(config.get('stock', 620))
            floor = float(config.get('floor', .25))
            scale = float(config.get('scale', 1))
            if not all(map(math.isfinite, [stock, floor, scale])) or not 0 <= stock <= 10000 or stock != int(stock) or not .1 <= scale <= 3:
                raise ValueError('Invalid stock or demand scale')
            data = pd.read_csv(ROOT/'data/channels.csv')
            rows = data[data.sku == config.get('sku', 'Camera-A')].reset_index(drop=True)
            if rows.empty:
                raise ValueError('Unknown SKU')
            result = run_case(rows, int(stock), floor, scale=scale)
            result['channels'] = rows.to_dict(orient='records')
            self.reply(200, json.dumps(result, allow_nan=False).encode())
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, json.dumps({'error': str(exc)}).encode())

if __name__ == '__main__':
    print('Inventory Allocation Lab: http://127.0.0.1:8000', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
