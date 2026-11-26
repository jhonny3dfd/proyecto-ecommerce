from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from ecommerce.domain.ventas import NombreInvalido, TelefonoInvalido, normalizar_nombre_persona, normalizar_telefono_chile

User = get_user_model()

class RegistroUsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password2 = serializers.CharField(
        write_only=True, 
        required=True
    )

    class Meta:
        model = User
        # Sin 'rol': el registro es público y siempre crea un comprador (valor por defecto del modelo).
        # El administrador se crea con createsuperuser; si el rol viniera en la petición, cualquiera sería ADMIN.
        fields = (
            'id', 
            'email', 
            'nombre', 
            'apellido_paterno', 
            'apellido_materno', 
            'telefono', 
            'acepta_cookies', 
            'password', 
            'password2'
        )
        extra_kwargs = {
            'email': {'required': True},
            'nombre': {'required': True},
            'apellido_paterno': {'required': True},
            'apellido_materno': {'required': False},
            'telefono': {'required': False},
            'acepta_cookies': {'required': False},
        }

    def _nombre(self, valor):
        try:
            return normalizar_nombre_persona(valor)
        except NombreInvalido as error:
            raise serializers.ValidationError(str(error))

    def validate_nombre(self, valor):
        return self._nombre(valor)

    def validate_apellido_paterno(self, valor):
        return self._nombre(valor)

    def validate_apellido_materno(self, valor):
        # Opcional
        return self._nombre(valor) if valor and valor.strip() else valor

    def validate_telefono(self, valor):
        # Opcional; si viene, el mismo formato que el checkout (el teléfono se usa para coordinar entregas)
        if not valor:
            return valor
        try:
            return normalizar_telefono_chile(valor)
        except TelefonoInvalido as error:
            raise serializers.ValidationError(str(error))

    def validate_email(self, valor):
        # Sin distinguir mayúsculas: Ana@Gmail.com y ana@gmail.com son la misma cuenta
        valor = valor.strip().lower()
        if User.objects.filter(email__iexact=valor).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este correo.')
        return valor

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            password=password,
            **validated_data
        )
        return user
    
class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)


class CumpleanosSerializer(serializers.Serializer):
    """Solo la fecha opcional de la propia cuenta, sin año ni identificador de otra persona."""
    dia = serializers.IntegerField(allow_null=True)
    mes = serializers.IntegerField(allow_null=True)

    def validate(self, attrs):
        from ecommerce.domain.cumpleanos import validar_cumpleanos
        try:
            validar_cumpleanos(attrs['dia'], attrs['mes'])
        except ValueError as error:
            raise serializers.ValidationError({'dia': str(error)}) from error
        return attrs


# Las reglas de la contraseña nueva están en application/cuentas.py: aquí solo se recibe el formulario
class OlvidoContrasenaSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)


class RestablecerContrasenaSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=128)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    password2 = serializers.CharField(max_length=128, trim_whitespace=False)


class CambiarContrasenaSerializer(serializers.Serializer):
    # Vacía en una cuenta de Google que todavía no tiene contraseña
    actual = serializers.CharField(max_length=128, required=False, allow_blank=True, default='', trim_whitespace=False)
    password = serializers.CharField(max_length=128, trim_whitespace=False)
    password2 = serializers.CharField(max_length=128, trim_whitespace=False)
