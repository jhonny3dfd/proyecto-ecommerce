"""Small deterministic factory; passwords are hashed by the real manager."""

from ecommerce.infrastructure.usuarios.models import Usuario


PASSWORD = 'QA-Ecode-938!Secure'


def create_user(email='comprador@example.test', **overrides):
    fields = {
        'nombre': 'Persona',
        'apellido_paterno': 'Prueba',
        'apellido_materno': 'Seguridad',
        'rol': 'COMPRADOR',
    }
    fields.update(overrides)
    return Usuario.objects.create_user(email, PASSWORD, **fields)
