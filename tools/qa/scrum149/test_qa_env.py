"""Verifica la carga privada, la prioridad de sesión y errores sin secretos."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import qa_env


class CredencialesQA(unittest.TestCase):
    def test_faltantes_no_usan_respaldo(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(qa_env, 'ENV_FILE', Path('no-existe-qa.env')):
            with self.assertRaisesRegex(RuntimeError, 'Faltan variables de QA: QA149_SECRET_KEY'):
                qa_env.require_env(['QA149_SECRET_KEY'])

    def test_archivo_privado_y_prioridad_de_sesion(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env.local'
            path.write_text('QA149_SECRET_KEY=valor-de-prueba\n', encoding='utf-8')
            with patch.dict(os.environ, {}, clear=True), patch.object(qa_env, 'ENV_FILE', path):
                self.assertEqual(qa_env.require_env(['QA149_SECRET_KEY'])['QA149_SECRET_KEY'], 'valor-de-prueba')
                os.environ['QA149_SECRET_KEY'] = 'sesion-de-prueba'
                self.assertEqual(qa_env.require_env(['QA149_SECRET_KEY'])['QA149_SECRET_KEY'], 'sesion-de-prueba')

    def test_vacio_explicito_no_recurre_al_archivo(self):
        with patch.dict(os.environ, {'QA149_SECRET_KEY': ' '}, clear=True):
            with self.assertRaises(RuntimeError) as error:
                qa_env.require_env(['QA149_SECRET_KEY'])
            self.assertNotIn('valor-de-prueba', str(error.exception))


if __name__ == '__main__':
    unittest.main()
