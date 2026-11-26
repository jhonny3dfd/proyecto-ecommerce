"""Alta, edicion y contrasenas mediante las vistas de UserAdmin de Django."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.urls import reverse

from ..forms import UsuarioChangeForm, UsuarioCreationForm
from ..models import Usuario
from .factories import PASSWORD, create_user


NUEVA_PASSWORD = 'Cambio-QA-177!937-ficticio'


class UsuarioAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superusuario = create_user(
            'superusuario@example.test', rol='ADMIN', is_staff=True, is_superuser=True,
        )
        cls.usuario = create_user('alicia@example.test', nombre='Alicia', google_sso_id='google-qa-177')

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.superusuario)
        self.alta = reverse('admin:usuarios_usuario_add')
        self.edicion = reverse('admin:usuarios_usuario_change', args=[self.usuario.pk])

    def post_con_csrf(self, url, datos):
        self.client.get(url)
        return self.client.post(url, {
            **datos, 'csrfmiddlewaretoken': self.client.cookies['csrftoken'].value,
        })

    def datos_alta(self, **cambios):
        datos = {
            'email': 'nueva-cuenta@example.test', 'nombre': 'Carla',
            'apellido_paterno': 'Perez', 'apellido_materno': 'Prueba', 'telefono': '+56912345678',
            'rol': 'COMPRADOR', 'usable_password': 'true',
            'password1': PASSWORD, 'password2': PASSWORD, '_save': 'Guardar',
        }
        datos.update(cambios)
        return datos

    def password_url(self, usuario=None):
        return reverse('admin:auth_user_password_change', args=[(usuario or self.usuario).pk])

    def cambiar_password(self, usuario=None, **cambios):
        datos = {
            'usable_password': 'true', 'password1': NUEVA_PASSWORD, 'password2': NUEVA_PASSWORD,
            'set-password': 'Cambiar contrasena',
        }
        datos.update(cambios)
        return self.post_con_csrf(self.password_url(usuario), datos)

    def test_registro_y_formularios_adaptados_a_todos_los_campos_de_usuario(self):
        configuracion = admin.site._registry[Usuario]
        self.assertIsInstance(configuracion, UserAdmin)
        self.assertIs(configuracion.change_password_form, AdminPasswordChangeForm)
        for url, clase in ((self.alta, UsuarioCreationForm), (self.edicion, UsuarioChangeForm)):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                formulario = respuesta.context['adminform'].form
                self.assertIsInstance(formulario, clase)
                for campo in ('email', 'nombre', 'apellido_paterno', 'apellido_materno', 'telefono', 'rol'):
                    self.assertIn(campo, formulario.fields)
                for campo in ('username', 'first_name', 'last_name', 'date_joined', 'last_login'):
                    self.assertNotIn(campo, formulario.fields)

    def test_alta_desde_admin_hash_argon2_e_inicio_de_sesion_por_email(self):
        respuesta = self.post_con_csrf(self.alta, self.datos_alta())
        self.assertEqual(respuesta.status_code, 302)
        usuario = Usuario.objects.get(email='nueva-cuenta@example.test')
        self.assertEqual(identify_hasher(usuario.password).algorithm, 'argon2')
        self.assertTrue(usuario.check_password(PASSWORD))
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertTrue(Client().login(email=usuario.email, password=PASSWORD))

    def test_alta_invalida_muestra_errores_y_no_crea_cuenta(self):
        respuesta = self.post_con_csrf(self.alta, self.datos_alta(password2='No-coincide-177!'))
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('password2', respuesta.context['adminform'].form.errors)
        self.assertFalse(Usuario.objects.filter(email='nueva-cuenta@example.test').exists())

    def test_edicion_legitima_de_datos_y_permisos_no_acepta_password_directo(self):
        grupo = Group.objects.create(name='Grupo QA 177')
        permiso = Permission.objects.get(codename='change_ordencompra')
        hash_anterior = self.usuario.password
        respuesta = self.post_con_csrf(self.edicion, {
            'email': self.usuario.email, 'nombre': 'Alicia corregida',
            'apellido_paterno': self.usuario.apellido_paterno, 'apellido_materno': self.usuario.apellido_materno,
            'telefono': '+56987654321', 'rol': 'ADMIN', 'google_sso_id': 'google-qa-177',
            'acepta_cookies': 'on', 'is_active': 'on', 'is_staff': 'on',
            'groups': [grupo.pk], 'user_permissions': [permiso.pk],
            'password': 'texto-plano-inyectado', 'last_login': '2000-01-01 00:00:00', '_save': 'Guardar',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.nombre, self.usuario.telefono, self.usuario.rol),
                         ('Alicia corregida', '+56987654321', 'ADMIN'))
        self.assertTrue(self.usuario.is_staff)
        self.assertTrue(self.usuario.acepta_cookies)
        self.assertEqual(self.usuario.google_sso_id, 'google-qa-177')
        self.assertEqual(list(self.usuario.groups.all()), [grupo])
        self.assertEqual(list(self.usuario.user_permissions.all()), [permiso])
        self.assertIsNone(self.usuario.last_login)
        self.assertEqual(self.usuario.password, hash_anterior)
        self.assertTrue(self.usuario.check_password(PASSWORD))

    def test_cambio_con_formulario_estandar_guarda_argon2_y_permite_login_jwt(self):
        vista = self.client.get(self.password_url())
        self.assertEqual(vista.status_code, 200)
        self.assertIsInstance(vista.context['form'], AdminPasswordChangeForm)
        hash_anterior = self.usuario.password
        self.assertEqual(self.cambiar_password().status_code, 302)
        self.usuario.refresh_from_db()
        self.assertNotEqual(self.usuario.password, hash_anterior)
        self.assertEqual(identify_hasher(self.usuario.password).algorithm, 'argon2')
        self.assertTrue(self.usuario.check_password(NUEVA_PASSWORD))
        self.assertFalse(self.usuario.check_password(PASSWORD))
        self.assertEqual(self.usuario.google_sso_id, 'google-qa-177')
        cliente = Client()
        self.assertFalse(cliente.login(email=self.usuario.email, password=PASSWORD))
        self.assertTrue(cliente.login(email=self.usuario.email, password=NUEVA_PASSWORD))
        jwt = cliente.post(reverse('token_obtain_pair'), {
            'email': self.usuario.email, 'password': NUEVA_PASSWORD,
        })
        self.assertEqual(jwt.status_code, 200)
        self.assertIn('access', jwt.json())

    def test_contrasenas_invalidas_no_cambian_el_hash(self):
        hash_anterior = self.usuario.password
        for cambios in (
            {'password2': 'Confirmacion-distinta-177!'},
            {'password1': '12345678', 'password2': '12345678'},
            {'password1': '', 'password2': ''},
        ):
            with self.subTest(cambios=cambios):
                respuesta = self.cambiar_password(**cambios)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(respuesta.context['form'].errors)
                self.usuario.refresh_from_db()
                self.assertEqual(self.usuario.password, hash_anterior)

    def test_cambio_de_clave_propia_conserva_sesion_del_superusuario(self):
        self.assertEqual(self.cambiar_password(self.superusuario).status_code, 302)
        self.superusuario.refresh_from_db()
        self.assertEqual(identify_hasher(self.superusuario.password).algorithm, 'argon2')
        self.assertTrue(self.superusuario.check_password(NUEVA_PASSWORD))
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 200)

    def test_cuenta_sso_se_puede_editar_y_establecer_clave_con_formulario_estandar(self):
        self.usuario.set_unusable_password()
        self.usuario.save(update_fields=['password'])
        self.assertEqual(self.client.get(self.edicion).status_code, 200)
        self.assertEqual(self.cambiar_password().status_code, 302)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(NUEVA_PASSWORD))
        self.assertEqual(identify_hasher(self.usuario.password).algorithm, 'argon2')
        self.assertEqual(self.usuario.google_sso_id, 'google-qa-177')

    def test_listado_busca_filtra_y_ordena_por_campos_existentes(self):
        listado = reverse('admin:usuarios_usuario_changelist')
        respuesta = self.client.get(listado)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([u.email for u in respuesta.context['cl'].result_list],
                         ['alicia@example.test', 'superusuario@example.test'])
        for consulta in ({'q': 'Alicia'}, {'rol__exact': 'COMPRADOR'}):
            resultado = self.client.get(listado, consulta)
            self.assertEqual([u.pk for u in resultado.context['cl'].result_list], [self.usuario.pk])

    def test_usuario_no_autorizado_no_cambia_claves_y_post_sin_csrf_se_rechaza(self):
        self.assertEqual(self.client.post(self.password_url(), {}).status_code, 403)
        hash_anterior = self.usuario.password
        staff = create_user('staff-sin-permisos@example.test', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.password_url()).status_code, 403)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(self.edicion).status_code, 302)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.password, hash_anterior)
