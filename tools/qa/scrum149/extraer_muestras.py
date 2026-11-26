"""Extrae muestras originales sin redondear ni copiar respuestas, rutas privadas o credenciales."""
import argparse
import csv
import json
from pathlib import Path

FIELDS = ('scenario', 'series', 'sample', 'elapsed_ms', 'status', 'error')


def extract(source, output):
    data = json.loads(source.read_text(encoding='utf-8'))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Cada índice permite localizar la observación exacta en el JSON de origen.
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(FIELDS)
        for series, scenarios in enumerate(data['series'], 1):
            for scenario, samples in scenarios.items():
                for index, sample in enumerate(samples, 1):
                    writer.writerow((scenario, series, index, sample['ms'], sample['status'], sample.get('error', '')))
        for index, sample in enumerate(data['cold'], 1):
            writer.writerow(('first_process_requests', 0, index, sample['ms'], sample['status'], sample.get('error', '')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='JSON original de measure.py')
    parser.add_argument('--output', type=Path, required=True, help='CSV sanitizado de destino')
    args = parser.parse_args()
    extract(args.input, args.output)
    print('Muestras originales extraídas; no se han recalculado ni reconstruido tiempos.')
