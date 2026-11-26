"""Formularios administrativos con validadores y Argon2 reales."""

from django.contrib.auth.hashers import identify_hasher
from django.test import TestCase

from ..forms import UsuarioChangeForm, UsuarioCreationForm
from ..models import Usuario
from .factories import PASSWORD, create_user


class UsuarioCreationFormTests(TestCase):
    def datos(self, **cambios):
        datos = {
            'email': 'alta-admin@example.test', 'nombre': 'Ana',
            'apellido_paterno': 'Prueba', 'apellido_materno': 'Formulario',
            'telefono': '+56912345678', 'rol': 'COMPRADOR',
            'usable_password': 'true', 'password1': PASSWORD, 'password2': PASSWORD,
        }
        datos.update(cambios)
        return datos

    def test_alta_por_email_guarda_con_argon2_y_datos_propios(self):
        formulario = UsuarioCreationForm(data=self.datos())
        self.assertNotIn('username', formulario.fields)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        usuario = formulario.save()
        usuario.refresh_from_db()
        self.assertEqual(usuario.get_username(), 'alta-admin@example.test')
        self.assertEqual((usuario.nombre, usuario.apellido_paterno, usuario.apellido_materno),
                         ('Ana', 'Prueba', 'Formulario'))
        self.assertEqual(usuario.telefono, '+56912345678')
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertEqual(identify_hasher(usuario.password).algorithm, 'argon2')
        self.assertTrue(usuario.check_password(PASSWORD))

    def test_no_crea_usuario_con_contrasenas_distintas_debiles_o_ausentes(self):
        for cambios in (
            {'password2': 'Otra-clave-que-no-coincide-938!'},
            {'password1': '12345678', 'password2': '12345678'},
            {'password1': '', 'password2': ''},
        ):
            with self.subTest(cambios=cambios):
                formulario = UsuarioCreationForm(data=self.datos(**cambios))
                self.assertFalse(formulario.is_valid())
                self.assertTrue({'password1', 'password2'} & set(formulario.errors))
        self.assertFalse(Usuario.objects.exists())

    def test_email_unico_valido_y_campos_personales_obligatorios(self):
        create_user('ocupado@example.test')
        for campo, valor in (
            ('email', 'ocupado@example.test'), ('email', 'no-es-email'),
            ('nombre', ''), ('apellido_paterno', ''), ('apellido_materno', ''),
        ):
            with self.subTest(campo=campo, valor=valor):
                formulario = UsuarioCreationForm(data=self.datos(**{campo: valor}))
                self.assertFalse(formulario.is_valid())
                self.assertIn(campo, formulario.errors)
        self.assertEqual(Usuario.objects.count(), 1)

    def test_save_sin_commit_no_persiste_y_ya_prepara_el_hash_argon2(self):
        formulario = UsuarioCreationForm(data=self.datos())
        self.assertTrue(formulario.is_valid(), formulario.errors)
        usuario = formulario.save(commit=False)
        self.assertIsNone(usuario.pk)
        self.assertFalse(Usuario.objects.exists())
        self.assertEqual(identify_hasher(usuario.password).algorithm, 'argon2')
        self.assertTrue(usuario.check_password(PASSWORD))

    def test_alta_sin_autenticacion_por_contrasena_conserva_opcion_de_django(self):
        formulario = UsuarioCreationForm(data=self.datos(
            usable_password='false', password1='', password2='',
        ))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        usuario = formulario.save()
        self.assertFalse(usuario.has_usable_password())


class UsuarioChangeFormTests(TestCase):
    def datos(self, usuario, **cambios):
        datos = {
            'email': usuario.email, 'nombre': 'Nombre corregido',
            'apellido_paterno': usuario.apellido_paterno, 'apellido_materno': usuario.apellido_materno,
            'rol': usuario.rol, 'is_active': 'on', 'google_sso_id': usuario.google_sso_id or '',
        }
        datos.update(cambios)
        return datos

    def test_edita_datos_propios_e_ignora_password_inyectado(self):
        usuario = create_user(google_sso_id='identificador-google-ficticio')
        hash_anterior = usuario.password
        formulario = UsuarioChangeForm(instance=usuario, data=self.datos(
            usuario, password='texto-plano-inyectado', telefono='+56987654321', rol='ADMIN',
        ))
        self.assertTrue(formulario.fields['password'].disabled)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        usuario.refresh_from_db()
        self.assertEqual((usuario.nombre, usuario.telefono, usuario.rol),
                         ('Nombre corregido', '+56987654321', 'ADMIN'))
        self.assertEqual(usuario.google_sso_id, 'identificador-google-ficticio')
        self.assertEqual(usuario.password, hash_anterior)
        self.assertEqual(identify_hasher(usuario.password).algorithm, 'argon2')
        self.assertTrue(usuario.check_password(PASSWORD))

    def test_editar_cuenta_sso_no_habilita_contrasena(self):
        usuario = create_user(google_sso_id='solo-google-ficticio')
        usuario.set_unusable_password()
        usuario.save(update_fields=['password'])
        hash_anterior = usuario.password
        formulario = UsuarioChangeForm(instance=usuario, data=self.datos(usuario, password=PASSWORD))
        self.assertTrue(formulario.is_valid(), formulario.errors)
        formulario.save()
        usuario.refresh_from_db()
        self.assertEqual(usuario.password, hash_anterior)
        self.assertFalse(usuario.has_usable_password())
        self.assertEqual(usuario.google_sso_id, 'solo-google-ficticio')

    def test_edicion_rechaza_email_duplicado(self):
        usuario = create_user()
        create_user('otro@example.test')
        formulario = UsuarioChangeForm(instance=usuario, data=self.datos(usuario, email='otro@example.test'))
        self.assertFalse(formulario.is_valid())
        self.assertIn('email', formulario.errors)
