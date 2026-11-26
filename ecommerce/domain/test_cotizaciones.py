from datetime import date

from django.test import SimpleTestCase

from ecommerce.domain.cotizaciones import MAX_FOTOS_COTIZACION, CotizacionInvalida, SolicitudCotizacion
from ecommerce.domain.imagenes import ImagenProcesada

HOY = date(2026, 10, 20)
EMPRESA = {'razon_social': 'Comercial Andes SpA', 'rut': '761234560', 'giro': 'Regalos corporativos',
           'direccion': 'Av. Providencia 1234', 'correo': 'facturas@andes.test'}
DATOS = {'nombre': 'Ana Pérez', 'correo': 'ana@example.test', 'telefono': '9 1234 5678', 'cantidad': 50,
         'descripcion': 'Tazas con el logo de la empresa', 'personalizacion': 'Logo a dos colores'}


class SolicitudCotizacionTests(SimpleTestCase):
    def errores(self, datos, **kwargs):
        with self.assertRaises(CotizacionInvalida) as error:
            SolicitudCotizacion.desde(datos, HOY, **kwargs)
        return error.exception.errores

    def test_hasta_tres_fotos_de_la_idea(self):
        foto = ImagenProcesada(contenido=b'jpg', extension='jpg')
        solicitud = SolicitudCotizacion.desde(DATOS, HOY, fotos=(foto,) * MAX_FOTOS_COTIZACION)
        self.assertEqual(len(solicitud.fotos), 3)
        self.assertIn('fotos', self.errores(DATOS, fotos=(foto,) * (MAX_FOTOS_COTIZACION + 1)))

    def test_una_persona_cotiza_un_producto_descrito_por_ella(self):
        solicitud = SolicitudCotizacion.desde({**DATOS, 'nombre': '  Ana Pérez '}, HOY)
        self.assertEqual(solicitud.nombre, 'Ana Pérez')
        self.assertEqual(solicitud.telefono, '+56912345678')
        self.assertIsNone(solicitud.empresa)

    def test_un_producto_del_catalogo_guarda_su_nombre(self):
        solicitud = SolicitudCotizacion.desde({**DATOS, 'descripcion': '', 'producto_id': 'abc'}, HOY,
                                              producto_nombre='Taza de cerámica')
        self.assertEqual((solicitud.producto_id, solicitud.producto_nombre), ('abc', 'Taza de cerámica'))

    def test_un_producto_que_ya_no_existe_se_rechaza(self):
        self.assertEqual(set(self.errores({**DATOS, 'producto_id': 'borrado'})), {'producto_id'})

    def test_sin_producto_ni_descripcion_no_se_sabe_que_cotizar(self):
        self.assertEqual(set(self.errores({**DATOS, 'descripcion': '  '})), {'descripcion'})

    def test_contacto_obligatorio_y_telefono_chileno(self):
        self.assertEqual(set(self.errores({**DATOS, 'nombre': '', 'correo': ''})), {'nombre', 'correo'})
        self.assertIn('telefono', self.errores({**DATOS, 'telefono': '123'}))
        self.assertIn('nombre', self.errores({**DATOS, 'nombre': '12345'}))

    def test_cantidad_entre_1_y_100000(self):
        for cantidad in (0, -3, 100_001, None, '5', True):
            with self.subTest(cantidad=cantidad):
                self.assertEqual(set(self.errores({**DATOS, 'cantidad': cantidad})), {'cantidad'})
        self.assertEqual(SolicitudCotizacion.desde({**DATOS, 'cantidad': 100_000}, HOY).cantidad, 100_000)

    def test_la_fecha_requerida_es_opcional_pero_no_puede_estar_en_el_pasado(self):
        self.assertIsNone(SolicitudCotizacion.desde(DATOS, HOY).fecha_requerida)
        self.assertEqual(SolicitudCotizacion.desde({**DATOS, 'fecha_requerida': HOY}, HOY).fecha_requerida, HOY)
        self.assertIn('fecha_requerida', self.errores({**DATOS, 'fecha_requerida': date(2026, 10, 19)}))

    def test_como_empresa_exige_los_datos_para_la_factura(self):
        solicitud = SolicitudCotizacion.desde({**DATOS, 'como_empresa': True, 'empresa': EMPRESA}, HOY)
        self.assertEqual(solicitud.empresa.rut, '76.123.456-0')

        errores = self.errores({**DATOS, 'como_empresa': True, 'empresa': {**EMPRESA, 'rut': '76.123.456-1'}})
        self.assertEqual(set(errores['empresa']), {'rut'})
        self.assertEqual(set(self.errores({**DATOS, 'como_empresa': True})['empresa']),
                         {'razon_social', 'rut', 'giro', 'direccion', 'correo'})

    def test_como_persona_ignora_los_datos_de_empresa(self):
        self.assertIsNone(SolicitudCotizacion.desde({**DATOS, 'empresa': EMPRESA}, HOY).empresa)
