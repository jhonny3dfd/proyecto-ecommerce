"""Reglas de SCRUM-177 en las vistas reales del admin de Django."""

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from pymongo import MongoClient

from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoConfigurado
from ecommerce.infrastructure.catalogo.documents import Producto, Variante
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, DetalleOrden, MedioPago, OrdenCompra, Promocion
from .cifrado import cifrar_json
from .repositorio_medios_pago import DjangoRepositorioMediosPago


class OrdenCompraAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superusuario = create_user(
            'superusuario-admin@example.test', rol='ADMIN', is_staff=True, is_superuser=True,
        )
        cls.orden = OrdenCompra.objects.create(
            email_invitado='pedido-admin@example.test', metodo_pago='TRANSFERENCIA',
            direccion_envio_snapshot={'comuna': 'Santiago'},
            nombre_destinatario='Persona original', subtotal=20000, costo_envio=0, total_final=20000,
        )

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.superusuario)
        self.url = reverse('admin:ventas_ordencompra_change', args=[self.orden.pk])

    def guardar(self, url=None, **cambios):
        url = url or self.url
        self.client.get(reverse('admin:index'))
        datos = {
            'email_invitado': self.orden.email_invitado,
            'metodo_pago': 'TRANSFERENCIA',
            'direccion_envio_snapshot': json.dumps(self.orden.direccion_envio_snapshot),
            'nombre_destinatario': 'Persona corregida',
            'subtotal': '20000', 'costo_envio': '0', 'total_final': '20000',
            'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
            '_save': 'Guardar',
        }
        datos.update(cambios)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, datos)

    def test_estado_y_control_de_stock_son_solo_lectura_en_edicion(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        formulario = respuesta.context['adminform'].form
        self.assertNotIn('estado', formulario.fields)
        self.assertNotIn('stock_descontado', formulario.fields)
        self.assertContains(respuesta, 'field-estado')

    def test_edicion_permitida_se_guarda_sin_modificar_estado_ni_enviar_correo(self):
        direccion = {'comuna': 'Providencia', 'calle': 'Calle corregida', 'calle_numero': '177'}
        respuesta = self.guardar(telefono_destinatario='+56987654321',
                                 direccion_envio_snapshot=json.dumps(direccion))
        self.assertEqual(respuesta.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.nombre_destinatario, 'Persona corregida')
        self.assertEqual(self.orden.telefono_destinatario, '+56987654321')
        self.assertEqual(self.orden.direccion_envio_snapshot, direccion)
        self.assertEqual(self.orden.estado, 'PENDIENTE')
        self.assertFalse(self.orden.stock_descontado)
        self.assertEqual(mail.outbox, [])

    def test_solo_los_tres_campos_del_destinatario_son_editables_y_el_resto_se_consulta(self):
        respuesta = self.client.get(self.url)
        permitidos = {'nombre_destinatario', 'telefono_destinatario', 'direccion_envio_snapshot'}
        self.assertEqual(set(respuesta.context['adminform'].form.fields), permitidos)
        for campo in OrdenCompra._meta.fields:
            if campo.name not in permitidos:
                self.assertContains(respuesta, 'field-' + campo.name)

    def test_post_manipulado_no_modifica_ningun_campo_protegido(self):
        otro_usuario = create_user('otra-persona-177@example.test')
        promocion = Promocion.objects.create(codigo='OTRA177', tipo_descuento='MONTO_FIJO', valor_descuento=100)
        OrdenCompra.objects.filter(pk=self.orden.pk).update(
            requiere_revision=True, motivo_revision='Revisión original',
            recordatorio_pago_enviado=True, id_transaccion_pasarela='pago-original',
        )
        antes = OrdenCompra.objects.values().get(pk=self.orden.pk)
        respuesta = self.guardar(
            id=str(self.orden.pk + 177), usuario=str(otro_usuario.pk), email_invitado='otro@example.test',
            promocion=str(promocion.pk), fecha_creacion='2000-01-01 00:00:00',
            estado='PAGADO', metodo_pago='MERCADO_PAGO', stock_descontado='on',
            subtotal='1', costo_envio='2', total_final='3', id_transaccion_pasarela='pago-inyectado',
            requiere_revision='', motivo_revision='', motivo_cancelacion='inyectado',
            recordatorio_pago_enviado='', proveedor_logistico='CHILEXPRESS',
            numero_seguimiento_tracking='ot-inyectada', paquete='{"peso":999}',
            error_orden_transporte='error-inyectado',
        )
        self.assertEqual(respuesta.status_code, 302)
        despues = OrdenCompra.objects.values().get(pk=self.orden.pk)
        permitidos = {'nombre_destinatario', 'telefono_destinatario', 'direccion_envio_snapshot'}
        self.assertEqual({k: v for k, v in despues.items() if k not in permitidos},
                         {k: v for k, v in antes.items() if k not in permitidos})
        self.assertEqual(despues['nombre_destinatario'], 'Persona corregida')
        self.assertEqual(OrdenCompra.objects.count(), 1)
        self.assertEqual(mail.outbox, [])

    def test_correccion_de_destinatario_no_sobrescribe_actualizacion_concurrente(self):
        configuracion = admin.site._registry[OrdenCompra]
        guardar = configuracion.save_model

        def actualizar_antes_de_guardar(request, obj, form, change):
            OrdenCompra.objects.filter(pk=obj.pk).update(
                estado='PAGADO', stock_descontado=True, id_transaccion_pasarela='pago-concurrente',
                recordatorio_pago_enviado=True,
            )
            guardar(request, obj, form, change)

        with patch.object(configuracion, 'save_model', side_effect=actualizar_antes_de_guardar):
            self.assertEqual(self.guardar().status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.nombre_destinatario, 'Persona corregida')
        self.assertEqual(self.orden.estado, 'PAGADO')
        self.assertTrue(self.orden.stock_descontado)
        self.assertEqual(self.orden.id_transaccion_pasarela, 'pago-concurrente')
        self.assertTrue(self.orden.recordatorio_pago_enviado)

    def test_post_manipulado_no_cambia_estado_aunque_guarde_la_edicion_permitida(self):
        for actual, nuevo in (
            ('PENDIENTE', 'PAGADO'), ('PENDIENTE', 'ENVIADO'),
            ('PAGADO', 'CANCELADO'), ('ENTREGADO', 'PENDIENTE'), ('CANCELADO', 'PAGADO'),
        ):
            with self.subTest(actual=actual, nuevo=nuevo):
                descontado = actual in ('PAGADO', 'ENTREGADO')
                OrdenCompra.objects.filter(pk=self.orden.pk).update(
                    estado=actual, stock_descontado=descontado, nombre_destinatario='Persona original',
                )
                respuesta = self.guardar(
                    estado=nuevo, stock_descontado='' if descontado else 'on',
                )
                self.assertEqual(respuesta.status_code, 302)
                self.orden.refresh_from_db()
                self.assertEqual(self.orden.estado, actual)
                self.assertEqual(self.orden.stock_descontado, descontado)
                self.assertEqual(self.orden.nombre_destinatario, 'Persona corregida')
        self.assertEqual(mail.outbox, [])

    def test_alta_get_y_post_se_rechazan_incluso_con_superusuario_y_csrf_valido(self):
        url = reverse('admin:ventas_ordencompra_add')
        antes = list(OrdenCompra.objects.values())
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.guardar(url, estado='PAGADO', stock_descontado='on').status_code, 403)
        self.assertEqual(list(OrdenCompra.objects.values()), antes)
        self.assertEqual(DetalleOrden.objects.count(), 0)
        self.assertEqual(mail.outbox, [])

    def test_clonacion_por_post_se_rechaza_sin_modificar_el_pedido_original(self):
        antes = list(OrdenCompra.objects.values())
        self.assertEqual(self.guardar(_saveasnew='1').status_code, 403)
        self.assertEqual(list(OrdenCompra.objects.values()), antes)
        self.assertEqual(DetalleOrden.objects.count(), 0)
        self.assertEqual(mail.outbox, [])

    def test_listado_y_edicion_no_ofrecen_agregar_orden(self):
        for url in (reverse('admin:ventas_ordencompra_changelist'), self.url):
            respuesta = self.client.get(url)
            self.assertEqual(respuesta.status_code, 200)
            self.assertNotContains(respuesta, 'href="' + reverse('admin:ventas_ordencompra_add') + '"')

    def test_superusuario_conserva_gestion_de_promociones_y_configuracion(self):
        alta = reverse('admin:ventas_promocion_add')
        self.client.get(alta)
        datos = {
            'codigo': 'QA-ADMIN-177', 'tipo_descuento': 'PORCENTAJE', 'valor_descuento': '10',
            'is_active': 'on', 'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
        }
        self.assertEqual(self.client.post(alta, datos).status_code, 302)
        promocion = Promocion.objects.get(codigo='QA-ADMIN-177')
        borrar = reverse('admin:ventas_promocion_delete', args=[promocion.pk])
        self.client.get(borrar)
        self.assertEqual(self.client.post(borrar, {
            'post': 'yes', 'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
        }).status_code, 302)
        self.assertFalse(Promocion.objects.filter(pk=promocion.pk).exists())

        configuracion = ConfiguracionGlobal.objects.create(nombre_tienda='Tienda QA')
        edicion = self.client.get(reverse('admin:ventas_configuracionglobal_change', args=[configuracion.pk]))
        self.assertEqual(edicion.status_code, 200)
        self.assertFalse(edicion.context['adminform'].form.fields['nombre_tienda'].disabled)

    def test_el_admin_de_django_aplica_las_reglas_de_los_cupones_y_no_edita_los_usos(self):
        alta = reverse('admin:ventas_promocion_add')
        self.assertNotIn('name="usos"', self.client.get(alta).content.decode())
        datos = {
            'codigo': 'REGALO', 'tipo_descuento': 'PORCENTAJE', 'valor_descuento': '250', 'usos': '5',
            'is_active': 'on', 'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
        }
        self.assertEqual(self.client.post(alta, datos).status_code, 200)
        self.assertFalse(Promocion.objects.exists())

        self.assertEqual(self.client.post(alta, {**datos, 'valor_descuento': '25'}).status_code, 302)
        self.assertEqual(Promocion.objects.get().usos, 0)

    def test_comprador_no_accede_y_post_sin_csrf_se_rechaza(self):
        self.assertEqual(self.client.post(self.url, {'estado': 'PAGADO'}).status_code, 403)
        comprador = create_user('comprador-admin@example.test')
        self.client.force_login(comprador)
        self.assertRedirects(self.client.get(self.url), f'{reverse("admin:login")}?next={self.url}')


class MedioPagoAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superusuario = create_user(
            'superusuario-pagos@example.test', rol='ADMIN', is_staff=True, is_superuser=True,
        )
        cls.secretos = ('api-key-ficticia-177', 'token-ficticio-177', 'webhook-ficticio-177', 'linkify-ficticio-177')
        repo = DjangoRepositorioMediosPago()
        for codigo, datos in (
            (CodigoMedioPago.TRANSBANK, {
                'ambiente': 'PRODUCCION', 'commerce_code': '597012345678', 'api_key': cls.secretos[0],
            }),
            (CodigoMedioPago.MERCADO_PAGO, {'access_token': cls.secretos[1], 'webhook_secret': cls.secretos[2]}),
            (CodigoMedioPago.TRANSFERENCIA, {'banco': 'Banco QA', 'linkify_secret': cls.secretos[3]}),
        ):
            repo.guardar(MedioPagoConfigurado(codigo, True, datos))

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.superusuario)

    def post_con_csrf(self, url, datos):
        self.client.get(url)
        return self.client.post(url, {
            **datos, 'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
        })

    def assert_sin_credenciales(self, respuesta):
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'credenciales_cifradas')
        for valor in (*self.secretos, *MedioPago.objects.values_list('credenciales_cifradas', flat=True)):
            if valor:
                self.assertNotContains(respuesta, valor)

    def test_credenciales_ausentes_en_listado_alta_edicion_historial_y_borrado(self):
        urls = [reverse('admin:ventas_mediopago_changelist'), reverse('admin:ventas_mediopago_add')]
        for medio in MedioPago.objects.all():
            urls.extend(reverse(f'admin:ventas_mediopago_{vista}', args=[medio.pk])
                        for vista in ('change', 'history', 'delete'))
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assert_sin_credenciales(respuesta)
                if 'adminform' in respuesta.context:
                    self.assertNotIn('credenciales_cifradas', respuesta.context['adminform'].form.fields)

    def test_edicion_publica_se_guarda_e_ignora_credenciales_inyectadas(self):
        for medio in MedioPago.objects.all():
            with self.subTest(codigo=medio.codigo):
                cifrado_anterior = medio.credenciales_cifradas
                datos = dict(medio.datos)
                if medio.codigo == 'TRANSFERENCIA':
                    datos['banco'] = 'Banco QA corregido'
                url = reverse('admin:ventas_mediopago_change', args=[medio.pk])
                respuesta = self.post_con_csrf(url, {
                    'codigo': medio.codigo, 'datos': json.dumps(datos),
                    'credenciales_cifradas': 'reemplazo-inyectado', '_save': 'Guardar',
                })
                self.assertEqual(respuesta.status_code, 302)
                medio.refresh_from_db()
                self.assertFalse(medio.habilitado)
                self.assertEqual(medio.datos, datos)
                self.assertEqual(medio.credenciales_cifradas, cifrado_anterior)
                self.assert_sin_credenciales(self.client.get(
                    reverse('admin:ventas_mediopago_history', args=[medio.pk]),
                ))

    def test_formulario_invalido_no_refleja_credenciales_ni_modifica_valor_guardado(self):
        medio = MedioPago.objects.get(codigo='TRANSBANK')
        cifrado_anterior = medio.credenciales_cifradas
        respuesta = self.post_con_csrf(reverse('admin:ventas_mediopago_change', args=[medio.pk]), {
            'codigo': medio.codigo, 'datos': '{json-invalido', 'credenciales_cifradas': 'reemplazo-inyectado',
        })
        self.assert_sin_credenciales(respuesta)
        self.assertIn('datos', respuesta.context['adminform'].form.errors)
        self.assertNotContains(respuesta, 'reemplazo-inyectado')
        medio.refresh_from_db()
        self.assertEqual(medio.credenciales_cifradas, cifrado_anterior)
        self.assertTrue(medio.habilitado)

    def test_alta_legitima_no_acepta_credenciales_inyectadas(self):
        MedioPago.objects.filter(codigo='TRANSBANK').delete()
        respuesta = self.post_con_csrf(reverse('admin:ventas_mediopago_add'), {
            'codigo': 'TRANSBANK', 'habilitado': 'on', 'datos': '{"ambiente":"INTEGRACION"}',
            'credenciales_cifradas': 'reemplazo-inyectado', '_save': 'Guardar',
        })
        self.assertEqual(respuesta.status_code, 302)
        medio = MedioPago.objects.get(codigo='TRANSBANK')
        self.assertTrue(medio.habilitado)
        self.assertEqual(medio.datos, {'ambiente': 'INTEGRACION'})
        self.assertEqual(medio.credenciales_cifradas, '')

    def test_confirmacion_de_borrado_masivo_no_expone_credenciales(self):
        respuesta = self.post_con_csrf(reverse('admin:ventas_mediopago_changelist'), {
            'action': 'delete_selected', '_selected_action': list(MedioPago.objects.values_list('pk', flat=True)),
        })
        self.assert_sin_credenciales(respuesta)
        self.assertEqual(MedioPago.objects.count(), 3)

    def test_secretos_desconocidos_y_estructuras_no_publicas_se_rechazan_sin_reflejarlos(self):
        secreto = 'secreto-introducido-177'
        entradas = [
            {'access_token': secreto}, {'api_key': secreto}, {'webhook_secret': secreto},
            {'linkify_secret': secreto}, {'desconocido': secreto},
            {'banco': {'access_token': secreto}}, {'banco': [secreto]},
            {'ambiente': secreto}, [secreto], secreto, 177, None,
        ]
        for medio in MedioPago.objects.all():
            antes = MedioPago.objects.values().get(pk=medio.pk)
            logs = LogEntry.objects.count()
            for datos in entradas:
                with self.subTest(codigo=medio.codigo, datos=datos):
                    respuesta = self.post_con_csrf(
                        reverse('admin:ventas_mediopago_change', args=[medio.pk]),
                        {'datos': json.dumps(datos), 'habilitado': '', '_save': 'Guardar'},
                    )
                    self.assert_sin_credenciales(respuesta)
                    self.assertIn('datos', respuesta.context['adminform'].form.errors)
                    self.assertNotContains(respuesta, secreto)
                    self.assertEqual(MedioPago.objects.values().get(pk=medio.pk), antes)
                    self.assertEqual(LogEntry.objects.count(), logs)

    def test_json_malformado_no_refleja_el_secreto_introducido(self):
        medio = MedioPago.objects.get(codigo='TRANSBANK')
        antes = MedioPago.objects.values().get(pk=medio.pk)
        secreto = 'secreto-json-incompleto-177'
        respuesta = self.post_con_csrf(reverse('admin:ventas_mediopago_change', args=[medio.pk]), {
            'datos': '{"access_token":"' + secreto + '"',
        })
        self.assert_sin_credenciales(respuesta)
        self.assertIn('datos', respuesta.context['adminform'].form.errors)
        self.assertNotContains(respuesta, secreto)
        self.assertEqual(MedioPago.objects.values().get(pk=medio.pk), antes)

    def test_datos_antiguos_no_admitidos_se_ocultan_y_bloquean_guardado_sin_limpiarlos(self):
        secreto = 'secreto-antiguo-ficticio-177'
        for medio in MedioPago.objects.all():
            for contaminacion in ({'access_token': secreto}, {'otra_clave': secreto},
                                  {'banco': {'anidado': secreto}}):
                with self.subTest(codigo=medio.codigo, contaminacion=contaminacion):
                    MedioPago.objects.filter(pk=medio.pk).update(datos={**medio.datos, **contaminacion})
                    antes = MedioPago.objects.values().get(pk=medio.pk)
                    url = reverse('admin:ventas_mediopago_change', args=[medio.pk])
                    for vista in ('change', 'history', 'delete'):
                        respuesta = self.client.get(reverse(f'admin:ventas_mediopago_{vista}', args=[medio.pk]))
                        self.assert_sin_credenciales(respuesta)
                        self.assertNotContains(respuesta, secreto)
                    self.assertContains(self.client.get(url), 'guardado está bloqueado')
                    respuesta = self.post_con_csrf(url, {'datos': '{}', 'habilitado': '', '_save': 'Guardar'})
                    self.assert_sin_credenciales(respuesta)
                    self.assertTrue(respuesta.context['adminform'].form.non_field_errors())
                    self.assertNotContains(respuesta, secreto)
                    self.assertEqual(MedioPago.objects.values().get(pk=medio.pk), antes)

    def test_codigo_existente_es_protegido_y_se_valida_con_el_proveedor_original(self):
        medio = MedioPago.objects.get(codigo='TRANSBANK')
        cifrado = medio.credenciales_cifradas
        url = reverse('admin:ventas_mediopago_change', args=[medio.pk])
        self.assertNotIn('codigo', self.client.get(url).context['adminform'].form.fields)
        respuesta = self.post_con_csrf(url, {'codigo': 'TRANSFERENCIA', 'datos': '{"banco":"Banco QA"}'})
        self.assertIn('datos', respuesta.context['adminform'].form.errors)
        respuesta = self.post_con_csrf(url, {'codigo': 'TRANSFERENCIA', 'datos': '{"ambiente":"INTEGRACION"}'})
        self.assertEqual(respuesta.status_code, 302)
        medio.refresh_from_db()
        self.assertEqual(medio.codigo, 'TRANSBANK')
        self.assertEqual(medio.datos, {'ambiente': 'INTEGRACION'})
        self.assertEqual(medio.credenciales_cifradas, cifrado)

    def test_alta_con_secreto_en_datos_no_crea_medio_ni_lo_refleja(self):
        MedioPago.objects.filter(codigo='MERCADO_PAGO').delete()
        secreto = 'secreto-alta-ficticio-177'
        respuesta = self.post_con_csrf(reverse('admin:ventas_mediopago_add'), {
            'codigo': 'MERCADO_PAGO', 'datos': json.dumps({'access_token': secreto}),
        })
        self.assert_sin_credenciales(respuesta)
        self.assertIn('datos', respuesta.context['adminform'].form.errors)
        self.assertNotContains(respuesta, secreto)
        self.assertFalse(MedioPago.objects.filter(codigo='MERCADO_PAGO').exists())

    def test_edicion_publica_no_sobrescribe_credenciales_actualizadas_por_panel(self):
        medio = MedioPago.objects.get(codigo='TRANSFERENCIA')
        configuracion = admin.site._registry[MedioPago]
        guardar = configuracion.save_model
        nuevo_cifrado = cifrar_json({'linkify_secret': 'actualizacion-concurrente-ficticia'})

        def actualizar_antes_de_guardar(request, obj, form, change):
            MedioPago.objects.filter(pk=obj.pk).update(credenciales_cifradas=nuevo_cifrado)
            guardar(request, obj, form, change)

        with patch.object(configuracion, 'save_model', side_effect=actualizar_antes_de_guardar):
            respuesta = self.post_con_csrf(reverse('admin:ventas_mediopago_change', args=[medio.pk]), {
                'datos': '{"banco":"Banco corregido"}', '_save': 'Guardar',
            })
        self.assertEqual(respuesta.status_code, 302)
        medio.refresh_from_db()
        self.assertEqual(medio.datos, {'banco': 'Banco corregido'})
        self.assertEqual(medio.credenciales_cifradas, nuevo_cifrado)

    def test_panel_conserva_cifrado_y_datos_publicos_despues_de_editar_admin(self):
        medio = MedioPago.objects.get(codigo='TRANSBANK')
        self.assertEqual(self.post_con_csrf(reverse('admin:ventas_mediopago_change', args=[medio.pk]), {
            'datos': '{"ambiente":"INTEGRACION"}', '_save': 'Guardar',
        }).status_code, 302)
        secreto = 'nuevo-secreto-panel-ficticio-177'
        respuesta = self.client.put(reverse('admin-medio-pago', args=['TRANSBANK']), json.dumps({
            'habilitado': True, 'datos': {'api_key': secreto},
        }), content_type='application/json', HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn(secreto, respuesta.content.decode())
        medio.refresh_from_db()
        self.assertEqual(medio.datos, {'ambiente': 'INTEGRACION'})
        self.assertNotIn(secreto, medio.credenciales_cifradas)
        self.assertEqual(DjangoRepositorioMediosPago().obtener('TRANSBANK').datos['api_key'], secreto)


class AdminPanelInventarioTests(TestCase):
    """PostgreSQL, inventario MongoDB y correos reales capturados en memoria."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mongo = MongoClient(os.environ.get('MONGO_TEST_URI', settings.MONGO_URI), serverSelectionTimeoutMS=5000)
        cls.addClassCleanup(mongo.close)
        mongo.admin.command('ping')
        nombre = f'test_ecode_admin177_{uuid4().hex}'
        cls.addClassCleanup(mongo.drop_database, nombre)
        cls.coleccion = mongo[nombre][Producto._meta['collection']]
        binding = patch.object(Producto, '_get_collection', return_value=cls.coleccion)
        binding.start()
        cls.addClassCleanup(binding.stop)

    @classmethod
    def setUpTestData(cls):
        cls.superusuario = create_user(
            'superusuario-integracion@example.test', rol='ADMIN', is_staff=True, is_superuser=True,
        )
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', retiro_en_local_activo=True)

    def setUp(self):
        self.coleccion.delete_many({})
        self.producto = Producto(
            nombre='Producto QA', categoria='Pruebas', fecha_creacion=datetime.now(timezone.utc),
            activo=True, publicado=True, variantes=[
                Variante(sku='QA177-S', precio=Decimal('10000'), stock=5),
                Variante(sku='QA177-M', precio=Decimal('9000'), stock=8),
            ],
        ).save()
        self.orden = OrdenCompra.objects.create(
            email_invitado='pedido-integracion@example.test', metodo_pago='TRANSFERENCIA',
            proveedor_logistico='RETIRO_LOCAL', direccion_envio_snapshot={'comuna': 'Santiago'},
            nombre_destinatario='Persona original', telefono_destinatario='+56912345678',
            subtotal=20000, costo_envio=0, total_final=20000,
        )
        DetalleOrden.objects.create(
            orden=self.orden, producto_mongo_id=str(self.producto.pk), variante_sku='QA177-S',
            nombre_producto_snapshot='Producto QA - QA177-S', precio_unitario_snapshot=10000, cantidad=2,
        )
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.superusuario)
        self.client.get(reverse('admin:index'))

    def stock(self):
        return {v.sku: v.stock for v in self.producto.reload().variantes}

    def cambiar(self, estado):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.patch(
                reverse('admin-ordenes-patch', args=[self.orden.pk]),
                json.dumps({'estado': estado}), content_type='application/json',
                HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value,
            )

    def manipular_admin(self, **campos):
        url = reverse('admin:ventas_ordencompra_change', args=[self.orden.pk])
        self.client.get(url)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(url, {
                'email_invitado': self.orden.email_invitado, 'metodo_pago': 'TRANSFERENCIA',
                'proveedor_logistico': 'RETIRO_LOCAL',
                'direccion_envio_snapshot': json.dumps(self.orden.direccion_envio_snapshot),
                'nombre_destinatario': 'Persona corregida', 'telefono_destinatario': '+56912345678',
                'subtotal': self.orden.subtotal, 'costo_envio': self.orden.costo_envio,
                'total_final': self.orden.total_final,
                'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value, '_save': 'Guardar',
                **campos,
            })

    def test_intento_de_pago_en_admin_no_tiene_efectos_y_panel_descuenta_una_vez(self):
        detalle_antes = list(self.orden.detalles.values())
        self.assertEqual(self.manipular_admin(estado='PAGADO', stock_descontado='on').status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PENDIENTE')
        self.assertFalse(self.orden.stock_descontado)
        self.assertEqual(self.orden.nombre_destinatario, 'Persona corregida')
        self.assertEqual(list(self.orden.detalles.values()), detalle_antes)
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(mail.outbox, [])

        self.assertEqual(self.cambiar('PAGADO').status_code, 200)
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.stock_descontado)
        self.assertEqual(self.stock(), {'QA177-S': 3, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.cambiar('PAGADO').status_code, 400)
        self.assertEqual(self.stock(), {'QA177-S': 3, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 1)

    def test_montos_pago_y_revision_manipulados_conservan_inventario_y_efectos(self):
        for estado in ('PENDIENTE', 'PAGADO'):
            with self.subTest(estado=estado):
                if estado == 'PAGADO':
                    self.assertEqual(self.cambiar('PAGADO').status_code, 200)
                antes = OrdenCompra.objects.values().get(pk=self.orden.pk)
                detalles = list(self.orden.detalles.values())
                stock = self.stock()
                correos = len(mail.outbox)
                respuesta = self.manipular_admin(
                    estado='CANCELADO', stock_descontado='on', metodo_pago='MERCADO_PAGO',
                    subtotal='1', costo_envio='1', total_final='1', id_transaccion_pasarela='inyectado',
                    requiere_revision='on', motivo_revision='inyectado', recordatorio_pago_enviado='on',
                    proveedor_logistico='CHILEXPRESS', numero_seguimiento_tracking='inyectado',
                )
                self.assertEqual(respuesta.status_code, 302)
                despues = OrdenCompra.objects.values().get(pk=self.orden.pk)
                permitidos = {'nombre_destinatario', 'telefono_destinatario', 'direccion_envio_snapshot'}
                self.assertEqual({k: v for k, v in despues.items() if k not in permitidos},
                                 {k: v for k, v in antes.items() if k not in permitidos})
                self.assertEqual(despues['nombre_destinatario'], 'Persona corregida')
                self.assertEqual(list(self.orden.detalles.values()), detalles)
                self.assertEqual(self.stock(), stock)
                self.assertEqual(len(mail.outbox), correos)

    def test_alta_y_clonacion_bloqueadas_no_alteran_pedidos_detalles_stock_o_correo(self):
        antes = list(OrdenCompra.objects.values())
        detalles = list(DetalleOrden.objects.values())
        stock = self.stock()
        respuesta = self.client.post(reverse('admin:ventas_ordencompra_add'), {
            'metodo_pago': 'TRANSFERENCIA', 'direccion_envio_snapshot': '{"comuna":"Santiago"}',
            'subtotal': '1', 'costo_envio': '0', 'total_final': '1',
            'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
        })
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self.manipular_admin(_saveasnew='1', estado='PAGADO').status_code, 403)
        self.assertEqual(list(OrdenCompra.objects.values()), antes)
        self.assertEqual(list(DetalleOrden.objects.values()), detalles)
        self.assertEqual(self.stock(), stock)
        self.assertEqual(mail.outbox, [])

    def test_cancelacion_manipulada_no_altera_stock_y_panel_lo_repone_una_vez(self):
        self.assertEqual(self.cambiar('PAGADO').status_code, 200)
        self.assertEqual(self.manipular_admin(estado='CANCELADO', stock_descontado='').status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PAGADO')
        self.assertTrue(self.orden.stock_descontado)
        self.assertEqual(self.stock(), {'QA177-S': 3, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual(self.cambiar('CANCELADO').status_code, 200)
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.stock_descontado)
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.cambiar('CANCELADO').status_code, 400)
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 2)

    def test_transicion_invalida_no_tiene_efectos_y_cancelar_pendiente_no_repone(self):
        self.assertEqual(self.cambiar('ENVIADO').status_code, 400)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'PENDIENTE')
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(mail.outbox, [])
        self.assertEqual(self.cambiar('CANCELADO').status_code, 200)
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 1)

    def test_ciclo_del_panel_con_retiro_conserva_stock_y_notifica_cada_hito(self):
        for estado in ('PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'):
            self.assertEqual(self.cambiar(estado).status_code, 200)
            self.assertEqual(self.stock(), {'QA177-S': 3, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 4)
        for correo in mail.outbox:
            self.assertEqual(correo.to, ['pedido-integracion@example.test'])
        self.assertIn('listo para retirar', mail.outbox[2].subject)
        self.assertIn('Retiraste tu pedido', mail.outbox[3].subject)
        self.assertEqual(self.cambiar('CANCELADO').status_code, 400)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(self.stock(), {'QA177-S': 3, 'QA177-M': 8})

    def test_falta_de_stock_compensa_lineas_y_cancelar_no_repone_unidades_no_descontadas(self):
        DetalleOrden.objects.create(
            orden=self.orden, producto_mongo_id=str(self.producto.pk), variante_sku='QA177-M',
            nombre_producto_snapshot='Producto QA - QA177-M', precio_unitario_snapshot=9000, cantidad=9,
        )
        respuesta = self.cambiar('PAGADO')
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()['requiere_revision'])
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.stock_descontado)
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.cambiar('CANCELADO').status_code, 200)
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 2)

    @override_settings(EXIGIR_PAGINAS_LEGALES=False)
    def test_checkout_real_y_pago_manual_siguen_operativos(self):
        DjangoRepositorioMediosPago().guardar(MedioPagoConfigurado(CodigoMedioPago.TRANSFERENCIA, True, {
            'banco': 'Banco QA', 'tipo_cuenta': 'Cuenta vista', 'numero_cuenta': '12345678',
            'rut_titular': '11.111.111-1', 'nombre_titular': 'Tienda QA', 'email': 'pagos@example.test',
        }))
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = Client().post(reverse('checkout'), json.dumps({
                'items': [{'producto_mongo_id': str(self.producto.pk), 'variante_sku': 'QA177-S', 'cantidad': 2}],
                'email_invitado': 'checkout-qa@example.test', 'metodo_pago': 'TRANSFERENCIA',
                'proveedor_logistico': 'RETIRO_LOCAL', 'direccion_envio_snapshot': {'comuna': 'Santiago'},
                'nombre_destinatario': 'Persona QA', 'telefono_destinatario': '+56912345678',
                'subtotal': 20000, 'acepta_terminos': True,
            }), content_type='application/json')
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.orden = OrdenCompra.objects.get(pk=respuesta.json()['orden_id'])
        self.assertEqual(self.orden.estado, 'PENDIENTE')
        self.assertEqual(self.stock(), {'QA177-S': 5, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.cambiar('PAGADO').status_code, 200)
        self.assertEqual(self.stock(), {'QA177-S': 3, 'QA177-M': 8})
        self.assertEqual(len(mail.outbox), 2)
