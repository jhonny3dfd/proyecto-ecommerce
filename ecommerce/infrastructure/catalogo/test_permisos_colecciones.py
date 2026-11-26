from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from ecommerce.infrastructure.usuarios.models import Usuario
from . import tests as catalogo_tests
from .documents import Producto
from .permissions import LecturaPublicaEscrituraAdmin
from .views import ProductoListCreateView


class PermisosColeccionesSinBaseTests(SimpleTestCase):
    """JWT y permisos reales; solo la persistencia se sustituye por mocks."""

    def setUp(self):
        self.permisos_originales = ProductoListCreateView.permission_classes
        self.autenticacion_original = ProductoListCreateView.authentication_classes
        self.assertEqual(self.permisos_originales, [LecturaPublicaEscrituraAdmin])
        self.addCleanup(self.comprobar_configuracion_original)
        bloqueo = patch.object(Producto, '_get_collection',
                               side_effect=AssertionError('No debe acceder a MongoDB'))
        bloqueo.start()
        self.addCleanup(bloqueo.stop)

    def comprobar_configuracion_original(self):
        self.assertIs(ProductoListCreateView.permission_classes, self.permisos_originales)
        self.assertEqual(ProductoListCreateView.permission_classes, [LecturaPublicaEscrituraAdmin])
        self.assertIs(ProductoListCreateView.authentication_classes, self.autenticacion_original)

    def test_preparacion_de_colecciones_crea_admin_y_no_muta_permisos(self):
        caso = catalogo_tests.ColeccionesBackendTestCase('test_guardar_colecciones_normalizadas')

        def usuario_sin_guardar(email, password, **campos):
            return Usuario(pk=1, email=email, **campos)

        with (
            patch.object(Usuario.objects, 'create_user', side_effect=usuario_sin_guardar) as crear,
            patch.object(Producto, '_get_collection'),
        ):
            try:
                caso.setUp()
                self.assertEqual(crear.call_args.kwargs['rol'], 'ADMIN')
                self.assertEqual(caso.admin.rol, 'ADMIN')
                self.assertTrue(caso.admin.is_active)
                self.assertTrue(caso.client._credentials['HTTP_AUTHORIZATION'].startswith('Bearer '))
                self.comprobar_configuracion_original()
            finally:
                self.assertTrue(caso.doCleanups())
        self.comprobar_configuracion_original()

    def solicitar_creacion(self, rol):
        # Incluso staff/superuser debe tener el rol de negocio correcto.
        usuario = Usuario(pk=1, email='permisos@example.test', rol=rol,
                          is_active=True, is_staff=True, is_superuser=True)
        cliente = APIClient()
        token = RefreshToken.for_user(usuario).access_token
        cliente.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        with (
            patch.object(Usuario.objects, 'get', return_value=usuario) as obtener_usuario,
            patch('ecommerce.infrastructure.catalogo.views.ProductoSerializer') as serializer,
        ):
            serializer.return_value.data = {'id': 'simulado', 'colecciones': ['Cyber']}
            respuesta = cliente.post('/api/catalogo/productos/', {
                'nombre': 'Producto', 'categoria': 'Electronica', 'colecciones': ['Cyber'],
            }, format='json')
            obtener_usuario.assert_called_once()
        return respuesta, serializer

    def test_admin_con_jwt_firmado_puede_crear(self):
        respuesta, serializer = self.solicitar_creacion('ADMIN')
        self.assertEqual(respuesta.status_code, 201)
        serializer.return_value.is_valid.assert_called_once_with(raise_exception=True)
        serializer.return_value.save.assert_called_once_with()

    def test_comprador_con_jwt_firmado_no_puede_crear(self):
        respuesta, serializer = self.solicitar_creacion('COMPRADOR')
        self.assertEqual(respuesta.status_code, 403)
        serializer.assert_not_called()

    def test_sin_jwt_o_con_jwt_invalido_no_se_crea_producto(self):
        for credencial in ('', 'Bearer token-invalido'):
            with self.subTest(credencial=credencial):
                cliente = APIClient()
                if credencial:
                    cliente.credentials(HTTP_AUTHORIZATION=credencial)
                with patch('ecommerce.infrastructure.catalogo.views.ProductoSerializer') as serializer:
                    respuesta = cliente.post('/api/catalogo/productos/', {
                        'nombre': 'Producto', 'categoria': 'Electronica',
                    }, format='json')
                self.assertEqual(respuesta.status_code, 401)
                serializer.assert_not_called()
