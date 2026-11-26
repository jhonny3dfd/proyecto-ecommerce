"""Captura comandos reales del controlador y planes de ejecución de PostgreSQL y MongoDB."""
import json
from pathlib import Path
import sys
import time

from pymongo import monitoring

sys.path.insert(0, str(Path(__file__).resolve().parent))


class Commands(monitoring.CommandListener):
    def __init__(self):
        self.commands = []
        self.times = []

    def started(self, event):
        if event.command_name in ('find', 'aggregate', 'distinct', 'count', 'getMore'):
            self.commands.append(dict(event.command))

    def succeeded(self, event):
        self.times.append({'name': event.command_name, 'ms': event.duration_micros / 1000})

    def failed(self, event):
        self.times.append({'name': event.command_name, 'failed': True})


listener = Commands()
monitoring.register(listener)
import manage  # Establece la configuración QA antes de inicializar Django y sus clientes.
import django
django.setup()
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from mongoengine.connection import get_db
from measure import SCENARIOS

result = {}
client = APIClient()
for name in ('products', 'filters', 'price_asc', 'number', 'configuration', 'legal'):
    listener.commands.clear()
    listener.times.clear()
    start = time.perf_counter()
    with CaptureQueriesContext(connection) as captured:
        response = client.get(SCENARIOS[name])
        response.render()
    commands = list(listener.commands)
    record = {'http_status': response.status_code, 'elapsed_ms': (time.perf_counter() - start) * 1000,
              'mongo_commands': len(commands), 'driver_times': list(listener.times),
              'sql': list(captured), 'mongo_explain': [], 'sql_explain': []}
    for command in commands:
        if 'getMore' in command:
            continue
        command = {k: v for k, v in command.items() if k not in ('$db', 'lsid', '$clusterTime')}
        try:
            record['mongo_explain'].append(get_db().command('explain', command, verbosity='executionStats'))
        except Exception as exc:
            record['mongo_explain'].append({'error': type(exc).__name__, 'message': str(exc)})
    with connection.cursor() as cursor:
        for query in captured:
            if query['sql'].startswith('SELECT'):
                cursor.execute('EXPLAIN (ANALYZE, BUFFERS) ' + query['sql'])
                record['sql_explain'].append([row[0] for row in cursor.fetchall()])
    result[name] = record
output = Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
print(json.dumps({k: {x: v[x] for x in ('elapsed_ms', 'mongo_commands')} | {'sql_queries': len(v['sql'])}
                  for k, v in result.items()}, indent=2))
