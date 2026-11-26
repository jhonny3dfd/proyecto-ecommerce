from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UsuarioManager(BaseUserManager):
    def por_correo(self, email):
        """La cuenta de un correo, sin distinguir mayúsculas: `Ana@Gmail.com` y `ana@gmail.com` son la misma.

        Si quedaron cuentas antiguas que solo difieren en eso, se usa la que coincide exacto (o ninguna).
        """
        email = str(email or '').strip()
        candidatas = list(self.filter(email__iexact=email)) if email else []
        if len(candidatas) == 1:
            return candidatas[0]
        return next((usuario for usuario in candidatas if usuario.email == email), None)

    def get_by_natural_key(self, email):
        # Lo usa el inicio de sesión: el correo se puede escribir con cualquier combinación de mayúsculas
        usuario = self.por_correo(email)
        if usuario is None:
            raise self.model.DoesNotExist
        return usuario

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        # En minúsculas: así no se crean dos cuentas que solo difieren en mayúsculas
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('rol', 'ADMIN')
        return self.create_user(email, password, **extra_fields)

class Usuario(AbstractBaseUser, PermissionsMixin):
    ROLES = [
        ('ADMIN', 'Administrador / Vendedor'),
        ('COMPRADOR', 'Comprador'),
    ]

    nombre = models.CharField(max_length=255)
    apellido_paterno = models.CharField(max_length=255)
    apellido_materno = models.CharField(max_length=255)
    email = models.EmailField(unique=True, max_length=255)
    
    # --- NUEVO CAMPO PARA CELULAR ---
    # Usamos max_length=20 para soportar códigos de país (ej: +569...)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    
    rol = models.CharField(max_length=20, choices=ROLES, default='COMPRADOR')
    google_sso_id = models.CharField(max_length=255, blank=True, null=True)
    acepta_cookies = models.BooleanField(default=False)
    cumpleanos_dia = models.PositiveSmallIntegerField(null=True, blank=True)
    cumpleanos_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre', 'apellido_paterno', 'apellido_materno']

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(cumpleanos_dia__isnull=True, cumpleanos_mes__isnull=True) | (
                models.Q(cumpleanos_dia__isnull=False, cumpleanos_mes__isnull=False,
                         cumpleanos_dia__gte=1, cumpleanos_dia__lte=31,
                         cumpleanos_mes__gte=1, cumpleanos_mes__lte=12)
                & ~models.Q(cumpleanos_mes__in=[4, 6, 9, 11], cumpleanos_dia=31)
                & ~models.Q(cumpleanos_mes=2, cumpleanos_dia__gte=30))),
            name='usuario_cumpleanos_valido')]

    def __str__(self):
        return f"{self.nombre} {self.apellido_paterno} ({self.rol}) - {self.email}"
