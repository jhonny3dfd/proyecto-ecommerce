"""Casos de uso de la contraseña de una cuenta: recuperarla por correo si se olvidó y cambiarla con la sesión iniciada.

Sirven igual para compradores y para el emprendedor. Una cuenta creada con Google no tiene contraseña: puede crear
una con el enlace del correo o desde su cuenta, sin que se le pida la actual.
"""

from abc import ABC, abstractmethod


class CuentasUsuario(ABC):
    """Puerto de salida: las cuentas de la tienda."""

    @abstractmethod
    def buscar_activa_por_correo(self, correo: str) -> int | None:
        """Id de la cuenta activa con ese correo (sin distinguir mayúsculas), o None."""
        raise NotImplementedError

    @abstractmethod
    def tiene_contrasena(self, usuario_id: int) -> bool:
        """False si la cuenta se creó con Google y todavía no tiene contraseña."""
        raise NotImplementedError

    @abstractmethod
    def contrasena_correcta(self, usuario_id: int, contrasena: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def cambiar_contrasena(self, usuario_id: int, contrasena: str) -> None:
        raise NotImplementedError


class EnlacesRestablecimiento(ABC):
    """Puerto de salida: el enlace firmado que llega por correo."""

    @abstractmethod
    def crear(self, usuario_id: int) -> str:
        """URL completa de la página para elegir la nueva contraseña."""
        raise NotImplementedError

    @abstractmethod
    def usuario_del_enlace(self, uid: str, token: str) -> int | None:
        """Id de la cuenta, o None si el enlace está alterado, venció o ya se usó."""
        raise NotImplementedError


class ValidadorContrasenas(ABC):
    """Puerto de salida: las reglas de una contraseña segura (largo, que no sea común ni parecida a los datos)."""

    @abstractmethod
    def errores(self, contrasena: str, usuario_id: int) -> list[str]:
        raise NotImplementedError


class NotificadorCuentas(ABC):
    """Puerto de salida: los correos de la cuenta."""

    @abstractmethod
    def enviar_enlace(self, usuario_id: int, enlace: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def avisar_cambio(self, usuario_id: int) -> None:
        """Avisa que la contraseña cambió, por si no fue el dueño de la cuenta."""
        raise NotImplementedError


class EnlaceInvalido(Exception):
    def __init__(self):
        super().__init__('El enlace no es válido o ya venció. Pide uno nuevo.')


class ContrasenaActualIncorrecta(Exception):
    def __init__(self):
        super().__init__('La contraseña actual no es correcta.')


class ContrasenaInvalida(Exception):
    """errores: {campo: [mensajes]}, con los campos del formulario (password, password2)."""

    def __init__(self, errores: dict):
        super().__init__('La nueva contraseña no es válida.')
        self.errores = errores


def _validar_nueva(validador: ValidadorContrasenas, usuario_id: int, nueva: str, confirmacion: str):
    errores = {}
    problemas = validador.errores(nueva, usuario_id)
    if problemas:
        errores['password'] = problemas
    if nueva != confirmacion:
        errores['password2'] = ['Las contraseñas no coinciden.']
    if errores:
        raise ContrasenaInvalida(errores)


class SolicitarRestablecimiento:
    """Envía el enlace para elegir una nueva contraseña.

    No avisa si el correo no tiene cuenta: quien llama responde siempre lo mismo, para no revelar qué correos
    están registrados (el mismo criterio del portal de seguimiento, RF-02.4).
    """

    def __init__(self, cuentas: CuentasUsuario, enlaces: EnlacesRestablecimiento, notificador: NotificadorCuentas):
        self.cuentas = cuentas
        self.enlaces = enlaces
        self.notificador = notificador

    def ejecutar(self, correo: str) -> None:
        correo = (correo or '').strip()
        usuario_id = self.cuentas.buscar_activa_por_correo(correo) if correo else None
        if usuario_id is not None:
            self.notificador.enviar_enlace(usuario_id, self.enlaces.crear(usuario_id))


class RestablecerContrasena:
    """Guarda la nueva contraseña con el enlace del correo. El enlace deja de servir apenas cambia la contraseña."""

    def __init__(self, cuentas: CuentasUsuario, enlaces: EnlacesRestablecimiento, validador: ValidadorContrasenas,
                 notificador: NotificadorCuentas):
        self.cuentas = cuentas
        self.enlaces = enlaces
        self.validador = validador
        self.notificador = notificador

    def ejecutar(self, uid: str, token: str, nueva: str, confirmacion: str) -> None:
        usuario_id = self.enlaces.usuario_del_enlace(uid, token)
        if usuario_id is None:
            raise EnlaceInvalido()
        _validar_nueva(self.validador, usuario_id, nueva, confirmacion)
        self.cuentas.cambiar_contrasena(usuario_id, nueva)
        self.notificador.avisar_cambio(usuario_id)


class CambiarContrasena:
    """Cambia la contraseña con la sesión iniciada. Pide la actual, salvo a una cuenta de Google que aún no tiene."""

    def __init__(self, cuentas: CuentasUsuario, validador: ValidadorContrasenas, notificador: NotificadorCuentas):
        self.cuentas = cuentas
        self.validador = validador
        self.notificador = notificador

    def ejecutar(self, usuario_id: int, actual: str, nueva: str, confirmacion: str) -> None:
        tenia_contrasena = self.cuentas.tiene_contrasena(usuario_id)
        if tenia_contrasena and not self.cuentas.contrasena_correcta(usuario_id, actual or ''):
            raise ContrasenaActualIncorrecta()
        _validar_nueva(self.validador, usuario_id, nueva, confirmacion)
        if tenia_contrasena and nueva == actual:
            raise ContrasenaInvalida({'password': ['La nueva contraseña debe ser distinta de la actual.']})
        self.cuentas.cambiar_contrasena(usuario_id, nueva)
        self.notificador.avisar_cambio(usuario_id)
