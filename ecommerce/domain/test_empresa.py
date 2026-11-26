from django.test import SimpleTestCase

from ecommerce.domain.empresa import DatosEmpresa, DatosEmpresaInvalidos, RutInvalido, normalizar_rut

DATOS = {'razon_social': 'Comercial Andes SpA', 'rut': '76.123.456-0', 'giro': 'Venta de artículos de regalo',
         'direccion': 'Av. Providencia 1234, Providencia', 'correo': 'facturas@andes.test'}


class RutTests(SimpleTestCase):
    def test_acepta_el_rut_con_o_sin_puntos_y_guion(self):
        for texto in ('76.123.456-0', '76123456-0', '761234560', ' 76.123.456 - 0 '):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_rut(texto), '76.123.456-0')

    def test_valida_un_rut_publico_conocido(self):
        # Servicio de Impuestos Internos
        self.assertEqual(normalizar_rut('60803000-k'), '60.803.000-K')

    def test_digito_verificador_k_y_cero_y_rut_de_siete_digitos(self):
        self.assertEqual(normalizar_rut('10.000.013-k'), '10.000.013-K')
        self.assertEqual(normalizar_rut('5.126.663-3'), '5.126.663-3')
        self.assertEqual(normalizar_rut('11.111.111-1'), '11.111.111-1')

    def test_rechaza_un_digito_verificador_incorrecto_o_un_formato_que_no_es_rut(self):
        for texto in ('76.123.456-1', '76.123.456', '1-9', '123.456.789-0', 'abc', '', None, '76.123.456-X'):
            with self.subTest(texto=texto), self.assertRaises(RutInvalido):
                normalizar_rut(texto)


class DatosEmpresaTests(SimpleTestCase):
    def test_limpia_espacios_y_normaliza_el_rut(self):
        empresa = DatosEmpresa.desde({**DATOS, 'rut': '761234560', 'razon_social': '  Comercial Andes SpA '})
        self.assertEqual(empresa.como_dict(), DATOS)

    def test_todos_los_datos_son_obligatorios(self):
        with self.assertRaises(DatosEmpresaInvalidos) as error:
            DatosEmpresa.desde({'razon_social': ' ', 'rut': '76.123.456-0'})
        self.assertEqual(set(error.exception.errores), {'razon_social', 'giro', 'direccion', 'correo'})

    def test_informa_el_rut_invalido_junto_a_los_demas_errores(self):
        with self.assertRaises(DatosEmpresaInvalidos) as error:
            DatosEmpresa.desde({**DATOS, 'rut': '76.123.456-1', 'giro': ''})
        self.assertEqual(set(error.exception.errores), {'rut', 'giro'})
        self.assertIn('dígito verificador', error.exception.errores['rut'])
