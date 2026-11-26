from django.urls import reverse
from rest_framework.test import APITestCase
from ecommerce.infrastructure.usuarios.tests.factories import create_user
from .models import ConfiguracionGlobal
from .serializers import ConfiguracionNegocioSerializer


class MenuPrincipalTests(APITestCase):
    def setUp(self):
        self.config = ConfiguracionGlobal.objects.create(pk=1, nombre_tienda='Tienda')
        self.orden = ['inicio', 'catalogo', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion']

    def test_validacion_y_normalizacion(self):
        invalidos = [None, [], {'ruta': '/'},
                     {'orden': ['inicio'] * 5}, {'orden': self.orden[:-1] + [{}]},
                     {'nombres': {'otro': 'Texto'}}, {'nombres': {'inicio': 1}},
                     {'nombres': {'inicio': 'x' * 31}}, {'nombres': {'inicio': 'Portada'}}, {'orden': 'inicio'},
                     {'nombres': []}, {'ocultos': None}, {'ocultos': 'cotizar'},
                     {'ocultos': ['inicio']}, {'ocultos': ['catalogo']}, {'ocultos': ['otro']},
                     {'ocultos': ['cotizar', 'cotizar']}, {'ocultos': [{}]}]
        for valor in invalidos:
            with self.subTest(valor=valor):
                serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': valor}, partial=True)
                self.assertFalse(serializer.is_valid())
                self.assertIn('menu_principal', serializer.errors)
        serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': {
            'orden': self.orden, 'nombres': {'catalogo': '  Mis   productos '}}}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['menu_principal']['nombres'], {'catalogo': 'Mis productos'})

    def test_permisos_persistencia_y_compatibilidad(self):
        url = reverse('configuracion-negocio')
        datos = {'menu_principal': {'orden': self.orden[::-1], 'nombres': {'catalogo': 'Productos'}}}
        self.assertEqual(self.client.patch(url, datos, format='json').status_code, 401)
        self.client.force_authenticate(create_user('cliente-menu@example.test'))
        self.assertEqual(self.client.patch(url, datos, format='json').status_code, 403)
        self.client.force_authenticate(create_user('admin-menu@example.test', rol='ADMIN'))
        self.assertEqual(self.client.patch(url, datos, format='json').status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, datos['menu_principal'])
        self.assertEqual(self.config.nombre_tienda, 'Tienda')
        self.client.patch(url, {'nombre_tienda': 'Nueva'}, format='json')
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, datos['menu_principal'])
        self.client.force_authenticate(None)
        respuesta = self.client.get(reverse('configuracion-global'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data['menu_principal'], datos['menu_principal'])

    def test_configuracion_anterior_y_restauracion(self):
        self.assertEqual(self.config.menu_principal, {})
        self.client.force_authenticate(create_user('restaurar-menu@example.test', rol='ADMIN'))
        url = reverse('configuracion-negocio')
        self.client.patch(url, {'menu_principal': {'nombres': {'catalogo': 'Productos'}}}, format='json')
        self.assertEqual(self.client.patch(url, {'menu_principal': {}}, format='json').status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, {})

    def test_visibilidad_se_guarda_en_el_menu_sin_activar_modulos(self):
        self.client.force_authenticate(create_user('visibilidad-menu@example.test', rol='ADMIN'))
        respuesta = self.client.patch(reverse('configuracion-negocio'), {
            'menu_principal': {'ocultos': ['nosotros', 'sobre_mi', 'cotizar'], 'nombres': {'catalogo': '  Productos  '}}
        }, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal['ocultos'], ['nosotros', 'sobre_mi', 'cotizar'])
        self.assertEqual(self.config.menu_principal['nombres']['catalogo'], 'Productos')
        self.assertFalse(self.config.blog_activo)
        self.assertFalse(self.config.sobre_mi_activo)
        self.assertFalse(self.config.cotizaciones_activas)
        respuesta = self.client.patch(reverse('configuracion-negocio'), {
            'menu_principal': '{"orden": ["catalogo", "inicio", "nosotros", "sobre_mi", "cotizar"], "ocultos": []}'
        }, format='multipart')
        self.assertEqual(respuesta.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal['ocultos'], [])
        self.assertEqual(self.config.menu_principal['orden'][0], 'catalogo')

    def test_solo_se_renombra_catalogo_hasta_20_caracteres(self):
        self.client.force_authenticate(create_user('limite-catalogo@example.test', rol='ADMIN'))
        url = reverse('configuracion-negocio')
        nombres = {'catalogo': 'x' * 20}
        respuesta = self.client.patch(url, {'menu_principal': {'nombres': nombres}}, format='json')
        self.assertEqual(respuesta.status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal['nombres'], nombres)
        # El blog y Sobre mí se nombran en su propio módulo; Inicio y Cotizar son fijos
        for clave in ['inicio', 'nosotros', 'sobre_mi', 'cotizar']:
            with self.subTest(clave=clave):
                respuesta = self.client.patch(url, {'menu_principal': {'nombres': {clave: 'Otro'}}}, format='json')
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn('Catálogo', str(respuesta.data['menu_principal']))
        respuesta = self.client.patch(url, {'menu_principal': {'nombres': {'catalogo': 'y' * 21}}}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('20', str(respuesta.data['menu_principal']))
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal['nombres'], nombres)

    def test_conserva_catalogo_antiguo_largo_al_reordenar_y_permite_reemplazarlo(self):
        anterior = 'Nuestra colección especial'
        self.config.menu_principal = {'nombres': {'catalogo': anterior}}
        self.config.save(update_fields=['menu_principal'])
        self.client.force_authenticate(create_user('catalogo-antiguo@example.test', rol='ADMIN'))
        url = reverse('configuracion-negocio')
        publica = self.client.get(reverse('configuracion-global'))
        self.assertEqual(publica.data['menu_principal']['nombres']['catalogo'], anterior)
        menu = {'nombres': {'catalogo': anterior}, 'orden': self.orden[::-1]}
        self.assertEqual(self.client.patch(url, {'menu_principal': menu}, format='json').status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, menu)
        self.assertEqual(self.client.patch(url, {'texto_bienvenida': 'Nuevo título'}, format='json').status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, menu)
        respuesta = self.client.patch(url, {'menu_principal': {'nombres': {'catalogo': 'Otro catálogo demasiado largo'}}}, format='json')
        self.assertEqual(respuesta.status_code, 400)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, menu)
        menu['nombres']['catalogo'] = 'Artículos'
        self.assertEqual(self.client.patch(url, {'menu_principal': menu}, format='json').status_code, 200)
        self.config.refresh_from_db()
        self.assertEqual(self.config.menu_principal, menu)

    def test_orden_incompleto_agrega_faltantes_sin_alterar_la_entrada(self):
        for orden, esperado in [
            (['catalogo', 'inicio'], ['catalogo', 'inicio', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion']),
            (['sobre_mi', 'cotizar'], ['sobre_mi', 'cotizar', 'inicio', 'catalogo', 'nosotros', 'suscripcion']),
        ]:
            with self.subTest(orden=orden):
                entrada = list(orden)
                serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': {'orden': entrada}}, partial=True)
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data['menu_principal']['orden'], esperado)
                self.assertEqual(entrada, orden)

    def test_orden_vacio_se_completa_con_el_predeterminado(self):
        serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': {'orden': []}}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['menu_principal']['orden'], self.orden)

    def test_orden_completo_conserva_su_orden(self):
        for orden in [self.orden, self.orden[::-1]]:
            with self.subTest(orden=orden):
                serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': {'orden': orden}}, partial=True)
                self.assertTrue(serializer.is_valid(), serializer.errors)
                self.assertEqual(serializer.validated_data['menu_principal']['orden'], orden)

    def test_orden_rechaza_duplicados_desconocidos_y_valores_no_textuales(self):
        for orden in [['inicio', 'inicio'], ['otro'], ['catalogo', 'otro'], ['inicio', 1],
                      ['inicio', None], ['inicio', {}], ['inicio', []], [True]]:
            with self.subTest(orden=orden):
                serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': {'orden': orden}}, partial=True)
                self.assertFalse(serializer.is_valid())
                self.assertIn('menu_principal', serializer.errors)

    def test_orden_rechaza_valores_que_no_sean_listas(self):
        for orden in [None, 'inicio', {}, ('inicio',), 1, True]:
            with self.subTest(orden=orden):
                serializer = ConfiguracionNegocioSerializer(self.config, data={'menu_principal': {'orden': orden}}, partial=True)
                self.assertFalse(serializer.is_valid())
                self.assertIn('menu_principal', serializer.errors)

    def test_endpoint_persiste_orden_completado_con_nombres_y_ocultos(self):
        anterior = 'Nuestra colección especial'
        self.config.menu_principal = {'nombres': {'catalogo': anterior}}
        self.config.save(update_fields=['menu_principal'])
        self.client.force_authenticate(create_user('completar-menu@example.test', rol='ADMIN'))
        for orden, esperado in [([], self.orden), (['catalogo', 'inicio'], ['catalogo', 'inicio', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion'])]:
            with self.subTest(orden=orden):
                respuesta = self.client.patch(reverse('configuracion-negocio'), {'menu_principal': {
                    'orden': orden, 'nombres': {'catalogo': anterior}, 'ocultos': ['sobre_mi']
                }}, format='json')
                self.assertEqual(respuesta.status_code, 200)
                menu_esperado = {'orden': esperado, 'nombres': {'catalogo': anterior}, 'ocultos': ['sobre_mi']}
                self.assertEqual(respuesta.data['menu_principal'], menu_esperado)
                self.config.refresh_from_db()
                self.assertEqual(self.config.menu_principal, menu_esperado)
