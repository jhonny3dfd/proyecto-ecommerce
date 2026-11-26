import json
from datetime import datetime, timedelta, timezone

from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user
from ecommerce.infrastructure.ventas.models import (
    ConfiguracionGlobal, DetalleOrden, OrdenCompra, Publicacion,
)

from .documents import Producto, Variante
from .tests import usar_mongo_de_prueba


class VitrinaAPITests(APITestCase):
    """RF-01.1: la landing recibe los más vendidos (solo pedidos pagados) y los últimos agregados."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        ahora = datetime.now(timezone.utc)
        # Del más viejo (dias=6) al más nuevo (dias=0)
        self.ids = {}
        for dias, nombre, publicado in ((6, 'Vendido', True), (5, 'Pendiente', True), (4, 'Cancelado', True),
                                        (3, 'Oculto', False), (2, 'Medio', True), (1, 'Nuevo', True),
                                        (0, 'Nuevisimo', True)):
            producto = Producto(nombre=nombre, categoria='Arte', publicado=publicado,
                                fecha_creacion=ahora - timedelta(days=dias),
                                variantes=[Variante(sku=f'{nombre}-1', precio=10000, stock=5)]).save()
            self.ids[nombre] = str(producto.id)

        self.vender('Vendido', 5, 'PAGADO')
        self.vender('Oculto', 50, 'ENTREGADO')
        self.vender('Pendiente', 10, 'PENDIENTE')
        self.vender('Cancelado', 9, 'CANCELADO')

    def vender(self, nombre, cantidad, estado):
        orden = OrdenCompra.objects.create(
            email_invitado='comprador@example.test', estado=estado, direccion_envio_snapshot={},
            subtotal=10000 * cantidad, costo_envio=0, total_final=10000 * cantidad, proveedor_logistico='RETIRO_LOCAL')
        DetalleOrden.objects.create(orden=orden, producto_mongo_id=self.ids[nombre], variante_sku=f'{nombre}-1',
                                    nombre_producto_snapshot=nombre, precio_unitario_snapshot=10000, cantidad=cantidad)

    def nombres(self, productos):
        return [p['nombre'] for p in productos]

    def test_mas_vendidos_cuenta_solo_pedidos_pagados_y_productos_publicados(self):
        response = self.client.get(reverse('vitrina'))

        self.assertEqual(response.status_code, 200)
        mas_vendidos = self.nombres(response.data['mas_vendidos'])
        # El único vendido y publicado va primero; el resto se completa (hay pocas ventas)
        self.assertEqual(mas_vendidos[0], 'Vendido')
        self.assertEqual(len(mas_vendidos), 4)
        self.assertNotIn('Oculto', mas_vendidos)

    def test_ultimos_agregados_son_los_publicados_mas_nuevos(self):
        recientes = self.nombres(self.client.get(reverse('vitrina')).data['recientes'])

        self.assertEqual(recientes, ['Nuevisimo', 'Nuevo', 'Medio', 'Cancelado'])

    def test_entrega_los_datos_que_usan_las_tarjetas_del_catalogo(self):
        producto = self.client.get(reverse('vitrina')).data['recientes'][0]

        for campo in ('id', 'nombre', 'categoria', 'imagenes', 'variantes'):
            self.assertIn(campo, producto)


class DestacadosAPITests(APITestCase):
    """RF-01.1, pedido de un cliente: el admin elige los destacados de la landing en vez de "Más vendidos"."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        ahora = datetime.now(timezone.utc)
        self.mural = str(Producto(nombre='Mural', categoria='Arte', publicado=True,
                                  fecha_creacion=ahora - timedelta(days=2),
                                  imagenes=['https://example.com/mural.jpg'],
                                  variantes=[Variante(sku='MURAL-1', precio=90000, stock=1)]).save().id)
        self.cuadro = str(Producto(nombre='Cuadro', categoria='Arte', publicado=True,
                                   fecha_creacion=ahora - timedelta(days=1),
                                   variantes=[Variante(sku='CUADRO-1', precio=40000, stock=2)]).save().id)
        self.sin_publicar = str(Producto(nombre='Boceto', categoria='Arte', publicado=False, fecha_creacion=ahora,
                                         variantes=[Variante(sku='BOCETO-1', precio=1000, stock=1)]).save().id)
        self.proyecto = str(Publicacion.objects.create(titulo='Mural en Cerro Alegre', slug='mural-cerro-alegre',
                                                       estado='PUBLICADA').pk)
        self.borrador = str(Publicacion.objects.create(titulo='Idea', slug='idea', estado='BORRADOR').pk)
        self.configuracion = ConfiguracionGlobal.objects.create(
            pk=1, nombre_tienda='Taller', blog_activo=True, vitrina_modo='DESTACADOS', destacados_titulo='Obras',
            destacados=[{'tipo': 'PUBLICACION', 'id': self.proyecto}, {'tipo': 'PRODUCTO', 'id': self.mural}])

    def vitrina(self):
        respuesta = self.client.get(reverse('vitrina'))
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.data

    def configurar(self, **campos):
        ConfiguracionGlobal.objects.filter(pk=1).update(**campos)

    def test_muestra_los_destacados_en_el_orden_elegido_en_lugar_de_los_mas_vendidos(self):
        datos = self.vitrina()

        self.assertEqual(datos['destacados_titulo'], 'Obras')
        self.assertEqual(datos['mas_vendidos'], [])
        proyecto, mural = datos['destacados']
        self.assertEqual(proyecto, {'tipo': 'PUBLICACION', 'id': self.proyecto, 'nombre': 'Mural en Cerro Alegre',
                                    'imagen': None, 'enlace': '/blog/mural-cerro-alegre'})
        self.assertEqual((mural['tipo'], mural['id'], mural['nombre'], mural['categoria']),
                         ('PRODUCTO', self.mural, 'Mural', 'Arte'))
        self.assertEqual(mural['imagen'], 'https://example.com/mural.jpg')
        self.assertEqual(mural['enlace'], f'/catalogo/producto/{self.mural}')
        self.assertEqual(float(mural['variantes'][0]['precio']), 90000)
        # "Últimos agregados" no cambia
        self.assertEqual([p['nombre'] for p in datos['recientes']], ['Cuadro', 'Mural'])

    def test_un_producto_despublicado_o_una_publicacion_en_borrador_desaparecen(self):
        self.configurar(destacados=[{'tipo': 'PRODUCTO', 'id': self.sin_publicar},
                                    {'tipo': 'PUBLICACION', 'id': self.borrador},
                                    {'tipo': 'PRODUCTO', 'id': self.cuadro}])

        self.assertEqual([d['nombre'] for d in self.vitrina()['destacados']], ['Cuadro'])

    def test_con_el_blog_apagado_las_publicaciones_no_se_muestran(self):
        self.configurar(blog_activo=False)

        self.assertEqual([d['tipo'] for d in self.vitrina()['destacados']], ['PRODUCTO'])

    def test_si_no_queda_ninguno_visible_se_muestran_los_mas_vendidos(self):
        self.configurar(blog_activo=False, destacados=[{'tipo': 'PUBLICACION', 'id': self.proyecto}])
        datos = self.vitrina()

        self.assertEqual(datos['destacados'], [])
        self.assertEqual(len(datos['mas_vendidos']), 2)

    def test_por_defecto_se_ven_los_mas_vendidos_como_antes(self):
        ConfiguracionGlobal.objects.all().delete()
        datos = self.vitrina()

        self.assertEqual((datos['destacados'], datos['destacados_titulo']), ([], 'Destacados'))
        self.assertEqual(len(datos['mas_vendidos']), 2)
        self.assertEqual(ConfiguracionGlobal(nombre_tienda='Nueva').vitrina_modo, 'MAS_VENDIDOS')


class GuardarDestacadosTests(APITestCase):
    """El backend valida la selección: como máximo 4, sin repetir y solo lo que existe."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        usar_mongo_de_prueba(cls)

    def setUp(self):
        Producto._get_collection().delete_many({})
        ahora = datetime.now(timezone.utc)
        self.productos = [str(Producto(nombre=f'Obra {numero}', categoria='Arte', publicado=numero != 3,
                                       fecha_creacion=ahora - timedelta(days=numero),
                                       variantes=[Variante(sku=f'OBRA-{numero}', precio=1000, stock=1)]).save().id)
                          for numero in range(4)]
        self.borrador = Publicacion.objects.create(titulo='Idea', slug='idea', estado='BORRADOR').pk
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Taller')
        self.url = reverse('configuracion-negocio')
        self.client.force_authenticate(create_user('admin-destacados@example.test', rol='ADMIN'))

    def guardar(self, **datos):
        return self.client.patch(self.url, datos, format='json')

    def test_guarda_el_modo_el_titulo_y_la_seleccion(self):
        seleccion = [{'tipo': 'PUBLICACION', 'id': self.borrador}, {'tipo': 'PRODUCTO', 'id': self.productos[3]}]
        respuesta = self.guardar(vitrina_modo='DESTACADOS', destacados_titulo='  Obras   elegidas ',
                                 destacados=seleccion)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        configuracion = ConfiguracionGlobal.objects.get(pk=1)
        self.assertEqual(configuracion.vitrina_modo, 'DESTACADOS')
        self.assertEqual(configuracion.destacados_titulo, 'Obras elegidas')
        # El id de la publicación se guarda como texto; un borrador y un producto sin publicar se aceptan
        self.assertEqual(configuracion.destacados, [{'tipo': 'PUBLICACION', 'id': str(self.borrador)},
                                                    {'tipo': 'PRODUCTO', 'id': self.productos[3]}])
        publica = self.client.get(reverse('configuracion-global')).data
        self.assertEqual((publica['vitrina_modo'], publica['destacados_titulo']), ('DESTACADOS', 'Obras elegidas'))

    def test_con_imagenes_la_seleccion_llega_como_json_en_el_mismo_multipart(self):
        # El modo edición guarda las imágenes y la selección en una sola petición (useEdicionLanding.js)
        seleccion = [{'tipo': 'PRODUCTO', 'id': self.productos[0]}]
        respuesta = self.client.patch(self.url, {'vitrina_modo': 'DESTACADOS', 'destacados': json.dumps(seleccion)},
                                      format='multipart')

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).destacados, seleccion)
        mal_formado = self.client.patch(self.url, {'destacados': '[{'}, format='multipart')
        self.assertEqual(mal_formado.status_code, 400)
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).destacados, seleccion)

    def test_un_titulo_vacio_vuelve_a_destacados(self):
        self.assertEqual(self.guardar(destacados_titulo='   ').status_code, 200)
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).destacados_titulo, 'Destacados')

    def test_rechaza_una_seleccion_invalida_sin_guardarla(self):
        producto = {'tipo': 'PRODUCTO', 'id': self.productos[0]}
        # 9 que existen: 8 productos y una publicación
        otros = [str(Producto(nombre=f'Extra {numero}', categoria='Arte', fecha_creacion=datetime.now(timezone.utc),
                              variantes=[Variante(sku=f'EXTRA-{numero}', precio=1000, stock=1)]).save().id)
                 for numero in range(4)]
        casos = {
            'mas de 8': [{'tipo': 'PRODUCTO', 'id': i} for i in self.productos + otros]
            + [{'tipo': 'PUBLICACION', 'id': self.borrador}],
            'repetido': [producto, producto],
            'producto que no existe': [{'tipo': 'PRODUCTO', 'id': '6650f0a1b2c3d4e5f6a7b8c9'}],
            'publicacion que no existe': [{'tipo': 'PUBLICACION', 'id': '999999'}],
            'otro tipo': [{'tipo': 'CATEGORIA', 'id': 'Arte'}],
            'no es una lista': {'tipo': 'PRODUCTO'},
        }
        for caso, seleccion in casos.items():
            with self.subTest(caso):
                respuesta = self.guardar(destacados=seleccion)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn('destacados', respuesta.data)
                if caso == 'mas de 8':
                    self.assertIn('hasta 8', str(respuesta.data['destacados']))
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).destacados, [])

    def test_rechaza_un_modo_o_un_titulo_invalidos(self):
        self.assertEqual(self.guardar(vitrina_modo='ALEATORIO').status_code, 400)
        self.assertEqual(self.guardar(destacados_titulo='x' * 61).status_code, 400)

    def test_solo_el_admin_puede_elegirlos(self):
        datos = {'vitrina_modo': 'DESTACADOS'}
        self.client.force_authenticate(None)
        self.assertEqual(self.client.patch(self.url, datos, format='json').status_code, 401)
        self.client.force_authenticate(create_user('comprador-destacados@example.test'))
        self.assertEqual(self.client.patch(self.url, datos, format='json').status_code, 403)
        self.assertEqual(ConfiguracionGlobal.objects.get(pk=1).vitrina_modo, 'MAS_VENDIDOS')
