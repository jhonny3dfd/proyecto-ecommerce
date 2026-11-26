"""Recalcula los CSV y contrasta las cifras publicadas en la guía, solo con la biblioteca estándar."""
import argparse
from collections import defaultdict
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = ROOT / 'docs/evidencias/scrum-149/procedencia.json'
DEFAULT_GUIDE = ROOT / 'docs/scrum-149-qa.md'
FIELDS = ['scenario', 'series', 'sample', 'elapsed_ms', 'status', 'error']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def csv_hash(path):
    # Git puede convertir LF a CRLF; el contenido lógico UTF-8 debe ser idéntico.
    return hashlib.sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()


def summarize(samples):
    values = sorted(row['ms'] for row in samples)
    require(bool(values), 'No hay muestras para calcular estadísticos')
    return (len(values), statistics.median(values), values[math.ceil(.95 * len(values)) - 1],
            max(values), sum(row['status'] != 200 for row in samples))


def read_samples(folder, run):
    path = folder / run['csv']
    require(path.parent.resolve() == folder.resolve(), 'El CSV debe estar junto al manifiesto')
    require(csv_hash(path) == run['csv_sha256_utf8_lf'], f'El CSV no coincide con su huella: {path.name}')
    reader = csv.DictReader(io.StringIO(path.read_text(encoding='utf-8')))
    require(reader.fieldnames == FIELDS, f'Columnas CSV incorrectas: {path.name}')
    groups = defaultdict(list)
    keys = set()
    indexes = defaultdict(list)
    for row in reader:
        scenario = row['scenario']
        series, index, status = (int(row[key]) for key in ('series', 'sample', 'status'))
        elapsed = float(row['elapsed_ms'])
        require(math.isfinite(elapsed) and elapsed >= 0, f'Tiempo inválido: {path.name}')
        require(status == 0 or 100 <= status <= 599, f'Estado HTTP inválido: {path.name}')
        require(series >= 0 and index > 0, f'Índices inválidos: {path.name}')
        require((series == 0) == (scenario == 'first_process_requests'), f'Serie inicial incorrecta: {path.name}')
        key = (scenario, series, index)
        require(key not in keys, f'Muestra duplicada: {path.name} {key}')
        keys.add(key)
        indexes[scenario, series].append(index)
        groups[scenario].append({'ms': elapsed, 'status': status})
    require({key: len(rows) for key, rows in groups.items()} == run['sample_counts'],
            f'Cantidad de muestras distinta del manifiesto: {path.name}')
    for scenario in groups:
        expected_series = [0] if scenario == 'first_process_requests' else list(range(1, run['series'] + 1))
        actual_series = sorted(series for name, series in indexes if name == scenario)
        require(actual_series == expected_series, f'Series incompletas: {path.name} {scenario}')
        count = run['cold'] if scenario == 'first_process_requests' else run['repetitions']
        for series in expected_series:
            require(sorted(indexes[scenario, series]) == list(range(1, count + 1)),
                    f'Secuencia de muestras incompleta: {path.name} {scenario}')
    return {key: summarize(rows) for key, rows in groups.items()}


def guide_table(guide, marker):
    token = f'<!-- evidencia:{marker} -->'
    require(guide.count(token) == 1, f'Marcador ausente o duplicado en la guía: {marker}')
    block = guide.split(token, 1)[1].lstrip().split('\n\n', 1)[0]
    lines = block.splitlines()
    require(len(lines) >= 3 and all(line.startswith('|') for line in lines), f'Tabla inválida: {marker}')
    rows = [[cell.strip() for cell in line.strip('|').split('|')] for line in lines]
    require(len(rows[0]) == 6 and all(word in cell.lower() for word, cell in
            zip(('muestras', 'mediana', 'p95', 'máximo', 'errores'), rows[0][1:])),
            f'Cabecera de estadísticos incompleta: {marker}')
    result = {}
    for row in rows[2:]:
        require(len(row) == 6 and row[0] not in result, f'Fila inválida o duplicada en la guía: {marker}')
        result[row[0]] = row[1:]
    return result


def check(manifest_path=DEFAULT_MANIFEST, guide_path=DEFAULT_GUIDE):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    require(manifest['units'] == 'ms', 'Las unidades deben ser milisegundos')
    require(len({run['id'] for run in manifest['runs']}) == len(manifest['runs']), 'Identificadores de ejecución duplicados')
    stats = {run['id']: read_samples(manifest_path.parent, run) for run in manifest['runs']}
    guide = guide_path.read_text(encoding='utf-8')
    checked = 0
    for marker, table in manifest['tables'].items():
        published = guide_table(guide, marker)
        require(set(published) == {row['label'] for row in table['rows']}, f'Filas distintas en la guía: {marker}')
        for row in table['rows']:
            runs = row.get('runs', table['runs'])
            computed = [stats[run][row['scenario']] for run in runs]
            for column, cell in enumerate(published[row['label']]):
                values = [value.strip() for value in cell.split('/')]
                require(len(values) == len(runs), f'Número de ejecuciones incorrecto: {row["label"]}')
                for value, result in zip(values, computed):
                    actual = Decimal(value.replace(',', '.'))
                    expected = Decimal(str(round(result[column], 3)))
                    require(actual == expected,
                            f'Cifra distinta en la guía: {marker}, {row["label"]}, columna {column + 1}')
            checked += 1
    return checked, sum(sum(run['sample_counts'].values()) for run in manifest['runs'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', required=True, help='Verificar muestras y tablas de la guía')
    args = parser.parse_args()
    try:
        rows, samples = check()
    except (ValueError, KeyError, OSError, InvalidOperation) as error:
        parser.exit(1, f'Error de evidencia: {error}\n')
    print(f'Evidencia correcta: {samples} muestras originales y {rows} filas publicadas verificadas; sin servicios externos.')
