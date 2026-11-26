from django.test import SimpleTestCase

from ecommerce.application.cuentas import (
    CambiarContrasena, ContrasenaActualIncorrecta, ContrasenaInvalida, CuentasUsuario, EnlaceInvalido,
    EnlacesRestablecimiento, NotificadorCuentas, RestablecerContrasena, SolicitarRestablecimiento,
    ValidadorContrasenas,
)

ANA, GOOGLE = 1, 2


class CuentasFalsas(CuentasUsuario):
    def __init__(self):
        # Ana tiene contraseña; la cuenta 2 se creó con Google y no tiene
        self.contrasenas = {ANA: 'clave-antigua-123', GOOGLE: None}
        self.correos = {'ana@example.test': ANA, 'google@example.test': GOOGLE}

    def buscar_activa_por_correo(self, correo):
        return self.correos.get(correo.lower())

    def tiene_contrasena(self, usuario_id):
        return self.contrasenas[usuario_id] is not None

    def contrasena_correcta(self, usuario_id, contrasena):
        return self.contrasenas[usuario_id] is not None and self.contrasenas[usuario_id] == contrasena

    def cambiar_contrasena(self, usuario_id, contrasena):
        self.contrasenas[usuario_id] = contrasena


class EnlacesFalsos(EnlacesRestablecimiento):
    def __init__(self, cuentas):
        self.cuentas = cuentas

    def crear(self, usuario_id):
        return f'https://tienda.test/restablecer-contrasena?uid={usuario_id}&token=t{usuario_id}'

    def usuario_del_enlace(self, uid, token):
        # Como el de Django: el enlace solo sirve mientras la contraseña sea la misma que cuando se creó
        return int(uid) if token == f't{uid}' and self.cuentas.contrasenas.get(int(uid)) in (None, 'clave-antigua-123') else None


class ValidadorFalso(ValidadorContrasenas):
    def errores(self, contrasena, usuario_id):
        return ['Esta contraseña es demasiado corta.'] if len(contrasena) < 8 else []


class NotificadorFalso(NotificadorCuentas):
    def __init__(self):
        self.enlaces = []
        self.cambios = []

    def enviar_enlace(self, usuario_id, enlace):
        self.enlaces.append((usuario_id, enlace))

    def avisar_cambio(self, usuario_id):
        self.cambios.append(usuario_id)


class BaseCuentas(SimpleTestCase):
    def setUp(self):
        self.cuentas = CuentasFalsas()
        self.enlaces = EnlacesFalsos(self.cuentas)
        self.notificador = NotificadorFalso()


class SolicitarRestablecimientoTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.caso = SolicitarRestablecimiento(self.cuentas, self.enlaces, self.notificador)

    def test_envia_el_enlace_a_la_cuenta_del_correo_sin_distinguir_mayusculas_ni_espacios(self):
        self.caso.ejecutar('  Ana@Example.test ')
        self.assertEqual(self.notificador.enlaces,
                         [(ANA, 'https://tienda.test/restablecer-contrasena?uid=1&token=t1')])

    def test_un_correo_sin_cuenta_o_vacio_no_envia_nada_ni_falla(self):
        self.caso.ejecutar('nadie@example.test')
        self.caso.ejecutar('')
        self.caso.ejecutar(None)
        self.assertEqual(self.notificador.enlaces, [])

    def test_una_cuenta_de_google_sin_contrasena_tambien_recibe_el_enlace(self):
        self.caso.ejecutar('google@example.test')
        self.assertEqual([usuario for usuario, _ in self.notificador.enlaces], [GOOGLE])


class RestablecerContrasenaTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.caso = RestablecerContrasena(self.cuentas, self.enlaces, ValidadorFalso(), self.notificador)

    def test_con_un_enlace_valido_guarda_la_nueva_y_avisa_del_cambio(self):
        self.caso.ejecutar('1', 't1', 'clave-nueva-456', 'clave-nueva-456')
        self.assertEqual(self.cuentas.contrasenas[ANA], 'clave-nueva-456')
        self.assertEqual(self.notificador.cambios, [ANA])

    def test_el_enlace_sirve_una_sola_vez(self):
        self.caso.ejecutar('1', 't1', 'clave-nueva-456', 'clave-nueva-456')
        with self.assertRaises(EnlaceInvalido):
            self.caso.ejecutar('1', 't1', 'otra-clave-789', 'otra-clave-789')
        self.assertEqual(self.cuentas.contrasenas[ANA], 'clave-nueva-456')

    def test_un_enlace_alterado_no_cambia_nada(self):
        with self.assertRaises(EnlaceInvalido):
            self.caso.ejecutar('1', 'inventado', 'clave-nueva-456', 'clave-nueva-456')
        self.assertEqual((self.cuentas.contrasenas[ANA], self.notificador.cambios), ('clave-antigua-123', []))

    def test_una_contrasena_debil_o_que_no_coincide_se_rechaza_con_el_error_de_cada_campo(self):
        with self.assertRaises(ContrasenaInvalida) as error:
            self.caso.ejecutar('1', 't1', 'corta', 'distinta')
        self.assertEqual(error.exception.errores, {'password': ['Esta contraseña es demasiado corta.'],
                                                   'password2': ['Las contraseñas no coinciden.']})
        self.assertEqual(self.cuentas.contrasenas[ANA], 'clave-antigua-123')

    def test_una_cuenta_de_google_crea_su_primera_contrasena(self):
        self.caso.ejecutar('2', 't2', 'clave-nueva-456', 'clave-nueva-456')
        self.assertEqual(self.cuentas.contrasenas[GOOGLE], 'clave-nueva-456')


class CambiarContrasenaTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.caso = CambiarContrasena(self.cuentas, ValidadorFalso(), self.notificador)

    def test_con_la_actual_correcta_guarda_la_nueva_y_avisa_del_cambio(self):
        self.caso.ejecutar(ANA, 'clave-antigua-123', 'clave-nueva-456', 'clave-nueva-456')
        self.assertEqual(self.cuentas.contrasenas[ANA], 'clave-nueva-456')
        self.assertEqual(self.notificador.cambios, [ANA])

    def test_con_la_actual_incorrecta_o_vacia_no_cambia_nada(self):
        for actual in ('equivocada', '', None):
            with self.assertRaises(ContrasenaActualIncorrecta):
                self.caso.ejecutar(ANA, actual, 'clave-nueva-456', 'clave-nueva-456')
        self.assertEqual((self.cuentas.contrasenas[ANA], self.notificador.cambios), ('clave-antigua-123', []))

    def test_la_nueva_debe_ser_valida_coincidir_y_ser_distinta_de_la_actual(self):
        with self.assertRaises(ContrasenaInvalida) as debil:
            self.caso.ejecutar(ANA, 'clave-antigua-123', 'corta', 'corta')
        self.assertIn('password', debil.exception.errores)
        with self.assertRaises(ContrasenaInvalida) as distinta:
            self.caso.ejecutar(ANA, 'clave-antigua-123', 'clave-nueva-456', 'clave-nueva-457')
        self.assertIn('password2', distinta.exception.errores)
        with self.assertRaises(ContrasenaInvalida) as igual:
            self.caso.ejecutar(ANA, 'clave-antigua-123', 'clave-antigua-123', 'clave-antigua-123')
        self.assertEqual(igual.exception.errores,
                         {'password': ['La nueva contraseña debe ser distinta de la actual.']})
        self.assertEqual(self.cuentas.contrasenas[ANA], 'clave-antigua-123')

    def test_una_cuenta_de_google_crea_su_contrasena_sin_que_se_le_pida_la_actual(self):
        self.caso.ejecutar(GOOGLE, '', 'clave-nueva-456', 'clave-nueva-456')
        self.assertEqual(self.cuentas.contrasenas[GOOGLE], 'clave-nueva-456')
        self.assertEqual(self.notificador.cambios, [GOOGLE])
