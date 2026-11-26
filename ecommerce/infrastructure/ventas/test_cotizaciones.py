"""Formulario de cotización y encargos: la tienda recibe la solicitud por correo y la gestiona en el panel."""

from io import BytesIO
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from PIL import Image

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from ecommerce.application.cotizaciones import NombresProductos
from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .models import ConfiguracionGlobal, Cotizacion

EMPRESA = {'razon_social': 'Comercial Andes SpA', 'rut': '761234560', 'giro': 'Regalos corporativos',
           'direccion': 'Av. Providencia 1234', 'correo': 'facturas@andes.test'}
SOLICITUD = {
    'nombre': 'Ana Pérez', 'correo': 'ana@example.test', 'telefono': '9 1234 5678', 'cantidad': 50,
    'producto_id': 'taza', 'personalizacion': 'Logo a dos colores', 'acepta_privacidad': True,
}


class ProductosFalsos(NombresProductos):
    def nombre(self, producto_id):
        return {'taza': 'Taza de cerámica'}.get(producto_id)


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class FormularioCotizacionTests(APITestCase):
    def setUp(self):
        # El throttle cuenta las solicitudes en la caché: cada test parte de cero
        cache.clear()
        self.config = ConfiguracionGlobal.objects.create(
            pk=1, nombre_tienda='Tienda QA', cotizaciones_activas=True, correo_contacto='hola@tienda.test')
        productos = patch('ecommerce.infrastructure.ventas.views.MongoNombresProductos', ProductosFalsos)
        productos.start()
        self.addCleanup(productos.stop)

    def enviar(self, **cambios):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('cotizaciones'), {**SOLICITUD, **cambios}, format='json')

    def test_guarda_la_solicitud_como_nueva_y_avisa_a_la_tienda_y_al_cliente(self):
        response = self.enviar()

        self.assertEqual(response.status_code, 201, response.data)
        cotizacion = Cotizacion.objects.get()
        self.assertEqual((cotizacion.estado, cotizacion.producto_nombre, cotizacion.telefono),
                         ('NUEVA', 'Taza de cerámica', '+56912345678'))
        tienda, cliente = mail.outbox
        self.assertEqual(tienda.to, ['hola@tienda.test'])
        # La tienda le responde al cliente con solo responder el correo, y viceversa
        self.assertEqual(tienda.reply_to, ['ana@example.test'])
        self.assertEqual(tienda.subject, f'Nueva solicitud de cotización #{cotizacion.id} | Tienda QA')
        self.assertIn('Producto: Taza de cerámica', tienda.body)
        self.assertIn('Personalización: Logo a dos colores', tienda.body)
        self.assertIn('http://tienda.test/admin', tienda.body)
        self.assertEqual((cliente.to, cliente.reply_to), (['ana@example.test'], ['hola@tienda.test']))
        self.assertIn('Tienda QA revisará tu solicitud', cliente.body)
        # Una cotización no es un pedido: sin enlace al seguimiento
        self.assertNotIn('seguimiento', cliente.alternatives[0][0])

    def test_una_empresa_cotiza_con_los_datos_para_la_factura(self):
        response = self.enviar(como_empresa=True, empresa=EMPRESA)

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Cotizacion.objects.get().datos_empresa['rut'], '76.123.456-0')
        self.assertIn('RUT: 76.123.456-0', mail.outbox[0].body)

    def test_una_empresa_sin_rut_valido_se_rechaza_junto_al_campo(self):
        response = self.enviar(como_empresa=True, empresa={**EMPRESA, 'rut': ''})

        self.assertEqual(response.status_code, 400)
        self.assertIn('rut', response.data['empresa'])
        self.assertFalse(Cotizacion.objects.exists())

    def test_rechaza_lo_que_falta_sin_guardar_ni_avisar(self):
        response = self.enviar(producto_id='', descripcion='', cantidad=0, telefono='123')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {'descripcion', 'cantidad', 'telefono'})
        self.assertEqual((Cotizacion.objects.count(), len(mail.outbox)), (0, 0))

    def test_exige_aceptar_la_politica_de_privacidad(self):
        response = self.enviar(acepta_privacidad=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn('acepta_privacidad', response.data)

    def test_con_el_formulario_desactivado_no_recibe_solicitudes(self):
        self.config.cotizaciones_activas = False
        self.config.save(update_fields=['cotizaciones_activas'])

        response = self.enviar()

        self.assertEqual(response.status_code, 403)
        self.assertEqual((Cotizacion.objects.count(), len(mail.outbox)), (0, 0))

    def test_el_campo_trampa_lleno_responde_como_si_nada_pero_no_guarda(self):
        response = self.enviar(sitio_web='https://spam.example')

        self.assertEqual(response.status_code, 201)
        self.assertEqual((Cotizacion.objects.count(), len(mail.outbox)), (0, 0))

    def test_no_permite_escribir_campos_internos(self):
        self.enviar(estado='ACEPTADA', id=999, fecha_creacion='2020-01-01T00:00:00Z')
        cotizacion = Cotizacion.objects.get()
        self.assertEqual(cotizacion.estado, 'NUEVA')
        self.assertNotEqual(cotizacion.id, 999)

    def test_limita_las_solicitudes_por_hora_desde_la_misma_ip(self):
        for _ in range(10):
            self.assertNotEqual(self.enviar(nombre='').status_code, 429)
        self.assertEqual(self.enviar().status_code, 429)
        self.assertFalse(Cotizacion.objects.exists())

    def test_sin_correo_de_contacto_avisa_a_los_administradores(self):
        self.config.correo_contacto = ''
        self.config.save(update_fields=['correo_contacto'])
        create_user('duena@tienda.test', rol='ADMIN')

        self.enviar()

        self.assertEqual(mail.outbox[0].to, ['duena@tienda.test'])


class PanelCotizacionesTests(APITestCase):
    def setUp(self):
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA')
        datos = {'correo': 'ana@example.test', 'telefono': '+56912345678', 'cantidad': 10}
        self.antigua = Cotizacion.objects.create(nombre='Ana', descripcion='Tazas', **datos)
        self.reciente = Cotizacion.objects.create(nombre='Luis', descripcion='Poleras', **datos)
        self.client.force_authenticate(create_user('admin-cotizaciones@example.test', rol='ADMIN'))

    def test_lista_de_la_mas_reciente_a_la_mas_antigua(self):
        datos = self.client.get(reverse('admin-cotizaciones')).data
        self.assertEqual(datos['count'], 2)
        self.assertEqual([c['id'] for c in datos['results']], [self.reciente.id, self.antigua.id])
        self.assertEqual(datos['results'][0]['estado_display'], 'Nueva')

    def test_lista_paginada_de_a_20(self):
        Cotizacion.objects.bulk_create(
            Cotizacion(nombre=f'Cliente {n}', correo=f'c{n}@example.test', telefono='+56912345678', cantidad=1,
                       descripcion='Tazas')
            for n in range(21))

        primera = self.client.get(reverse('admin-cotizaciones')).data
        segunda = self.client.get(reverse('admin-cotizaciones'), {'pagina': 2}).data

        self.assertEqual((primera['count'], len(primera['results'])), (23, 20))
        self.assertIsNotNone(primera['next'])
        self.assertEqual(len(segunda['results']), 3)
        self.assertIsNone(segunda['next'])

    def test_la_tienda_registra_en_que_quedo(self):
        url = reverse('admin-cotizacion-estado', args=[self.antigua.id])

        response = self.client.patch(url, {'estado': 'RESPONDIDA'}, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['estado_display'], 'Respondida')
        self.antigua.refresh_from_db()
        self.assertEqual(self.antigua.estado, 'RESPONDIDA')

    def test_estado_invalido_o_cotizacion_inexistente(self):
        url = reverse('admin-cotizacion-estado', args=[self.antigua.id])
        self.assertEqual(self.client.patch(url, {'estado': 'PAGADA'}, format='json').status_code, 400)
        url = reverse('admin-cotizacion-estado', args=[9999])
        self.assertEqual(self.client.patch(url, {'estado': 'ACEPTADA'}, format='json').status_code, 404)

    def test_solo_el_admin_las_ve_y_las_cambia(self):
        self.client.force_authenticate(create_user('comprador-cotiza@example.test'))
        self.assertEqual(self.client.get(reverse('admin-cotizaciones')).status_code, 403)
        url = reverse('admin-cotizacion-estado', args=[self.antigua.id])
        self.assertEqual(self.client.patch(url, {'estado': 'ACEPTADA'}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(reverse('admin-cotizaciones')).status_code, (401, 403))


def archivo_imagen(nombre='idea.jpg', formato='JPEG', exif=None):
    """Una foto real de 40 x 30; con `exif`, como las de un celular (ej. con la ubicación GPS)."""
    salida = BytesIO()
    imagen = Image.new('RGB', (40, 30), (200, 80, 60))
    opciones = {'exif': exif} if exif is not None else {}
    imagen.save(salida, format=formato, **opciones)
    tipo = {'JPEG': 'image/jpeg', 'PNG': 'image/png'}[formato]
    return SimpleUploadedFile(nombre, salida.getvalue(), content_type=tipo)


@patch.dict('os.environ', {'FRONTEND_URL': 'http://tienda.test'})
class FotosCotizacionTests(APITestCase):
    """El cliente adjunta hasta 3 fotos de su idea; solo las ve la tienda (no quedan en /media/, que es público)."""

    def setUp(self):
        cache.clear()
        ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda QA', cotizaciones_activas=True,
                                           correo_contacto='hola@tienda.test')
        productos = patch('ecommerce.infrastructure.ventas.views.MongoNombresProductos', ProductosFalsos)
        productos.start()
        self.addCleanup(productos.stop)
        self.privado = Path(tempfile.mkdtemp())
        self.media = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.privado, True)
        self.addCleanup(shutil.rmtree, self.media, True)
        carpetas = override_settings(ARCHIVOS_PRIVADOS_ROOT=self.privado, MEDIA_ROOT=self.media)
        carpetas.enable()
        self.addCleanup(carpetas.disable)

    def enviar(self, fotos, datos=None):
        cuerpo = {'datos': json.dumps(datos if datos is not None else SOLICITUD), 'fotos': fotos}
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('cotizaciones'), cuerpo, format='multipart')

    def archivos(self, carpeta):
        return [ruta for ruta in carpeta.rglob('*') if ruta.is_file()]

    def test_guarda_las_fotos_en_la_carpeta_privada_y_avisa_cuantas_son(self):
        response = self.enviar([archivo_imagen(), archivo_imagen('ref.png', 'PNG')])

        self.assertEqual(response.status_code, 201, response.data)
        cotizacion = Cotizacion.objects.get()
        self.assertEqual(cotizacion.fotos.count(), 2)
        self.assertEqual(len(self.archivos(self.privado)), 2)
        self.assertEqual(self.archivos(self.media), [])
        # El nombre del archivo es al azar: no es el que puso el cliente
        self.assertNotIn('idea', ' '.join(foto.ruta for foto in cotizacion.fotos.all()))
        tienda, cliente = mail.outbox
        self.assertIn('Fotos: 2 adjuntas', tienda.body)
        self.assertEqual(tienda.attachments, [])

    def test_sin_fotos_sigue_funcionando_como_antes(self):
        self.assertEqual(self.enviar([]).status_code, 201)
        self.assertEqual(Cotizacion.objects.get().fotos.count(), 0)

    def test_rechaza_mas_de_tres_fotos_o_archivos_que_no_son_imagenes(self):
        falsa = SimpleUploadedFile('idea.png', b'no soy una imagen', content_type='image/png')
        for fotos in ([archivo_imagen() for _ in range(4)], [falsa]):
            with self.subTest(fotos=len(fotos)):
                response = self.enviar(fotos)
                self.assertEqual(response.status_code, 400)
                self.assertIn('fotos', response.data)
        self.assertFalse(Cotizacion.objects.exists())
        self.assertEqual(self.archivos(self.privado), [])

    def test_quita_los_datos_de_la_camara_como_la_ubicacion(self):
        exif = Image.Exif()
        exif[0x8825] = {2: (33.0, 26.0, 0.0)}  # GPSInfo: una latitud
        exif[0x010F] = 'Marca del celular'
        self.assertEqual(self.enviar([archivo_imagen(exif=exif.tobytes())]).status_code, 201)
        guardada, = self.archivos(self.privado)
        with Image.open(guardada) as imagen:
            self.assertEqual(dict(imagen.getexif()), {})

    def test_datos_que_no_son_json_se_rechazan(self):
        cuerpo = {'datos': 'no es json', 'fotos': [archivo_imagen()]}
        response = self.client.post(reverse('cotizaciones'), cuerpo, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Cotizacion.objects.exists())

    def test_el_campo_trampa_con_fotos_no_guarda_nada(self):
        response = self.enviar([archivo_imagen()], datos={**SOLICITUD, 'sitio_web': 'http://spam.test'})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(Cotizacion.objects.exists())
        self.assertEqual(self.archivos(self.privado), [])

    def test_solo_el_admin_ve_las_fotos_y_con_cabeceras_seguras(self):
        self.enviar([archivo_imagen()])
        cotizacion = Cotizacion.objects.get()
        foto = cotizacion.fotos.get()
        url = reverse('admin-foto-cotizacion', args=[cotizacion.id, foto.id])

        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(create_user('comprador-fotos@example.test'))
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(create_user('admin-fotos@example.test', rol='ADMIN'))
        listado = self.client.get(reverse('admin-cotizaciones')).data['results']
        self.assertEqual(listado[0]['fotos'], [foto.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', response['Content-Security-Policy'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(b''.join(response.streaming_content).startswith(bytes([0xFF, 0xD8])))
        # Una foto pedida con el número de otra cotización no se entrega
        otra = Cotizacion.objects.create(nombre='Luis', correo='l@example.test', telefono='+56912345678', cantidad=1)
        self.assertEqual(self.client.get(reverse('admin-foto-cotizacion', args=[otra.id, foto.id])).status_code, 404)

