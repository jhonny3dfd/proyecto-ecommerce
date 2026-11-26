from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from ecommerce.infrastructure.usuarios.tests.factories import create_user

from .html_seguro import limpiar_html, tiene_texto
from .models import PaginaLegal

# Lo que escribe React Quill 2: listas como <ol> con data-list y la viñeta en span.ql-ui
LISTA_QUILL = ('<ol><li data-list="bullet"><span class="ql-ui" contenteditable="false"></span>uno</li>'
               '<li data-list="ordered" class="ql-indent-1"><span class="ql-ui" contenteditable="false"></span>'
               'dos</li></ol>')


class LimpiarHtmlTests(SimpleTestCase):
    def test_conserva_el_formato_del_editor(self):
        html = '<h2 class="ql-align-center">Título</h2><p>Texto <strong>fuerte</strong> y <em>énfasis</em></p>'
        self.assertEqual(limpiar_html(html), html)
        self.assertEqual(
            limpiar_html(LISTA_QUILL),
            '<ol><li data-list="bullet"><span class="ql-ui"></span>uno</li>'
            '<li data-list="ordered" class="ql-indent-1"><span class="ql-ui"></span>dos</li></ol>')

    def test_elimina_scripts_eventos_y_enlaces_peligrosos(self):
        limpio = limpiar_html(
            '<p>x<script>alert(1)</script><img src=x onerror="alert(1)"></p>'
            '<a href="javascript:alert(1)">malo</a><a href="https://ok.cl" onclick="x()">bueno</a>'
            '<p style="color:red" class="ql-align-center otra">y</p><iframe src="https://a"></iframe>')
        for peligroso in ('script', 'onerror', 'img', 'javascript', 'onclick', 'style', 'otra', 'iframe'):
            self.assertNotIn(peligroso, limpio)
        self.assertIn('<a href="https://ok.cl" rel="noopener noreferrer">bueno</a>', limpio)
        self.assertIn('<p class="ql-align-center">y</p>', limpio)

    def test_valores_de_lista_desconocidos_se_descartan(self):
        self.assertEqual(limpiar_html('<ol><li data-list="evil">y</li></ol>'), '<ol><li>y</li></ol>')

    def test_editor_vacio_no_tiene_texto(self):
        for vacio in ('', '<p><br></p>', '<p>&nbsp; </p>', '<p><script>x</script></p>'):
            with self.subTest(vacio=vacio):
                self.assertFalse(tiene_texto(vacio))
        self.assertTrue(tiene_texto('<p>Hola</p>'))


class PaginasLegalesAPITests(APITestCase):
    """RF-03.5: el admin redacta y publica; el público solo ve las páginas publicadas."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_token = Token.objects.create(user=create_user('admin@example.test', rol='ADMIN'))
        cls.buyer_token = Token.objects.create(user=create_user())

    def autenticar(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def guardar(self, tipo, **datos):
        datos = {'titulo': 'Términos y Condiciones', 'contenido': '<p>Texto legal</p>', 'publicada': False, **datos}
        return self.client.put(reverse('admin-pagina-legal', args=[tipo]), datos, format='json')

    def test_el_publico_solo_ve_las_publicadas(self):
        PaginaLegal.objects.create(tipo_pagina='TERMINOS', titulo='Términos', contenido='<p>a</p>', publicada=True)
        PaginaLegal.objects.create(tipo_pagina='PRIVACIDAD', titulo='Privacidad', contenido='<p>b</p>')

        listado = self.client.get(reverse('paginas-legales-publicas'))
        self.assertEqual([p['tipo_pagina'] for p in listado.data], ['TERMINOS'])
        self.assertNotIn('contenido', listado.data[0])

        detalle = self.client.get(reverse('pagina-legal-detalle', args=['terminos']))
        self.assertEqual(detalle.status_code, 200)
        self.assertEqual(detalle.data['contenido'], '<p>a</p>')
        for tipo in ('privacidad', 'reembolsos', 'otra'):
            with self.subTest(tipo=tipo):
                self.assertEqual(self.client.get(reverse('pagina-legal-detalle', args=[tipo])).status_code, 404)

    def test_admin_crea_publica_y_despublica_con_el_html_limpio(self):
        self.autenticar(self.admin_token)
        creada = self.guardar('terminos', contenido='<p>Hola<script>alert(1)</script></p>')
        self.assertEqual(creada.status_code, 201, creada.data)
        self.assertEqual(creada.data['contenido'], '<p>Hola</p>')
        self.assertEqual(self.client.get(reverse('paginas-legales-publicas')).data, [])

        publicada = self.guardar('TERMINOS', publicada=True)
        self.assertEqual(publicada.status_code, 200)
        self.assertEqual(len(self.client.get(reverse('paginas-legales-publicas')).data), 1)

        self.guardar('terminos', publicada=False)
        self.assertEqual(self.client.get(reverse('paginas-legales-publicas')).data, [])
        self.assertEqual(PaginaLegal.objects.count(), 1)

    def test_no_se_publica_una_pagina_vacia(self):
        self.autenticar(self.admin_token)
        response = self.guardar('privacidad', contenido='<p><br></p>', publicada=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn('contenido', response.data)
        self.assertEqual(self.guardar('privacidad', contenido='<p><br></p>').status_code, 201)

    def test_listado_del_admin_incluye_las_paginas_sin_redactar(self):
        self.autenticar(self.admin_token)
        self.guardar('terminos', publicada=True)
        paginas = self.client.get(reverse('admin-paginas-legales')).data
        self.assertEqual([(p['tipo_pagina'], p['publicada']) for p in paginas],
                         [('TERMINOS', True), ('PRIVACIDAD', False), ('REEMBOLSOS', False)])
        self.assertEqual(paginas[1]['titulo'], 'Política de Privacidad')

    def test_solo_el_admin_edita_y_el_tipo_debe_existir(self):
        self.assertEqual(self.guardar('terminos').status_code, 401)
        self.autenticar(self.buyer_token)
        self.assertEqual(self.guardar('terminos').status_code, 403)
        self.assertEqual(self.client.get(reverse('admin-paginas-legales')).status_code, 403)
        self.autenticar(self.admin_token)
        self.assertEqual(self.guardar('otra').status_code, 404)
        self.assertFalse(PaginaLegal.objects.exists())
