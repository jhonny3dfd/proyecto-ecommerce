"""Reseñas con estrellas: el enlace firmado del correo de entrega, el envío, lo que ve el público y la moderación."""

import time
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import unquote

from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from ecommerce.domain.ventas import EventoPedido
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .adapters.correo import CorreoNotificadorPedidos
from .enlaces_resena import orden_del_token, token_resena
from .models import ConfiguracionGlobal, DetalleOrden, OrdenCompra, Resena
from .views import token_verificacion_pago

CORREO_COMPRADOR = 'ana.perez@example.test'
RESENA = {'estrellas': 5, 'comentario': 'Llegó impecable', 'nombre_publico': 'Ana P.', 'acepta_publicacion': True,
          'productos': [{'producto_id': 'taza', 'estrellas': 4, 'comentario': 'Linda taza'}]}


def crear_pedido(estado='ENTREGADO', entregado_hace=timedelta(days=2)):
    orden = OrdenCompra.objects.create(
        email_invitado=CORREO_COMPRADOR, metodo_pago='TRANSBANK', estado=estado,
        direccion_envio_snapshot={'comuna': 'SANTIAGO'}, subtotal=10000, costo_envio=0, total_final=10000,
        nombre_destinatario='Ana Pérez',
        fecha_entrega=timezone.now() - entregado_hace if estado == 'ENTREGADO' else None)
    DetalleOrden.objects.create(orden=orden, producto_mongo_id='taza', variante_sku='TAZA-AZUL',
                                nombre_producto_snapshot='Taza de cerámica - TAZA-AZUL',
                                precio_unitario_snapshot=10000, cantidad=1)
    return orden


class TokenResenaTests(APITestCase):
    def test_lleva_el_numero_del_pedido(self):
        self.assertEqual(orden_del_token(token_resena(7)), 7)

    def test_alterado_de_otro_uso_o_vencido_no_vale(self):
        token = token_resena(7)
        self.assertIsNone(orden_del_token(token[:-1] + ('A' if token[-1] != 'A' else 'B')))
        self.assertIsNone(orden_del_token(token_verificacion_pago(7)))
        self.assertIsNone(orden_del_token(''))
        with patch('django.core.signing.time.time', return_value=time.time() - timedelta(days=61).total_seconds()):
            vencido = token_resena(7)
        self.assertIsNone(orden_del_token(vencido))


class ConResenasActivas(APITestCase):
    def setUp(self):
        cache.clear()
        self.config = ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', resenas_activas=True)
        self.orden = crear_pedido()

    def formulario(self, token=None):
        return self.client.get(reverse('resena-formulario'), {'t': token or token_resena(self.orden.id)})

    def enviar(self, token=None, **cambios):
        return self.client.post(reverse('resenas'), {'token': token or token_resena(self.orden.id), **RESENA,
                                                     **cambios}, format='json')


class FormularioResenaTests(ConResenasActivas):
    def test_muestra_los_productos_del_pedido_y_el_nombre_sugerido_sin_el_correo(self):
        response = self.formulario()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data, {'orden_id': self.orden.id, 'nombre_sugerido': 'Ana P.',
                                         'productos': [{'producto_id': 'taza', 'nombre': 'Taza de cerámica'}]})
        self.assertNotIn(CORREO_COMPRADOR, response.content.decode())

    def test_un_enlace_alterado_responde_lo_mismo_que_uno_de_un_pedido_inexistente(self):
        alterado = self.formulario(token_resena(self.orden.id)[:-2] + 'xx')
        inexistente = self.formulario(token_resena(self.orden.id + 100))
        self.assertEqual((alterado.status_code, inexistente.status_code), (404, 404))
        self.assertEqual(alterado.data['detail'], inexistente.data['detail'])

    def test_con_las_resenas_desactivadas_no_se_ofrece(self):
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=False)
        self.assertEqual(self.formulario().status_code, 403)

    def test_pedido_no_entregado_ya_resenado_o_fuera_de_plazo(self):
        enviado = crear_pedido(estado='ENVIADO')
        vencido = crear_pedido(entregado_hace=timedelta(days=61))
        self.enviar()
        for orden in (enviado, vencido, self.orden):
            with self.subTest(estado=orden.estado, fecha_entrega=orden.fecha_entrega):
                self.assertEqual(self.formulario(token_resena(orden.id)).status_code, 409)


class EnviarResenaTests(ConResenasActivas):
    def test_queda_pendiente_con_la_tienda_y_los_productos(self):
        response = self.enviar()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('revisará', response.data['mensaje'])
        resena = Resena.objects.get(orden=self.orden)
        self.assertEqual((resena.estado, resena.estrellas, resena.comentario, resena.nombre_publico),
                         ('PENDIENTE', 5, 'Llegó impecable', 'Ana P.'))
        self.assertEqual(list(resena.productos.values_list('producto_nombre', 'estrellas')),
                         [('Taza de cerámica', 4)])

    def test_una_sola_vez(self):
        self.enviar()
        response = self.enviar(estrellas=1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Resena.objects.get().estrellas, 5)

    def test_datos_invalidos_vuelven_por_campo(self):
        response = self.enviar(estrellas=7, acepta_publicacion=False,
                               productos=[{'producto_id': 'otro', 'estrellas': 5}])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {'estrellas', 'acepta_publicacion', 'productos'})
        self.assertIn('otro', response.data['productos'])
        self.assertFalse(Resena.objects.exists())

    def test_sin_token_valido_o_con_las_resenas_apagadas_no_guarda(self):
        self.assertEqual(self.enviar(token='falso').status_code, 404)
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=False)
        self.assertEqual(self.enviar().status_code, 403)
        self.assertFalse(Resena.objects.exists())

    def test_un_pedido_no_entregado_no_se_resena(self):
        orden = crear_pedido(estado='EN_PREPARACION')
        self.assertEqual(self.enviar(token=token_resena(orden.id)).status_code, 409)

    def test_un_cuerpo_que_no_es_un_objeto_se_rechaza(self):
        response = self.client.post(reverse('resenas'), [1, 2], format='json')
        self.assertEqual(response.status_code, 404)

    def test_limita_los_envios_por_hora(self):
        respuestas = [self.enviar(token='falso').status_code for _ in range(21)]
        self.assertEqual(respuestas[-1], 429)


class ResenasPublicasTests(ConResenasActivas):
    def aprobar(self, orden, estado='APROBADA', **cambios):
        self.client.post(reverse('resenas'), {'token': token_resena(orden.id), **RESENA, **cambios}, format='json')
        Resena.objects.filter(orden=orden).update(estado=estado)

    def test_la_tienda_muestra_el_promedio_y_las_aprobadas_sin_el_correo_ni_el_pedido(self):
        self.aprobar(self.orden)
        self.aprobar(crear_pedido(), estrellas=4, comentario='')
        self.aprobar(crear_pedido(), estado='PENDIENTE', estrellas=1)
        self.aprobar(crear_pedido(), estado='OCULTA', estrellas=1)

        response = self.client.get(reverse('resenas-tienda'))

        self.assertEqual((response.data['promedio'], response.data['total']), (4.5, 2))
        self.assertEqual([(r['nombre_publico'], r['estrellas'], r['comentario']) for r in response.data['resenas']],
                         [('Ana P.', 5, 'Llegó impecable')])
        contenido = response.content.decode()
        self.assertNotIn(CORREO_COMPRADOR, contenido)
        self.assertNotIn('orden', contenido)

    def test_la_ficha_muestra_las_del_producto(self):
        self.aprobar(self.orden)
        response = self.client.get(reverse('resenas-producto', args=['taza']))
        self.assertEqual((response.data['promedio'], response.data['total']), (4.0, 1))
        self.assertEqual(response.data['resenas'][0]['comentario'], 'Linda taza')

    def test_sin_aprobadas_o_con_las_resenas_apagadas_no_hay_nada(self):
        vacio = {'promedio': None, 'total': 0, 'resenas': []}
        self.assertEqual(self.client.get(reverse('resenas-tienda')).data, vacio)
        self.aprobar(self.orden)
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=False)
        self.assertEqual(self.client.get(reverse('resenas-tienda')).data, vacio)
        self.assertEqual(self.client.get(reverse('resenas-producto', args=['taza'])).data, vacio)


class ModeracionTests(ConResenasActivas):
    def setUp(self):
        super().setUp()
        self.enviar()
        self.resena = Resena.objects.get()
        self.client.force_authenticate(create_user('duena@tienda.test', rol='ADMIN'))

    def moderar(self, estado, **cambios):
        return self.client.patch(reverse('admin-resena-estado', args=[self.resena.id]), {'estado': estado, **cambios},
                                 format='json')

    def test_lista_las_pendientes_con_sus_productos_sin_el_correo(self):
        Resena.objects.create(orden=crear_pedido(), estrellas=3, nombre_publico='Luis R.', estado='APROBADA')

        response = self.client.get(reverse('admin-resenas'), {'estado': 'PENDIENTE'})

        self.assertEqual(response.data['count'], 1)
        resena, = response.data['results']
        self.assertEqual((resena['orden_id'], resena['estado_display'], resena['productos'][0]['producto_nombre']),
                         (self.orden.id, 'Pendiente', 'Taza de cerámica'))
        self.assertNotIn(CORREO_COMPRADOR, response.content.decode())
        self.assertEqual(self.client.get(reverse('admin-resenas')).data['count'], 2)

    def test_aprueba_u_oculta_sin_poder_editar_la_resena(self):
        response = self.moderar('APROBADA', estrellas=1, comentario='Editado', nombre_publico='Otro')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['estado'], 'APROBADA')
        self.resena.refresh_from_db()
        self.assertEqual((self.resena.estrellas, self.resena.comentario, self.resena.nombre_publico),
                         (5, 'Llegó impecable', 'Ana P.'))
        self.assertEqual(self.moderar('OCULTA').data['estado'], 'OCULTA')

    def test_no_vuelve_a_pendiente_ni_acepta_estados_desconocidos(self):
        self.moderar('APROBADA')
        self.assertEqual(self.moderar('PENDIENTE').status_code, 400)
        self.assertEqual(self.moderar('PUBLICADA').status_code, 400)
        self.assertEqual(self.client.patch(reverse('admin-resena-estado', args=[999]), {'estado': 'OCULTA'},
                                           format='json').status_code, 404)

    def test_el_admin_no_puede_crear_resenas(self):
        response = self.client.post(reverse('admin-resenas'), {'estrellas': 5, 'nombre_publico': 'Yo'}, format='json')
        self.assertEqual(response.status_code, 405)

    def test_solo_el_admin_modera(self):
        self.client.force_authenticate(create_user(CORREO_COMPRADOR))
        self.assertEqual(self.client.get(reverse('admin-resenas')).status_code, 403)
        self.assertEqual(self.moderar('APROBADA').status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse('admin-resenas')).status_code, 401)


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class CorreoEntregadoTests(ConResenasActivas):
    def enviar_correo(self, evento=EventoPedido.ENTREGADO):
        with self.captureOnCommitCallbacks(execute=True):
            CorreoNotificadorPedidos().notificar(self.orden.id, evento)
        correo, = mail.outbox
        return correo

    def test_con_las_resenas_activas_trae_el_enlace_firmado(self):
        correo = self.enviar_correo()

        self.assertIn('http://tienda.test/resena?t=', correo.body)
        self.assertIn('Cuéntanos qué te pareció', correo.alternatives[0][0])
        enlace = correo.body.split('http://tienda.test/resena?t=')[1].split()[0]
        self.assertEqual(orden_del_token(unquote(enlace)), self.orden.id)

    def test_sin_resenas_activas_ni_en_otros_correos(self):
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=False)
        self.assertNotIn('/resena', self.enviar_correo().body)
        mail.outbox.clear()
        OrdenCompra.objects.filter(id=self.orden.id).update(estado='ENVIADO')
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=True)
        self.assertNotIn('/resena', self.enviar_correo(EventoPedido.DESPACHADO).body)

    def test_si_ya_dejo_su_resena_no_la_vuelve_a_pedir(self):
        self.enviar()
        self.assertNotIn('/resena', self.enviar_correo().body)


class MisPedidosResenaTests(ConResenasActivas):
    def setUp(self):
        super().setUp()
        self.usuario = create_user(CORREO_COMPRADOR)
        OrdenCompra.objects.filter(id=self.orden.id).update(usuario=self.usuario, email_invitado='')
        self.client.force_authenticate(self.usuario)

    def mis_pedidos(self):
        return {p['id']: p for p in self.client.get(reverse('mis-pedidos')).data}

    def test_un_pedido_entregado_trae_su_enlace_firmado(self):
        pedido = self.mis_pedidos()[self.orden.id]
        self.assertEqual(orden_del_token(pedido['token_resena']), self.orden.id)
        self.assertFalse(pedido['resena_enviada'])

    def test_sin_enlace_si_no_esta_entregado_fuera_de_plazo_o_ya_resenado(self):
        en_camino = crear_pedido(estado='ENVIADO')
        vencido = crear_pedido(entregado_hace=timedelta(days=61))
        OrdenCompra.objects.filter(id__in=[en_camino.id, vencido.id]).update(usuario=self.usuario, email_invitado='')
        self.enviar()

        pedidos = self.mis_pedidos()

        self.assertIsNone(pedidos[en_camino.id]['token_resena'])
        self.assertIsNone(pedidos[vencido.id]['token_resena'])
        self.assertIsNone(pedidos[self.orden.id]['token_resena'])
        self.assertTrue(pedidos[self.orden.id]['resena_enviada'])

    def test_con_las_resenas_apagadas_no_se_ofrece(self):
        ConfiguracionGlobal.objects.filter(pk=1).update(resenas_activas=False)
        self.assertIsNone(self.mis_pedidos()[self.orden.id]['token_resena'])

    def test_no_se_ven_los_pedidos_de_otros(self):
        self.client.force_authenticate(create_user('otra@example.test'))
        self.assertEqual(self.mis_pedidos(), {})


class ConfiguracionResenasTests(APITestCase):
    def test_el_admin_las_activa_y_la_tienda_lo_sabe(self):
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA')
        self.assertFalse(self.client.get(reverse('configuracion-global')).data['resenas_activas'])

        self.client.force_authenticate(create_user('duena@tienda.test', rol='ADMIN'))
        response = self.client.patch(reverse('configuracion-negocio'), {'resenas_activas': True}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.client.force_authenticate(None)
        self.assertTrue(self.client.get(reverse('configuracion-global')).data['resenas_activas'])
