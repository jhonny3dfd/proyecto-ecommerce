from unittest import TestCase

from ecommerce.domain.catalogo import (
    ColeccionPrivadaInvalida, OrdenCategoriasInvalido, normalizar_orden_categorias, ordenar_categorias,
    validar_obra_no_es_version_de_otra, validar_version_a_la_venta,limpiar_colecciones,
)


class OrdenCategoriasTests(TestCase):
    def test_quita_espacios_y_conserva_el_orden(self):
        self.assertEqual(normalizar_orden_categorias([' Zeta ', 'Beta']), ['Zeta', 'Beta'])
        self.assertEqual(normalizar_orden_categorias([]), [])

    def test_rechaza_lo_que_no_es_una_lista_de_textos_validos(self):
        for valor in [None, {}, 'Beta', [''], ['   '], [1], ['x' * 101]]:
            with self.subTest(valor=valor), self.assertRaises(OrdenCategoriasInvalido):
                normalizar_orden_categorias(valor)

    def test_rechaza_repetidas_aunque_difieran_en_espacios(self):
        with self.assertRaises(OrdenCategoriasInvalido):
            normalizar_orden_categorias(['Beta', ' Beta '])

    def test_ordena_priorizadas_primero_y_el_resto_alfabetico(self):
        self.assertEqual(ordenar_categorias(['Zeta', 'Alfa', 'Beta', 'Gama'], ['Gama', 'Inexistente', 'Beta']),
                         ['Gama', 'Beta', 'Alfa', 'Zeta'])


class ColeccionPrivadaDomainTests(TestCase):
    def test_version_a_la_venta_no_puede_ser_el_mismo_producto(self):
        with self.assertRaises(ColeccionPrivadaInvalida) as ctx:
            validar_version_a_la_venta('prod-1', 'prod-1', target_existe=True, target_es_coleccion_privada=False)
        self.assertIn('su propia versión', str(ctx.exception))

    def test_version_a_la_venta_debe_existir(self):
        with self.assertRaises(ColeccionPrivadaInvalida) as ctx:
            validar_version_a_la_venta('prod-1', 'inexistente', target_existe=False, target_es_coleccion_privada=False)
        self.assertIn('no existe', str(ctx.exception))

    def test_version_a_la_venta_no_puede_ser_otra_coleccion_privada(self):
        with self.assertRaises(ColeccionPrivadaInvalida) as ctx:
            validar_version_a_la_venta('prod-1', 'prod-2', target_existe=True, target_es_coleccion_privada=True)
        self.assertIn('otra obra que es colección privada', str(ctx.exception))

    def test_version_a_la_venta_valida_no_levanta_error(self):
        validar_version_a_la_venta('prod-1', 'print-1', target_existe=True, target_es_coleccion_privada=False)

    def test_obra_asignada_como_version_no_puede_ser_coleccion_privada(self):
        with self.assertRaises(ColeccionPrivadaInvalida) as ctx:
            validar_obra_no_es_version_de_otra('print-1', coleccion_privada=True, nombre_referenciador='Pintura Al Óleo')
        self.assertIn('Pintura Al Óleo', str(ctx.exception))

    def test_obra_no_referenciada_puede_ser_coleccion_privada(self):
        validar_obra_no_es_version_de_otra('obra-1', coleccion_privada=True, nombre_referenciador=None)

class ColeccionesDomainTests(TestCase):
    def test_limpia_espacios_y_elimina_duplicados_case_insensitive(self):
        """Verifica que se eliminen espacios extra y duplicados sin distinguir mayúsculas."""
        brutas = [" Cyber ", "cyber", "VERANO", "Verano  ", ""]
        limpias = limpiar_colecciones(brutas)
        
        
        self.assertEqual(len(limpias), 2)
        self.assertIn("Cyber", limpias)
        self.assertIn("VERANO", limpias)

    def test_retorna_lista_vacia_si_recibe_nulo_o_vacio(self):
        self.assertEqual(limpiar_colecciones(None), [])
        self.assertEqual(limpiar_colecciones([]), [])

    def test_ignora_tipos_invalidos(self):
        self.assertEqual(limpiar_colecciones(["Cyber", 123, None, "Verano"]), ["Cyber", "Verano"])