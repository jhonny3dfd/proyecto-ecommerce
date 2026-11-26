from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()

URL_REGISTRO = '/api/usuarios/registro/'


class RegistroPublicoTests(APITestCase):
    """El registro público solo crea compradores: el rol no se elige desde la petición (RNF-03)."""

    def datos(self, **extra):
        return {
            'email': 'comprador@example.test',
            'nombre': 'Ana',
            'apellido_paterno': 'Pérez',
            'password': 'UnaClave-Larga-2026',
            'password2': 'UnaClave-Larga-2026',
            **extra,
        }

    def test_registro_crea_un_comprador(self):
        respuesta = self.client.post(URL_REGISTRO, self.datos(), format='json')

        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email='comprador@example.test').rol, 'COMPRADOR')

    def test_el_correo_no_distingue_mayusculas_al_registrarse_ni_al_entrar(self):
        respuesta = self.client.post(URL_REGISTRO, self.datos(email=' Comprador@Example.TEST '), format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='comprador@example.test').exists())

        # Una segunda cuenta con otras mayúsculas sería la misma persona
        otra = self.client.post(URL_REGISTRO, self.datos(email='COMPRADOR@example.test'), format='json')
        self.assertEqual(otra.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', otra.data)

        entrada = self.client.post('/api/usuarios/token/', {
            'email': 'COMPRADOR@Example.test', 'password': 'UnaClave-Larga-2026'}, format='json')
        self.assertEqual(entrada.status_code, status.HTTP_200_OK)
        self.assertIn('access', entrada.data)

    def test_cuentas_antiguas_que_solo_difieren_en_mayusculas_entran_con_su_correo_exacto(self):
        # Antes del cambio se podían crear; cada una sigue entrando con el correo tal como se registró
        for email in ('Ana@example.test', 'ana@example.test'):
            usuario = User(email=email, nombre='Ana', apellido_paterno='Pérez')
            usuario.set_password('UnaClave-Larga-2026')
            usuario.save()
        for email in ('Ana@example.test', 'ana@example.test'):
            with self.subTest(email=email):
                entrada = self.client.post('/api/usuarios/token/', {
                    'email': email, 'password': 'UnaClave-Larga-2026'}, format='json')
                self.assertEqual(entrada.status_code, status.HTTP_200_OK)
        self.assertIsNone(User.objects.por_correo('ANA@example.test'))

    def test_nombre_y_apellidos_llevan_letras(self):
        for campo, valor in (('nombre', '12345'), ('apellido_paterno', '<b>x</b>'), ('apellido_materno', 'Pérez2')):
            with self.subTest(campo=campo):
                respuesta = self.client.post(URL_REGISTRO, self.datos(**{campo: valor}), format='json')
                self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(campo, respuesta.data)
        self.assertFalse(User.objects.exists())

    def test_el_telefono_es_opcional_y_si_viene_tiene_que_ser_chileno(self):
        respuesta = self.client.post(URL_REGISTRO, self.datos(telefono='llamame'), format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('telefono', respuesta.data)

        respuesta = self.client.post(URL_REGISTRO, self.datos(telefono='9 1234 5678'), format='json')
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(User.objects.get().telefono, '+56912345678')

    def test_no_se_puede_registrar_un_administrador(self):
        respuesta = self.client.post(URL_REGISTRO, self.datos(rol='ADMIN'), format='json')

        usuario = User.objects.get(email='comprador@example.test')
        self.assertEqual(usuario.rol, 'COMPRADOR')
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(respuesta.data['user']['rol'], 'COMPRADOR')

    def test_no_se_pueden_elegir_permisos_de_staff(self):
        self.client.post(URL_REGISTRO, self.datos(is_staff=True, is_superuser=True), format='json')

        usuario = User.objects.get(email='comprador@example.test')
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
