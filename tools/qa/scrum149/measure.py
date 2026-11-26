"""Mide respuestas HTTP completas del backend QA con consultas a las bases reales."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import platform
from pathlib import Path
import statistics
import subprocess
import sys
import time

import requests
from qa_env import BACKEND_VARIABLES, require_env

ROOT = Path(__file__).resolve().parents[3]
BASE = 'http://127.0.0.1:8000'
PRODUCTS = '/api/catalogo/productos/'
SCENARIOS = {
    'products': PRODUCTS + '?page=1&page_size=24&orden=destacados',
    'category': PRODUCTS + '?categoria=Categoria+00',
    'number': PRODUCTS + '?categoria=Categoria+00&atributo_capacidad_gb=128',
    'text': PRODUCTS + '?categoria=Categoria+00&atributo_color=Verde',
    'price_asc': PRODUCTS + '?orden=precio-asc',
    'price_desc': PRODUCTS + '?orden=precio-desc',
    'middle': PRODUCTS + '?page=23',
    'last': PRODUCTS + '?page=45',
    'filters': '/api/catalogo/filtros/',
    'configuration': '/api/configuracion/',
    'legal': '/api/ventas/paginas-legales/',
}


def sample(path):
    start = time.perf_counter()
    try:
        response = requests.get(BASE + path, timeout=30)
        elapsed = (time.perf_counter() - start) * 1000
        return {'ms': elapsed, 'ttfb_ms': response.elapsed.total_seconds() * 1000,
                'status': response.status_code, 'bytes': len(response.content)}
    except requests.RequestException as exc:
        return {'ms': (time.perf_counter() - start) * 1000, 'status': 0,
                'error': type(exc).__name__}


def summarize(samples):
    values = sorted(s['ms'] for s in samples)
    return {'n': len(values), 'median_ms': round(statistics.median(values), 3),
            'p95_ms': round(values[math.ceil(len(values) * .95) - 1], 3),
            'max_ms': round(max(values), 3),
            'errors': sum(s['status'] != 200 for s in samples)}


def start_backend(log):
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('manage.py')),
                                'runserver', '127.0.0.1:8000', '--noreload'],
                               cwd=ROOT, stdout=log, stderr=log)
    for _ in range(150):
        if process.poll() is not None:
            raise RuntimeError('El servidor QA terminó; revise el registro temporal del backend')
        try:
            if requests.get(BASE + '/', timeout=.5).status_code == 200:
                return process
        except requests.RequestException:
            pass
        time.sleep(.1)
    process.terminate()
    raise RuntimeError('El servidor QA no llegó a estar disponible')


def measure(args):
    require_env(BACKEND_VARIABLES)
    # No detener ni reutilizar servicios ajenos en el puerto de medición.
    try:
        requests.get(BASE + '/', timeout=1)
    except requests.ConnectionError:
        pass
    else:
        raise RuntimeError('El puerto 8000 está ocupado; detenga primero solo el servidor QA correspondiente')
    initial = [SCENARIOS['products'], SCENARIOS['configuration'], SCENARIOS['legal']]
    if args.graph == 'baseline':
        initial += [SCENARIOS['filters'], SCENARIOS['configuration'], SCENARIOS['configuration']]
    result = {'phase': args.phase, 'graph': initial,
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
              'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                              'processor': platform.processor(), 'backend': 'Django runserver --noreload DEBUG=True',
                              'postgres': '15 Docker 55439', 'mongo': '6 Docker 27049',
                              'standard': 'localhost, un visitante, sin limitación artificial'},
              'fixture': json.loads((ROOT / '.tmp/scrum149/fixture.json').read_text()),
              'warmup_count': 5, 'cold': [], 'series': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix('.backend.log').open('w', encoding='utf-8') as log, ThreadPoolExecutor(max_workers=6) as pool:
        def initial_sample():
            start = time.perf_counter()
            responses = list(pool.map(sample, initial))
            return {'ms': (time.perf_counter() - start) * 1000,
                    'status': 200 if all(r['status'] == 200 for r in responses) else 0,
                    'responses': responses}
        for i in range(args.cold):
            process = start_backend(log)
            try:
                result['cold'].append(initial_sample())
            finally:
                process.terminate()
                process.wait(timeout=10)
        process = start_backend(log)
        try:
            for series in range(args.series):
                scenarios = {}
                for name, path in SCENARIOS.items():
                    for _ in range(5):
                        sample(path)
                    scenarios[name] = [sample(path) for _ in range(args.repetitions)]
                for _ in range(5):
                    initial_sample()
                scenarios['initial_bundle'] = [initial_sample() for _ in range(args.repetitions)]
                result['series'].append(scenarios)
                print(json.dumps({'series': series + 1,
                                  'summary': {k: summarize(v) for k, v in scenarios.items()}}), flush=True)
        finally:
            process.terminate()
            process.wait(timeout=10)
    result['summary'] = {name: summarize([s for series in result['series'] for s in series[name]])
                         for name in (*SCENARIOS, 'initial_bundle')} if result['series'] else {}
    if result['cold']:
        result['cold_summary'] = summarize(result['cold'])
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, help='Identificador de esta ejecución')
    parser.add_argument('--graph', choices=('baseline', 'optimized'), required=True, help='Grafo inicial histórico u optimizado')
    parser.add_argument('--output', type=Path, required=True, help='Archivo JSON de muestras temporales')
    parser.add_argument('--cold', type=int, default=10, help='Primeras cargas con reinicio de Django')
    parser.add_argument('--series', type=int, default=3, help='Cantidad de series posteriores al calentamiento')
    parser.add_argument('--repetitions', type=int, default=30, help='Muestras por escenario y serie')
    measure(parser.parse_args())
