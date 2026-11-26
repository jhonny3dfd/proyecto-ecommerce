"""Video de YouTube opcional en la ficha del producto (pedido de Alan): el admin pega el enlace y se guarda el ID."""

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user
from .documents import Producto
from .tests import usar_mongo_de_prueba

ID = 'dQw4w9WgXcQ'
OTRO_ID = 'aBcDeFgHiJk'


class VideoProductoTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Producto en una base Mongo temporal: el catálogo de la base real nunca se toca (AGENTS.md §11)
        usar_mongo_de_prueba(cls)

    def setUp(self):
        # Sin drop_collection(): borra la colección de la base real aunque Producto esté ligado a la temporal
        Producto._get_collection().delete_many({})
        self.client.force_authenticate(create_user(email='admin-video@example.test', rol='ADMIN'))
        self.lista = reverse('lista_productos')
        self.contador = 0

    def tearDown(self):
        Producto._get_collection().delete_many({})

    def crear(self, **cambios):
        self.contador += 1
        datos = {'nombre': 'Obra de prueba', 'categoria': 'Arte', 'publicado': True,
                 'variantes': [{'sku': f'VIDEO-{self.contador}', 'precio': 10000, 'stock': 2}]}
        respuesta = self.client.post(self.lista, {**datos, **cambios}, format='json')
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return respuesta.data

    def detalle(self, producto):
        return reverse('detalle_producto', args=[producto['id']])

    def editar(self, producto, **cambios):
        return self.client.patch(self.detalle(producto), cambios, format='json')

    def test_sin_video_por_defecto_y_los_productos_anteriores_se_leen_sin_video(self):
        self.assertEqual(self.crear()['youtube_id'], '')
        # Documento anterior al cambio: no necesita migración
        antiguo = Producto._get_collection().insert_one({
            'nombre': 'Producto antiguo', 'categoria': 'Arte', 'fecha_creacion': timezone.now(),
            'activo': True, 'publicado': True, 'variantes': [],
        })
        self.client.force_authenticate(None)
        respuesta = self.client.get(reverse('detalle_producto', args=[str(antiguo.inserted_id)]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['youtube_id'], '')

    def test_guarda_el_id_de_cualquier_formato_de_enlace(self):
        for enlace in (f'https://www.youtube.com/watch?v={ID}&t=10s', f'https://youtu.be/{ID}',
                       f'https://www.youtube.com/shorts/{ID}', f'  {ID}  '):
            with self.subTest(enlace=enlace):
                producto = self.crear(youtube=enlace)
                self.assertEqual(producto['youtube_id'], ID)
                self.assertNotIn('youtube', producto)
                self.assertEqual(Producto.objects.get(id=producto['id']).youtube_id, ID)

    def test_cambiar_y_quitar_el_video_sin_tocar_lo_demas(self):
        producto = self.crear(youtube=f'https://youtu.be/{ID}', etiqueta='Nuevo')
        respuesta = self.editar(producto, youtube=f'https://www.youtube.com/shorts/{OTRO_ID}')
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data['youtube_id'], OTRO_ID)

        # Editar otro campo no borra el video
        respuesta = self.editar(producto, nombre='Nuevo nombre')
        self.assertEqual(respuesta.data['youtube_id'], OTRO_ID)

        for vacio in ('', '   ', None):
            with self.subTest(vacio=vacio):
                self.editar(producto, youtube=f'https://youtu.be/{ID}')
                respuesta = self.editar(producto, youtube=vacio)
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertEqual(respuesta.data['youtube_id'], '')
        guardado = Producto.objects.get(id=producto['id'])
        self.assertEqual((guardado.youtube_id, guardado.nombre, guardado.etiqueta), ('', 'Nuevo nombre', 'Nuevo'))

    def test_rechaza_un_enlace_que_no_es_de_youtube_o_no_trae_el_video_sin_guardar(self):
        producto = self.crear(youtube=f'https://youtu.be/{ID}')
        for enlace in ('https://vimeo.com/12345678901', 'https://www.youtube.com/watch', 'https://youtu.be/',
                       'https://www.youtube.com/watch?v=corto', 'javascript:alert(1)', 'x' * 501):
            with self.subTest(enlace=enlace):
                respuesta = self.editar(producto, youtube=enlace)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn('youtube', respuesta.data)
                self.assertEqual(Producto.objects.get(id=producto['id']).youtube_id, ID)
        respuesta = self.client.post(self.lista, {'nombre': 'Con mal enlace', 'categoria': 'Arte', 'youtube':
                                                  'https://vimeo.com/12345678901'}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Producto.objects(nombre='Con mal enlace'))

    def test_el_video_se_publica_en_la_ficha_y_solo_el_admin_lo_cambia(self):
        producto = self.crear(youtube=f'https://youtu.be/{ID}')
        comprador = create_user()
        for usuario in (None, comprador):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(self.detalle(producto)).data['youtube_id'], ID)
            respuesta = self.editar(producto, youtube=f'https://youtu.be/{OTRO_ID}')
            self.assertIn(respuesta.status_code, (401, 403))
        self.assertEqual(Producto.objects.get(id=producto['id']).youtube_id, ID)
