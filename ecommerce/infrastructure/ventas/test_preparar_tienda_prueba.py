from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ecommerce.application.medios_pago import MediosPagoDisponibles
from ecommerce.domain.medios_pago import CodigoMedioPago

from .models import ConfiguracionGlobal, MedioPago, PaginaLegal
from .repositorio_medios_pago import DjangoRepositorioMediosPago


def preparar(nombre='Taller Maché'):
    salida = StringIO()
    call_command('preparar_tienda_prueba', nombre=nombre, stdout=salida)
    return salida.getvalue()


class ComandoPrepararTiendaPruebaTests(TestCase):
    """`manage.py preparar_tienda_prueba`: datos iniciales de una tienda publicada, sin pisar los del admin."""

    def test_en_una_base_vacia_crea_la_configuracion_los_medios_y_los_borradores(self):
        preparar()

        config = ConfiguracionGlobal.objects.get(pk=1)
        self.assertEqual(config.nombre_tienda, 'Taller Maché')
        # La dirección de ejemplo del modelo no se publica
        self.assertFalse(config.retiro_en_local_activo)
        self.assertFalse(config.mostrar_direccion_pie)
        self.assertEqual(config.modo_autenticacion, 'MIXTO')
        self.assertEqual(config.layout_catalogo, 'GRID_3')
        # RN-02: Transbank en integración y la transferencia quedan disponibles para el comprador
        self.assertEqual(MediosPagoDisponibles(DjangoRepositorioMediosPago()).disponibles(),
                         [CodigoMedioPago.TRANSBANK, CodigoMedioPago.TRANSFERENCIA])
        self.assertEqual(MedioPago.objects.get(codigo='TRANSBANK').datos, {'ambiente': 'INTEGRACION'})
        # Claramente ficticia: el comprador ve el aviso en el banco y un número de ceros
        datos_banco = MedioPago.objects.get(codigo='TRANSFERENCIA').datos
        self.assertIn('PRUEBA', datos_banco['banco'])
        self.assertEqual(datos_banco['numero_cuenta'], '00000000')
        self.assertEqual(set(PaginaLegal.objects.values_list('tipo_pagina', flat=True)),
                         {'TERMINOS', 'PRIVACIDAD', 'REEMBOLSOS'})

    def test_nunca_publica_las_paginas_legales(self):
        preparar()

        self.assertFalse(PaginaLegal.objects.filter(publicada=True).exists())
        for pagina in PaginaLegal.objects.all():
            self.assertIn('[completar', pagina.contenido)

    def test_correrlo_dos_veces_no_duplica_ni_cambia_nada(self):
        preparar()
        antes = (list(MedioPago.objects.values('codigo', 'habilitado', 'datos', 'credenciales_cifradas')),
                 list(PaginaLegal.objects.values('tipo_pagina', 'titulo', 'contenido', 'publicada')))

        salida = preparar(nombre='Otro nombre')

        despues = (list(MedioPago.objects.values('codigo', 'habilitado', 'datos', 'credenciales_cifradas')),
                   list(PaginaLegal.objects.values('tipo_pagina', 'titulo', 'contenido', 'publicada')))
        self.assertEqual(antes, despues)
        self.assertEqual(ConfiguracionGlobal.objects.count(), 1)
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).nombre_tienda, 'Taller Maché')
        self.assertIn('ya existía: no se cambió', salida)

    def test_no_pisa_lo_que_el_admin_ya_cambio(self):
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda de Alan', tema_seleccionado=3,
                                           retiro_en_local_activo=True)
        # El admin apagó Transbank y ya publicó sus Términos
        MedioPago.objects.create(codigo='TRANSBANK', habilitado=False, datos={'ambiente': 'INTEGRACION'})
        PaginaLegal.objects.create(tipo_pagina='TERMINOS', titulo='Mis términos', contenido='<p>Reales</p>',
                                   publicada=True)

        preparar()

        config = ConfiguracionGlobal.objects.get(pk=1)
        self.assertEqual((config.nombre_tienda, config.tema_seleccionado, config.retiro_en_local_activo),
                         ('Tienda de Alan', 3, True))
        self.assertFalse(MedioPago.objects.get(codigo='TRANSBANK').habilitado)
        terminos = PaginaLegal.objects.get(tipo_pagina='TERMINOS')
        self.assertEqual((terminos.contenido, terminos.publicada), ('<p>Reales</p>', True))
        # Lo que faltaba sí se crea
        self.assertTrue(MedioPago.objects.get(codigo='TRANSFERENCIA').habilitado)
        self.assertFalse(PaginaLegal.objects.get(tipo_pagina='PRIVACIDAD').publicada)

    def test_no_configura_mercado_pago_ni_crea_usuarios(self):
        from django.contrib.auth import get_user_model

        preparar()

        self.assertFalse(MedioPago.objects.filter(codigo='MERCADO_PAGO').exists())
        self.assertFalse(get_user_model().objects.exists())

    def test_exige_el_nombre_de_la_tienda(self):
        with self.assertRaises(CommandError):
            call_command('preparar_tienda_prueba', stdout=StringIO())
