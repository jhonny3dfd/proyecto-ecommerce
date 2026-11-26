from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

ANTERIOR = [('ventas', '0012_configuracionglobal_dpto_casa_origen')]
REVISION = [('ventas', '0013_revision_y_stock_descontado')]


class MigracionRevisionYStockTests(TransactionTestCase):
    """0013 completa las órdenes existentes según las reglas de stock decididas el 2026-10-12."""

    def migrar(self, destino):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(destino)
        return executor.loader.project_state(destino).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_marca_stock_descontado_en_pagadas_y_cancela_las_rechazadas(self):
        OrdenCompra = self.migrar(ANTERIOR).get_model('ventas', 'OrdenCompra')
        ids = {
            estado: OrdenCompra.objects.create(
                estado=estado, metodo_pago='TRANSBANK', direccion_envio_snapshot={},
                subtotal=1000, costo_envio=0, total_final=1000,
            ).id
            for estado in ('PENDIENTE', 'PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO',
                           'CANCELADO', 'RECHAZADO')
        }

        OrdenCompra = self.migrar(REVISION).get_model('ventas', 'OrdenCompra')

        ordenes = {estado: OrdenCompra.objects.get(id=id_) for estado, id_ in ids.items()}
        for estado in ('PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'):
            self.assertTrue(ordenes[estado].stock_descontado, estado)
        for estado in ('PENDIENTE', 'CANCELADO', 'RECHAZADO'):
            self.assertFalse(ordenes[estado].stock_descontado, estado)
        self.assertEqual(ordenes['RECHAZADO'].estado, 'CANCELADO')
        self.assertEqual(ordenes['RECHAZADO'].motivo_cancelacion, 'Pago rechazado')
        self.assertEqual(ordenes['CANCELADO'].motivo_cancelacion, '')
        self.assertFalse(any(orden.requiere_revision for orden in ordenes.values()))


class MigracionPlazoPagoTests(TransactionTestCase):
    """0031 fija a las transferencias existentes el plazo de entonces: 48 horas, con el recordatorio a las 24."""

    migrar = MigracionRevisionYStockTests.migrar
    tearDown = MigracionRevisionYStockTests.tearDown

    def test_solo_las_transferencias_reciben_su_fecha_limite(self):
        OrdenCompra = self.migrar([('ventas', '0030_entrega_coordinada')]).get_model('ventas', 'OrdenCompra')
        ids = {
            metodo: OrdenCompra.objects.create(
                metodo_pago=metodo, direccion_envio_snapshot={}, subtotal=1000, costo_envio=0, total_final=1000,
            ).id
            for metodo in ('TRANSFERENCIA', 'TRANSBANK')
        }

        OrdenCompra = self.migrar([('ventas', '0031_plazo_pago_por_orden')]).get_model('ventas', 'OrdenCompra')

        transferencia = OrdenCompra.objects.get(id=ids['TRANSFERENCIA'])
        self.assertEqual(transferencia.fecha_limite_pago, transferencia.fecha_creacion + timedelta(hours=48))
        self.assertEqual(transferencia.fecha_recordatorio_pago, transferencia.fecha_creacion + timedelta(hours=24))
        webpay = OrdenCompra.objects.get(id=ids['TRANSBANK'])
        self.assertIsNone(webpay.fecha_limite_pago)


class MigracionTextosFotoBannerTests(TransactionTestCase):
    """0050 copia los textos de la portada a las fotos del carrusel que ya existían (SCRUM-194)."""

    migrar = MigracionRevisionYStockTests.migrar
    tearDown = MigracionRevisionYStockTests.tearDown

    def test_las_fotos_existentes_toman_los_textos_de_la_portada(self):
        apps = self.migrar([('ventas', '0049_publicacion_youtube_id')])
        ConfiguracionGlobal = apps.get_model('ventas', 'ConfiguracionGlobal')
        FotoBanner = apps.get_model('ventas', 'FotoBanner')
        config = ConfiguracionGlobal.objects.create(
            pk=1, nombre_tienda='Tienda', subtitulo_bienvenida='  Hecho a mano ', texto_bienvenida='Murales',
            texto_landing='x' * 1200,
        )
        ids = [FotoBanner.objects.create(configuracion=config, imagen=f'negocio/banners/{i}.png', orden=i).id
               for i in range(2)]

        FotoBanner = self.migrar([('ventas', '0050_fotobanner_textos')]).get_model('ventas', 'FotoBanner')

        for foto in FotoBanner.objects.filter(id__in=ids):
            self.assertEqual((foto.antetitulo, foto.titulo, foto.destino), ('Hecho a mano', 'Murales', 'CATALOGO'))
            self.assertEqual(foto.texto, 'x' * 1000)

    def test_sin_titulo_en_la_portada_usa_el_titulo_por_defecto(self):
        apps = self.migrar([('ventas', '0049_publicacion_youtube_id')])
        config = apps.get_model('ventas', 'ConfiguracionGlobal').objects.create(pk=1, texto_bienvenida='   ')
        foto = apps.get_model('ventas', 'FotoBanner').objects.create(configuracion=config, imagen='a.png')

        FotoBanner = self.migrar([('ventas', '0050_fotobanner_textos')]).get_model('ventas', 'FotoBanner')

        self.assertEqual(FotoBanner.objects.get(id=foto.id).titulo, 'Bienvenido a nuestra tienda')
