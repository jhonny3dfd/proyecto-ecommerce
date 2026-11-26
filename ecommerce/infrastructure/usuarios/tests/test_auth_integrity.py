from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class AuthenticationIntegrityTests(TestCase):
    """
    Pruebas de integridad de autenticación (QA)
    
    Verificar que la base de datos rechace correos duplicados, que las contraseñas se guarden encriptadas y que los JWT contengan el payload correcto
    """

    def test_email_no_puede_duplicarse(self):
        """
        Verifica que PostgreSQL rechace un segundo usuario con un correo ya registrado
        """

        User.objects.create_user(
            email="usuario1@test.com",
            password="Password123!",
            nombre="Usuario",
            apellido_paterno="Prueba",
            apellido_materno="",
            rol="COMPRADOR",
        )

        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email="usuario1@test.com",
                password="Password456!",
                nombre="Usuario",
                apellido_paterno="Duplicado",
                apellido_materno="",
                rol="COMPRADOR",
            )

    def test_password_no_se_guarda_en_texto_plano(self):
        """
        Verifica que la contraseña no se almacene en texto plano y que Django pueda comprobarla mediante check_password()
        """

        password = "Password123!"

        user = User.objects.create_user(
            email="password@test.com",
            password=password,
            nombre="Usuario",
            apellido_paterno="Password",
            apellido_materno="",
            rol="COMPRADOR",
        )

        #La contraseña almacenada no debe ser igual a la original
        self.assertNotEqual(user.password, password)

        #Django debe poder verificar correctamente la contraseña
        self.assertTrue(user.check_password(password))

        #Una contraseña incorrecta debe ser rechazada
        self.assertFalse(user.check_password("PasswordIncorrecta123!"))

        #Comprobamos que se esta encriptando la contraseña mediante hash
        self.assertTrue(user.password.startswith("argon2$"))

    def test_jwt_contiene_payload_esperado(self):
        """
        Verifica que el JWT generado por SimpleJWT contenga
        los claims estándar y el identificador del usuario.
        """

        user = User.objects.create_user(
            email="jwt@test.com",
            password="Password123!",
            nombre="Usuario",
            apellido_paterno="JWT",
            apellido_materno="",
            rol="COMPRADOR",
        )

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        payload = access.payload

        #Claims actualmente genera un SimpleJWT
        self.assertEqual(payload["token_type"], "access")
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)
        self.assertIn("jti", payload)

        #El JWT debe identificar al usuario
        self.assertEqual(str(payload["user_id"]), str(user.id))

    def test_jwt_no_contiene_datos_personales_no_configurados(self):
        """
        Documenta que actualmente email, rol y nombre NO forman
        parte del payload del JWT.
        """

        user = User.objects.create_user(
            email="jwt2@test.com",
            password="Password123!",
            nombre="Usuario",
            apellido_paterno="JWT",
            apellido_materno="",
            rol="COMPRADOR",
        )

        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        payload = access.payload

        self.assertNotIn("email", payload)
        self.assertNotIn("rol", payload)
        self.assertNotIn("nombre", payload)