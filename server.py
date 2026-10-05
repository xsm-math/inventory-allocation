"""Local-only dashboard; no account, API key or external services required."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import math
import pandas as pd
from threading import Lock
from supplychain.network import Network
from supplychain.simulation import run_episode
SIMULATION_LOCK = Lock()
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
        routes = {'/': ('web/network.html', 'text/html; charset=utf-8'),
                  '/network': ('web/network.html', 'text/html; charset=utf-8'),
                  '/single-period': ('web/index.html', 'text/html; charset=utf-8'),
                  '/api/network-results': ('results/network/report.json', 'application/json; charset=utf-8'),
                  '/figures/policy_comparison.svg': ('results/network/policy_comparison.svg', 'image/svg+xml'),
                  '/figures/trajectories.svg': ('results/network/trajectories.svg', 'image/svg+xml')}
        item = routes.get(self.path)
        if item is None:
            self.reply(404, b'Not found', 'text/plain')
            return
        path, kind = item
        if not (ROOT/path).exists():
            self.reply(404, b'Run python -m supplychain.benchmark first', 'text/plain')
            return
        self.reply(200, (ROOT/path).read_bytes(), kind)
    def do_POST(self):
        if self.path == '/api/network-run':
            self.network_run()
            return
        if self.path != '/api/solve':
            self.reply(404, b'{}')
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request size')
            config = json.loads(self.rfile.read(length))
            if not isinstance(config, dict):
                raise ValueError('Expected a JSON object')
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

    def network_run(self):
        acquired = False
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 4096:
                raise ValueError('Invalid request size')
            config = json.loads(self.rfile.read(length))
            if not isinstance(config, dict):
                raise ValueError('Expected a JSON object')
            seed = config.get('seed', 101)
            days = config.get('days', 21)
            horizon = config.get('horizon', 5)
            for v, low, high in [(seed,0,100000),(days,7,28),(horizon,3,7)]:
                if isinstance(v,bool) or not isinstance(v,int) or not low<=v<=high:
                    raise ValueError('Seed, days or horizon outside supported bounds')
            policy = config.get('policy', 'mpc_buffered')
            regime = config.get('regime', 'normal')
            if policy not in ('base_stock','mpc','mpc_buffered','mpc_safety') or regime not in ('normal','surge','supply_shock'):
                raise ValueError('Unknown policy or regime')
            acquired = SIMULATION_LOCK.acquire(blocking=False)
            if not acquired:
                self.reply(429, b'{"error":"A simulation is already running"}')
                return
            result = run_episode(Network.load(), seed, days, regime, policy, horizon, time_limit=.5, capture=True)
            self.reply(200, json.dumps(result, allow_nan=False).encode())
        except (ValueError, TypeError, KeyError) as exc:
            self.reply(400, json.dumps({'error':str(exc)}).encode())
        finally:
            if acquired:
                SIMULATION_LOCK.release()

if __name__ == '__main__':
    print('Inventory Network Study: http://127.0.0.1:8000', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8000), Handler).serve_forever()
