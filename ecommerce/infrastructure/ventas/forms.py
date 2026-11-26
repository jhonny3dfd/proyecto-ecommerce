"""Datos públicos de pago en el admin; las credenciales se gestionan en el panel."""
from django import forms
from django.core.exceptions import ValidationError

from ecommerce.domain.medios_pago import definicion_medio
from ecommerce.domain.promociones import PromocionInvalida, validar_promocion

from .models import MedioPago, Promocion


def campos_publicos(codigo):
    try:
        return {campo.nombre: campo for campo in definicion_medio(codigo).campos if not campo.secreto}
    except ValueError:
        return {}


def dato_publico_admitido(nombre, valor, campos):
    campo = campos.get(nombre)
    return (campo is not None and isinstance(valor, str)
            and (not valor or not campo.opciones or valor in campo.opciones))


def datos_publicos_admitidos(datos, campos):
    return isinstance(datos, dict) and all(
        dato_publico_admitido(nombre, valor, campos) for nombre, valor in datos.items()
    )


class DatosPublicosField(forms.JSONField):
    def prepare_value(self, value):
        # Evitar que Django muestre secretos, incluso si el JSON recibido está mal formado.
        # Solo se filtra la presentación; clean_datos valida la entrada original.
        publicos = {nombre: valor for nombre, valor in value.items()
                    if dato_publico_admitido(nombre, valor, self.campos)} if isinstance(value, dict) else {}
        return super().prepare_value(publicos)

    def to_python(self, value):
        return {} if value in self.empty_values else super().to_python(value)


class MedioPagoAdminForm(forms.ModelForm):
    datos = DatosPublicosField(required=False)

    class Meta:
        model = MedioPago
        fields = ('codigo', 'habilitado', 'datos')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Un código manipulado no debe cambiar el proveedor de un registro existente.
        codigo = self.instance.codigo if self.instance.pk else (
            self.data.get('codigo') if self.is_bound else self.initial.get('codigo', self.instance.codigo)
        )
        self.campos_publicos = campos_publicos(codigo)
        self.fields['datos'].campos = self.campos_publicos
        self.datos_anteriores_invalidos = bool(
            self.instance.pk and not datos_publicos_admitidos(self.instance.datos, self.campos_publicos)
        )
        nombres = ', '.join(self.campos_publicos) or 'ninguno (use {})'
        self.fields['datos'].help_text = f'Campos públicos admitidos: {nombres}. Las credenciales se gestionan en el panel.'
        if self.datos_anteriores_invalidos:
            self.fields['datos'].help_text += (
                ' Este registro contiene datos no admitidos. Su guardado está bloqueado;'
                ' requiere una regularización individual antes de editarlo aquí.'
            )

    def clean_datos(self):
        datos = self.cleaned_data['datos']
        if not datos_publicos_admitidos(datos, self.campos_publicos):
            raise ValidationError('Use solo los campos públicos admitidos, con valores de texto y opciones válidas.')
        return datos

    def clean(self):
        cleaned = super().clean()
        if self.datos_anteriores_invalidos:
            # No borrar ni cifrar datos antiguos automáticamente al editar otros campos.
            raise ValidationError('El registro contiene datos no admitidos. No se guardó ningún cambio.')
        return cleaned


class PromocionAdminForm(forms.ModelForm):
    """El /admin/ de Django con las mismas reglas que el panel (domain/promociones.py): sin esto, un superusuario
    podía guardar un 250 % o un umbral de envío gratis negativo."""

    class Meta:
        model = Promocion
        fields = '__all__'

    def clean(self):
        datos = super().clean()
        try:
            datos['codigo'] = validar_promocion(
                datos.get('codigo'), datos.get('tipo_descuento'), datos.get('valor_descuento'),
                datos.get('umbral_envio_gratis'), datos.get('monto_minimo'), datos.get('automatica', False),
                datos.get('usos_maximos'))
        except PromocionInvalida as error:
            for campo, mensaje in error.errores.items():
                self.add_error(campo if campo in self.fields else None, mensaje)
            return datos
        # El comprador escribe el código sin distinguir mayúsculas: dos que solo difieren en eso serían el mismo
        repetidos = Promocion.objects.filter(codigo__iexact=datos['codigo']).exclude(pk=self.instance.pk)
        if repetidos.exists():
            self.add_error('codigo', 'Ya existe un código igual.')
        return datos
