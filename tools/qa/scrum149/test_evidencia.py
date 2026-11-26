"""Prueba el cálculo y detecta divergencias entre muestras y documentación."""
import csv
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from extraer_muestras import extract
import recalcular_evidencia as evidence


class Estadisticos(unittest.TestCase):
    def test_mediana_par_impar_p95_y_errores(self):
        samples = [{'ms': float(i), 'status': 500 if i == 20 else 200} for i in range(1, 21)]
        self.assertEqual(evidence.summarize(samples), (20, 10.5, 19, 20, 1))
        self.assertEqual(evidence.summarize(samples[:3]), (3, 2, 3, 3, 0))
        self.assertEqual(evidence.summarize([{'ms': 0., 'status': 0}])[-1], 1)

    def test_extrae_valores_y_procedencia_sin_resumenes(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'original.json', Path(folder) / 'muestras.csv'
            source.write_text(json.dumps({'series': [{'products': [{'ms': .123456789012345, 'status': 200}]}],
                                          'cold': [{'ms': 45.6789123456789, 'status': 0, 'error': 'Timeout'}],
                                          'dato_privado': 'no-exportar', 'summary': {'inventado': -1}}), encoding='utf-8')
            extract(source, output)
            with output.open(encoding='utf-8') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(float(rows[0]['elapsed_ms']), .123456789012345)
            self.assertEqual((rows[0]['series'], rows[0]['sample']), ('1', '1'))
            self.assertEqual((rows[1]['scenario'], rows[1]['series'], rows[1]['error']), ('first_process_requests', '0', 'Timeout'))
            self.assertNotIn('no-exportar', output.read_text(encoding='utf-8'))
            self.assertNotIn('inventado', output.read_text(encoding='utf-8'))


class EvidenciaPublicada(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for path in evidence.DEFAULT_MANIFEST.parent.iterdir():
            if path.is_file():
                shutil.copyfile(path, self.folder / path.name)
        self.manifest = self.folder / 'procedencia.json'
        self.guide = self.folder / 'guia.md'
        shutil.copyfile(evidence.DEFAULT_GUIDE, self.guide)

    def check(self):
        return evidence.check(self.manifest, self.guide)

    def test_evidencia_real_y_guia_coinciden(self):
        rows, samples = self.check()
        self.assertGreater(rows, 0)
        self.assertGreater(samples, 3000)

    def test_cambio_en_cifra_publicada_falla_sin_tabla_duplicada(self):
        guide = self.guide.read_text(encoding='utf-8')
        table = evidence.guide_table(guide, 'scrum149-historico')
        cell = next(iter(table.values()))[1]
        self.guide.write_text(guide.replace(cell, '9999 / 9999', 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Cifra distinta en la guía'):
            self.check()

    def test_cambio_en_csv_falla_por_huella(self):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        path = self.folder / manifest['runs'][0]['csv']
        path.write_text(path.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'huella'):
            self.check()

    def test_cantidad_incorrecta_en_guia_falla(self):
        guide = self.guide.read_text(encoding='utf-8')
        self.guide.write_text(guide.replace('| 90 / 90 |', '| 89 / 90 |', 1), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Cifra distinta en la guía'):
            self.check()

    def test_tiempo_alterado_aun_con_huella_actualizada_falla_contra_guia(self):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        run = manifest['runs'][0]
        path = self.folder / run['csv']
        with path.open(encoding='utf-8') as stream:
            rows = list(csv.DictReader(stream))
        rows[0]['elapsed_ms'] = '9999'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=evidence.FIELDS, lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
        run['csv_sha256_utf8_lf'] = evidence.csv_hash(path)
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Cifra distinta en la guía'):
            self.check()

    def test_serie_incompleta_aun_con_huella_actualizada_falla(self):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        run = manifest['runs'][0]
        path = self.folder / run['csv']
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        path.write_text(''.join(lines[:1] + lines[2:]), encoding='utf-8')
        run['csv_sha256_utf8_lf'] = evidence.csv_hash(path)
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Cantidad de muestras'):
            self.check()

    def test_crlf_conserva_huella_logica(self):
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        path = self.folder / manifest['runs'][0]['csv']
        # Normalizar primero para no duplicar los retornos de un archivo ya en CRLF.
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.check()


if __name__ == '__main__':
    unittest.main()
