from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from ecommerce.domain.catalogo import (
    COLORES_ETIQUETA_PRODUCTO,
    LARGO_ETIQUETA_PRODUCTO,
    ColeccionPrivadaInvalida,
    validar_obra_no_es_version_de_otra,
    validar_version_a_la_venta,
    limpiar_colecciones,
)
from ecommerce.domain.youtube import extraer_id_youtube
from .documents import Producto, Variante
from .image_adapters import actualizar_producto
from .images import (
    ReferenciaImagenField,
    es_imagen_gestionada,
    normalizar_referencia_imagen,
)

class VarianteSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=64)
    precio = serializers.DecimalField(max_digits=10, decimal_places=2)
    precio_oferta = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    # RN-03: el stock nunca es negativo; con 0 la variante no se vende
    stock = serializers.IntegerField(default=0, min_value=0)
    imagen_especifica = ReferenciaImagenField(required=False, allow_blank=True, allow_null=True)
    atributos_variables = serializers.DictField(required=False, default=dict)

    # Peso y medidas de una unidad: con ellos el servidor arma el paquete del envío (domain/logistica.py)
    peso_kg = serializers.FloatField(required=False, default=1.0, min_value=0.01, max_value=1000)
    alto_cm = serializers.IntegerField(required=False, default=10, min_value=1, max_value=1000)
    ancho_cm = serializers.IntegerField(required=False, default=10, min_value=1, max_value=1000)
    largo_cm = serializers.IntegerField(required=False, default=10, min_value=1, max_value=1000)

    def validate(self, attrs):
        precio = attrs.get('precio')
        precio_oferta = attrs.get('precio_oferta')
        if precio is not None and precio <= 0:
            raise serializers.ValidationError({"precio": "El precio debe ser mayor a cero."})
        # Pesos chilenos: sin decimales (el checkout y Transbank cobran montos enteros)
        for campo, valor in (('precio', precio), ('precio_oferta', precio_oferta)):
            if valor is not None and valor != valor.to_integral_value():
                raise serializers.ValidationError({campo: "El precio va en pesos, sin decimales."})
        if precio_oferta is not None:
            if precio_oferta <= 0:
                raise serializers.ValidationError({"precio_oferta": "El precio de oferta debe ser mayor a cero."})
            if precio is not None and precio_oferta >= precio:
                raise serializers.ValidationError({"precio_oferta": "El precio de oferta debe ser menor al precio normal."})
        return attrs

class ProductoSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    nombre = serializers.CharField(max_length=255)
    descripcion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    meta_titulo = serializers.CharField(max_length=60, required=False, allow_blank=True, allow_null=True)
    meta_descripcion = serializers.CharField(max_length=160, required=False, allow_blank=True, allow_null=True)
    etiqueta = serializers.CharField(max_length=LARGO_ETIQUETA_PRODUCTO, required=False, allow_blank=True, default='')
    etiqueta_color = serializers.ChoiceField(choices=COLORES_ETIQUETA_PRODUCTO, required=False, default='primary')
    solo_suscriptores = serializers.BooleanField(required=False)
    planes_suscripcion = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False,
                                              max_length=50)
    categoria = serializers.CharField(max_length=100)
    imagenes = serializers.ListField(child=ReferenciaImagenField(), required=False)
    # Video de YouTube de la ficha (pedido de Alan): el admin pega el enlace en "youtube" y se guarda el ID.
    # Vacío quita el video; sin "youtube" en la petición no se cambia
    youtube = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True,
                                    max_length=500)
    youtube_id = serializers.CharField(read_only=True)

    fecha_creacion = serializers.DateTimeField(read_only=True)
    
    activo = serializers.BooleanField(default=True)
    publicado = serializers.BooleanField(default=False)
    atributos_globales = serializers.DictField(required=False, default=dict)
    colecciones = serializers.ListField(child=serializers.CharField(max_length=100), required=False, default=list)
    
    # Colección privada (SCRUM-197)
    coleccion_privada = serializers.BooleanField(default=False, required=False)
    version_a_la_venta = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    texto_boton_version = serializers.CharField(default='Disponible en print', required=False, allow_blank=True, max_length=100)
    version_a_la_venta_disponible = serializers.SerializerMethodField()

    variantes = VarianteSerializer(many=True, required=False)

    def to_representation(self, instance):
        datos = super().to_representation(instance)
        from ecommerce.infrastructure.ventas.repositorio_suscripciones import suscripciones_activas_en_tienda
        if '_suscripciones_activas' not in self.context:
            self.context['_suscripciones_activas'] = suscripciones_activas_en_tienda()
        if not self.context['_suscripciones_activas']:
            datos['solo_suscriptores'] = False
            datos['planes_suscripcion'] = []
        return datos

    def validate_planes_suscripcion(self, valor):
        from ecommerce.infrastructure.ventas.models import PlanSuscripcion
        if len(set(valor)) != len(valor):
            raise serializers.ValidationError('Los planes no pueden repetirse.')
        if set(valor) != set(PlanSuscripcion.objects.filter(pk__in=valor).values_list('pk', flat=True)):
            raise serializers.ValidationError('Uno de los planes seleccionados ya no existe.')
        return valor

    def get_version_a_la_venta_disponible(self, obj):
        version_id = getattr(obj, 'version_a_la_venta', None)
        if not version_id:
            return False
        versiones_publicadas = self.context.get('versiones_publicadas')
        if versiones_publicadas is not None:
            return str(version_id) in versiones_publicadas
        try:
            target = Producto.objects(
                id=version_id, activo=True, publicado=True, coleccion_privada__ne=True
            ).only('id').first()
            return target is not None
        except Exception:
            return False

    def validate(self, attrs):
        request = self.context.get('request')
        if 'youtube' in attrs:
            try:
                attrs['youtube_id'] = extraer_id_youtube(attrs.pop('youtube'))
            except ValueError as error:
                raise serializers.ValidationError({'youtube': str(error)}) from error
        if attrs.get('solo_suscriptores'):
            from ecommerce.infrastructure.ventas.repositorio_suscripciones import suscripciones_activas_en_tienda
            if not suscripciones_activas_en_tienda():
                raise serializers.ValidationError({'solo_suscriptores': 'Activa Suscripciones antes de restringir un producto.'})
        if 'imagenes' in attrs:
            if len(attrs['imagenes']) > settings.CATALOGO_IMAGEN_MAX_GALERIA:
                raise serializers.ValidationError({'imagenes': 'Se ha superado el límite de imágenes por producto.'})
            try:
                attrs['imagenes'] = [
                    normalizar_referencia_imagen(valor, self.instance, request)
                    for valor in attrs['imagenes']
                ]
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({'imagenes': exc.detail}) from exc
            if len(set(attrs['imagenes'])) != len(attrs['imagenes']):
                raise serializers.ValidationError({'imagenes': 'La galería no puede contener imágenes repetidas.'})
        galeria = attrs.get('imagenes', self.instance.imagenes if self.instance else [])
        for index, variante in enumerate(attrs.get('variantes', [])):
            valor = variante.get('imagen_especifica')
            if not valor:
                continue
            try:
                clave = normalizar_referencia_imagen(valor, self.instance, request)
                if es_imagen_gestionada(clave) and clave not in galeria:
                    raise serializers.ValidationError('La imagen de variante debe pertenecer a la galería.')
                variante['imagen_especifica'] = clave
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({
                    'variantes': {index: {'imagen_especifica': exc.detail}},
                }) from exc

        variantes = attrs.get('variantes', [])
        skus = [str(v.get('sku', '')).strip() for v in variantes if v.get('sku')]
        if len(skus) != len(set(skus)):
            raise serializers.ValidationError({'variantes': 'Cada variante de un producto debe tener un código SKU único.'})

        # Validaciones de Colección privada en el dominio (SCRUM-197)
        coleccion_privada = attrs.get('coleccion_privada', getattr(self.instance, 'coleccion_privada', False) if self.instance else False)
        version_a_la_venta = attrs.get('version_a_la_venta', getattr(self.instance, 'version_a_la_venta', None) if self.instance else None)
        texto_boton = attrs.get('texto_boton_version')
        if texto_boton is not None and not str(texto_boton).strip():
            attrs['texto_boton_version'] = 'Disponible en print'

        if version_a_la_venta:
            version_str = str(version_a_la_venta).strip()
            attrs['version_a_la_venta'] = version_str
            try:
                target = Producto.objects(id=version_str).first()
            except Exception:
                raise serializers.ValidationError({'version_a_la_venta': 'El producto seleccionado no es válido.'})
            try:
                validar_version_a_la_venta(
                    producto_id=str(self.instance.id) if self.instance else None,
                    version_id=version_str,
                    target_existe=bool(target),
                    target_es_coleccion_privada=bool(getattr(target, 'coleccion_privada', False)) if target else False,
                )
            except ColeccionPrivadaInvalida as error:
                raise serializers.ValidationError({'version_a_la_venta': str(error)})

        if coleccion_privada and self.instance:
            referenciador = Producto.objects(version_a_la_venta=str(self.instance.id)).first()
            try:
                validar_obra_no_es_version_de_otra(
                    producto_id=str(self.instance.id),
                    coleccion_privada=coleccion_privada,
                    nombre_referenciador=referenciador.nombre if referenciador else None,
                )
            except ColeccionPrivadaInvalida as error:
                raise serializers.ValidationError({'coleccion_privada': str(error)})

        return attrs


    def create(self, validated_data):
        variantes_data = validated_data.pop('variantes', [])
        
        validated_data['fecha_creacion'] = timezone.now()
        
        producto = Producto(**validated_data)
        
        producto.variantes = [Variante(**v_data) for v_data in variantes_data]
        producto.save()
        return producto

    def update(self, instance, validated_data):
        return actualizar_producto(instance, validated_data)

    def validate_colecciones(self, value):
        return limpiar_colecciones(value)
