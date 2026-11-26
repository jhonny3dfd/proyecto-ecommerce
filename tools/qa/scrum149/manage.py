"""Ejecuta comandos Django exclusivamente sobre los servicios aislados de SCRUM-149."""
import os
from pathlib import Path
import sys

QA_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(QA_DIR), str(QA_DIR.parents[2])]
os.environ['DJANGO_SETTINGS_MODULE'] = 'qa_settings'

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    execute_from_command_line(sys.argv)
