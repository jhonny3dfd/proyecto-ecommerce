from dataclasses import asdict
from decimal import Decimal
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException
from mongoengine.errors import ValidationError as MongoValidationError
from ecommerce.infrastructure.catalogo.documents import Producto
from ecommerce.infrastructure.catalogo.images import ArchivoImagenField
from .models import Promocion
import re
from ecommerce.application.couriers import CotizarEnvio, CourierNoActivo
from ecommerce.domain.logistica import (
    ENTREGA_COORDINADA, ENTREGAS_DE_LA_TIENDA, RETIRO_LOCAL, CourierNoDisponible, EntregaNoHabilitada,
    EntregasDeLaTienda, SinCobertura, error_direccion_entrega, es_entrega_con_courier,
)
from ecommerce.application.medios_pago import MediosPagoDisponibles
from ecommerce.application.pagos import ErrorPasarelaPago
from ecommerce.application.ventas import PaqueteDelPedido, PrepararPedido, RevisarCarrito
from ecommerce.application.vitrina import ValidarDestacados
from ecommerce.domain.banner import DESTINO_POR_DEFECTO
from ecommerce.domain.blog import MAX_FOTOS_PUBLICACION, NombreBlogInvalido, normalizar_nombre_blog
from ecommerce.domain.catalogo import OrdenCategoriasInvalido, normalizar_orden_categorias
from ecommerce.domain.destacados import (
    DestacadosInvalidos, TituloDestacadosInvalido, normalizar_titulo_destacados,
)
from ecommerce.domain.cotizaciones import MAX_FOTOS_COTIZACION
from ecommerce.domain.contacto import UsuarioInstagramInvalido, direccion_es_publica, normalizar_usuario_instagram, validar_enlace_red_social, EnlaceRedSocialInvalido
from ecommerce.domain.documentos_tributarios import ModeloEmision, documento_por_emitir, documento_requerido
from ecommerce.domain.empresa import DatosEmpresa, DatosEmpresaInvalidos
from ecommerce.domain.promociones import (
    PromocionInvalida, ReglaDescuento, cumple_minimo, da_envio_gratis, elegir_promocion, monto_descuento,
    validar_promocion,
)
from ecommerce.domain.menu import MenuInvalido, normalizar_menu_principal
from ecommerce.domain.sobre_mi import NombreSobreMiInvalido, normalizar_nombre_sobre_mi
from ecommerce.domain.suscripciones import descuento_suscriptor, validar_dias_aviso
from ecommerce.application.suscripciones import BeneficiosCompra, beneficios_de
from ecommerce.domain.medios_pago import CodigoMedioPago, MedioPagoNoDisponible, plazo_pago_transferencia
from ecommerce.domain.ventas import (
    ErrorPedido, EventoPedido, ItemSolicitado, OrdenTransporteNoPermitida, SubtotalDesactualizado,
    NombreInvalido, TelefonoInvalido, normalizar_nombre_persona, normalizar_telefono_chile,
    paginas_legales_faltantes, plazo_pago, transiciones_desde, validar_generacion_orden_transporte,
)
from ecommerce.infrastructure.catalogo.repositorio_variantes import MongoCatalogoVariantes
from ecommerce.infrastructure.catalogo.repositorio_vitrina import MongoCatalogoVitrina

from .models import ConfiguracionGlobal, DetalleOrden, OrdenCompra, DireccionEnvio, Promocion
from .models import ConfiguracionGlobal, Cotizacion, OrdenCompra, DireccionEnvio, EmpresaComprador, PaginaLegal
from .models import FotoBanner, FotoPublicacion, Publicacion, Resena, ResenaProducto
from .adapters.correo import CorreoNotificadorPedidos
from .html_seguro import limpiar_html, tiene_texto
from .couriers import DjangoCouriers
from .pasarelas import PASARELAS, pasarela, urls_pasarela
from .repositorio_medios_pago import DjangoRepositorioMediosPago

def couriers():
    """RF-02.3: los couriers que la tienda tiene activos (las pruebas pueden reemplazarlo)."""
    return DjangoCouriers()


def precio_envio(proveedor, origen, destino, paquete):
    """El costo de envío que se cobra: lo cotiza el servidor con el courier elegido, nunca lo envía el navegador."""
    return CotizarEnvio(couriers()).precio(origen, destino, paquete, proveedor)


def medios_pago():
    """RN-02: medios habilitados y configurados por el admin (las pruebas pueden reemplazarlo)."""
    return MediosPagoDisponibles(DjangoRepositorioMediosPago())


def beneficios_del_comprador(request) -> BeneficiosCompra:
    """Lo que da en el checkout la suscripción activa del comprador; nada sin sesión o con el módulo apagado."""
    from .repositorio_suscripciones import DjangoRepositorioSuscripciones, suscripciones_activas_en_tienda
    usuario = getattr(request, 'user', None)
    if not (usuario and usuario.is_authenticated and suscripciones_activas_en_tienda()):
        return BeneficiosCompra()
    return beneficios_de(DjangoRepositorioSuscripciones(), usuario.id)


def entregas_de_la_tienda():
    """Retiro en local y entrega coordinada tal como los dejó el admin en el panel (RF-02.3)."""
    config = ConfiguracionGlobal.objects.filter(pk=1).first()
    if config is None:
        return EntregasDeLaTienda()
    return EntregasDeLaTienda(
        retiro_activo=config.retiro_en_local_activo,
        coordinada_activa=config.entrega_coordinada_activa,
        costo_coordinada=Decimal(config.costo_entrega_coordinada),
    )


CAMPOS_FOTOS_INSTAGRAM = tuple(f'instagram_foto_{numero}' for numero in range(1, 7))
CAMPOS_DIRECCION_LOCAL = ('calle_origen', 'numero_origen', 'dpto_casa_origen', 'comuna_origen', 'region_origen')


class FotoBannerSerializer(serializers.ModelSerializer):
    imagen = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()

    def get_video(self, obj):
        if not obj.video:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(obj.video.url) if request else obj.video.url

    class Meta:
        model = FotoBanner
        # Cada foto con sus textos y a qué página lleva su botón (SCRUM-194)
        fields = ['id', 'imagen', 'video', 'orden', 'antetitulo', 'titulo', 'texto', 'destino']

    def get_imagen(self, obj):
        if not obj.imagen:
            return None
        request = self.context.get('request')
        url = obj.imagen.url
        return request.build_absolute_uri(url) if request is not None else url


def obtener_banners_configuracion(obj, request=None):
    fotos = list(obj.fotos_banner.all())
    if fotos:
        return FotoBannerSerializer(fotos, many=True, context={'request': request}).data
    # La portada antigua (una sola foto) se muestra con los textos generales y el botón al catálogo
    textos = {'antetitulo': obj.subtitulo_bienvenida or '', 'titulo': obj.texto_bienvenida or '',
              'texto': obj.texto_landing or '', 'destino': DESTINO_POR_DEFECTO}
    if obj.banner:
        url = obj.banner.url
        if request is not None:
            url = request.build_absolute_uri(url)
        return [{'id': 'legacy', 'imagen': url, 'orden': 0, **textos}]
    if obj.banner_url and obj.banner_url.strip():
        return [{'id': 'legacy', 'imagen': obj.banner_url.strip(), 'orden': 0, **textos}]
    return []


class ConfiguracionGlobalSerializer(serializers.ModelSerializer):
    banner_url = serializers.URLField(required=False, allow_blank=True, default='')
    banners = serializers.SerializerMethodField()
    texto_boton_ingreso = serializers.CharField(max_length=100, required=False)
    pasarelas_activas = serializers.SerializerMethodField()
    # RN-04: el frontend muestra el botón de Google solo si viene informado (es público por diseño)
    google_client_id = serializers.SerializerMethodField()
    # Couriers con sus llaves cargadas: el checkout ofrece despacho y sucursales con ellos (nunca sus llaves)
    couriers = serializers.SerializerMethodField()

    def get_banners(self, obj):
        return obtener_banners_configuracion(obj, self.context.get('request'))

    class Meta:
        model = ConfiguracionGlobal
        fields = [
            'google_client_id',
            'texto_bienvenida',
            'texto_boton_ingreso',
            'banner_url',
            'tema_seleccionado',
            'tipografia_seleccionada',
            'layout_catalogo',
            'pasarelas_activas',
            'google_analytics_id',
            'meta_pixel_id',
            'modo_autenticacion',
            'comuna_origen',
            'region_origen',
            'calle_origen',
            'numero_origen',
            'dpto_casa_origen',
            'retiro_en_local_activo',
            'entrega_coordinada_activa',
            'costo_entrega_coordinada',
            'instrucciones_entrega_coordinada',
            'couriers',
            'cotizaciones_activas',
            # Suscripciones (pedido de un cliente): activas, el menú muestra "Suscripción"
            'suscripciones_activas',
            # Blog o portafolio: activo, el enlace del menú lleva a /blog con este nombre
            'blog_activo',
            'blog_nombre',
            'sobre_mi_activo',
            'sobre_mi_nombre',
            # Reseñas: activas, la landing y la ficha muestran las aprobadas
            'resenas_activas',
            # Destacados de la landing: la selección del admin (la vitrina filtra lo que no se puede ver)
            'vitrina_modo',
            'destacados_titulo',
            'destacados',
            # Presentación: fotos sin recorte, ficha con la foto horizontal y logo más grande en el computador
            'video_banner_activo',
            'fotos_completas',
            'ficha_horizontal',
            'logo_grande',
            # Identidad y landing (RF-01.1, RF-01.2): las imágenes salen como URL
            'orden_catalogo',
            'orden_categorias',
            'menu_principal',
            'nombre_tienda',
            'logo',
            'favicon',
            'banner',
            'banners',
            'subtitulo_bienvenida',
            'texto_landing',
            'nosotros_titulo',
            'nosotros_texto',
            'nosotros_imagen',
            # Contacto y redes: pie de página y sección de Instagram
            'correo_contacto',
            'horario_atencion',
            'mostrar_direccion_pie',
            'telefono_comercial',
            'facebook_url',
            'x_url',
            'youtube_url',
            'tiktok_url',
            'ubicacion_logo_universidad',
            'instagram_usuario',
            *CAMPOS_FOTOS_INSTAGRAM,
        ]

    def to_representation(self, instance):
        datos = super().to_representation(instance)
        # Sin retiro en local y sin mostrarla en el pie, la dirección del local no se publica
        if not direccion_es_publica(instance.retiro_en_local_activo, instance.mostrar_direccion_pie):
            for campo in CAMPOS_DIRECCION_LOCAL:
                datos.pop(campo, None)
        return datos

    def get_google_client_id(self, obj):
        return settings.GOOGLE_CLIENT_ID

    def get_couriers(self, obj):
        return [{'codigo': c.codigo, 'nombre': c.nombre, 'sucursales': c.con_sucursales} for c in couriers().activos()]

    def get_pasarelas_activas(self, obj):
        # RN-02: solo los medios habilitados y con sus datos completos; nunca sus credenciales
        return [codigo.value for codigo in medios_pago().disponibles()]

class ImagenNegocioField(ArchivoImagenField):
    """Logo, favicon o portada: se valida y se vuelve a codificar igual que las fotos del catálogo."""

    def to_internal_value(self, data):
        imagen = super().to_internal_value(data)
        return ContentFile(imagen.contenido, name=f'{uuid.uuid4().hex}.{imagen.extension}')


CAMPOS_IMAGEN_NEGOCIO = ('logo', 'favicon', 'banner', 'nosotros_imagen', *CAMPOS_FOTOS_INSTAGRAM, 'sobre_mi_foto_1',
                         'sobre_mi_foto_2')


class ConfiguracionNegocioSerializer(serializers.ModelSerializer):
    banners = serializers.SerializerMethodField()
    # Se suben por multipart; un null (en JSON) quita la imagen
    logo = ImagenNegocioField(required=False, allow_null=True)
    favicon = ImagenNegocioField(required=False, allow_null=True)
    banner = ImagenNegocioField(required=False, allow_null=True)
    nosotros_imagen = ImagenNegocioField(required=False, allow_null=True)
    instagram_foto_1 = ImagenNegocioField(required=False, allow_null=True)
    instagram_foto_2 = ImagenNegocioField(required=False, allow_null=True)
    instagram_foto_3 = ImagenNegocioField(required=False, allow_null=True)
    instagram_foto_4 = ImagenNegocioField(required=False, allow_null=True)
    instagram_foto_5 = ImagenNegocioField(required=False, allow_null=True)
    instagram_foto_6 = ImagenNegocioField(required=False, allow_null=True)
    # Fotos de la página Sobre mí (pedido de un cliente, opcionales)
    sobre_mi_foto_1 = ImagenNegocioField(required=False, allow_null=True)
    sobre_mi_foto_2 = ImagenNegocioField(required=False, allow_null=True)
    # El título de la portada: el mismo límite que el panel (en el modelo es un TextField sin límite)
    texto_bienvenida = serializers.CharField(max_length=300, required=False)
    texto_landing = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    nosotros_texto = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    horario_atencion = serializers.CharField(max_length=500, required=False, allow_blank=True)
    # Se acepta '@usuario' o el enlace al perfil; se guarda solo el usuario
    instagram_usuario = serializers.CharField(max_length=200, required=False, allow_blank=True)
    costo_entrega_coordinada = serializers.IntegerField(min_value=0, max_value=1_000_000, required=False)
    # Se ordenan los espacios antes de medirlo; vacío vuelve a "Nosotros" (domain/blog.py)
    blog_nombre = serializers.CharField(max_length=200, required=False, allow_blank=True)
    # Igual que el nombre del blog: vacío vuelve a "Destacados" (domain/destacados.py)
    destacados_titulo = serializers.CharField(max_length=200, required=False, allow_blank=True)

    sobre_mi_nombre = serializers.CharField(max_length=200,required=False,allow_blank=True)
    sobre_mi_biografia = serializers.CharField(max_length=100_000,required=False,allow_blank=True,trim_whitespace=False)

    def get_banners(self, obj):
        return obtener_banners_configuracion(obj, self.context.get('request'))

    class Meta:
        model = ConfiguracionGlobal
        fields = [
            'orden_catalogo',
            'orden_categorias',
            'menu_principal',
            'nombre_tienda',
            'texto_bienvenida',
            'subtitulo_bienvenida',
            'texto_landing',
            'nosotros_titulo',
            'nosotros_texto',
            'nosotros_imagen',
            'texto_boton_ingreso',
            'banner_url',
            'tema_seleccionado',
            'tipografia_seleccionada',
            'logo',
            'favicon',
            'banner',
            'banners',
            'layout_catalogo',
            'google_analytics_id',
            'meta_pixel_id',
            'modo_autenticacion',
            'comuna_origen',
            'region_origen',
            'calle_origen',
            'numero_origen',
            'dpto_casa_origen',
            'retiro_en_local_activo',
            'entrega_coordinada_activa',
            'costo_entrega_coordinada',
            'instrucciones_entrega_coordinada',
            'cotizaciones_activas',
            'suscripciones_activas',
            'suscripciones_dias_aviso',
            'blog_activo',
            'blog_nombre',
            'sobre_mi_activo',
            'sobre_mi_nombre',
            'sobre_mi_biografia',
            'sobre_mi_foto_1',
            'sobre_mi_foto_1_alt',
            'sobre_mi_foto_2',
            'sobre_mi_foto_2_alt',
            'resenas_activas',
            'vitrina_modo',
            'destacados_titulo',
            'destacados',
            'video_banner_activo',
            'fotos_completas',
            'ficha_horizontal',
            'logo_grande',
            'correo_contacto',
            'horario_atencion',
            'mostrar_direccion_pie',
            'telefono_comercial',
            'facebook_url',
            'x_url',
            'youtube_url',
            'tiktok_url',
            'ubicacion_logo_universidad',
            'instagram_usuario',
            *CAMPOS_FOTOS_INSTAGRAM,
            # Solo el panel: qué pedidos piden boleta (no se publica en /api/configuracion/)
            'modelo_emision',
        ]

    def validate_orden_categorias(self, valor):
        # Las reglas viven en domain/catalogo.py
        try:
            return normalizar_orden_categorias(valor)
        except OrdenCategoriasInvalido as error:
            raise serializers.ValidationError(str(error)) from error

    def validate_suscripciones_dias_aviso(self, valor):
        # Las reglas viven en domain/suscripciones.py
        try:
            return validar_dias_aviso(valor)
        except ValueError as error:
            raise serializers.ValidationError(str(error)) from error

    def validate_menu_principal(self, valor):
        menu_anterior = self.instance.menu_principal if self.instance else None
        try:
            return normalizar_menu_principal(valor, menu_anterior)
        except MenuInvalido as error:
            raise serializers.ValidationError(str(error)) from error

    def validate_sobre_mi_nombre(self, valor):
        try:
            return normalizar_nombre_sobre_mi(valor)
        except NombreSobreMiInvalido as error:
            raise serializers.ValidationError(str(error)) from error

    def validate_sobre_mi_biografia(self, valor):
        return limpiar_html(valor)
    def validate_instagram_usuario(self, valor):
        try:
            return normalizar_usuario_instagram(valor)
        except UsuarioInstagramInvalido as error:
            raise serializers.ValidationError(str(error))

    def validate_telefono_comercial(self, valor):
        if not valor or not valor.strip():
            return ''
        try:
            return normalizar_telefono_chile(valor)
        except TelefonoInvalido as error:
            raise serializers.ValidationError(str(error))


    def _validar_red_social(self, valor, red):
        try:
            return validar_enlace_red_social(valor, red)
        except EnlaceRedSocialInvalido as error:
            raise serializers.ValidationError(str(error))


    def validate_facebook_url(self, valor):
        return self._validar_red_social(valor, 'facebook')


    def validate_x_url(self, valor):
        return self._validar_red_social(valor, 'x')


    def validate_youtube_url(self, valor):
        return self._validar_red_social(valor, 'youtube')


    def validate_tiktok_url(self, valor):
        return self._validar_red_social(valor, 'tiktok')
        
    def validate_blog_nombre(self, valor):
        try:
            return normalizar_nombre_blog(valor)
        except NombreBlogInvalido as error:
            raise serializers.ValidationError(str(error))

    def validate_destacados_titulo(self, valor):
        try:
            return normalizar_titulo_destacados(valor)
        except TituloDestacadosInvalido as error:
            raise serializers.ValidationError(str(error))

    def validate_destacados(self, valor):
        # Hasta 4, sin repetir y solo productos y publicaciones que existen (application/vitrina.py)
        try:
            return validar_destacados().ejecutar(valor)
        except DestacadosInvalidos as error:
            raise serializers.ValidationError(str(error))


    def validate_google_analytics_id(self, valor):
        if not valor:
            return valor

        if not re.fullmatch(r'G-[A-Za-z0-9]{10}', valor):
            raise serializers.ValidationError(
                'Ingresa un ID de Google Analytics válido (ej.: G-XXXXXXXXXX).'
            )

        return valor

    def validate_meta_pixel_id(self, valor):
        if not valor:
            return valor

        if not re.fullmatch(r'[0-9]+', valor):
            raise serializers.ValidationError(
                'El ID de Meta Pixel debe contener solo números.'
            )

        return valor

    def update(self, instance, validated_data):
        # Al reemplazar o quitar una imagen se borra el archivo anterior, para no dejar archivos huérfanos
        anteriores = [getattr(instance, campo) for campo in CAMPOS_IMAGEN_NEGOCIO
                      if campo in validated_data and getattr(instance, campo)]
        anteriores = [(archivo.storage, archivo.name) for archivo in anteriores]
        instance = super().update(instance, validated_data)
        for storage, nombre in anteriores:
            storage.delete(nombre)
        return instance


class DireccionEntregaSerializer(serializers.Serializer):
    """La dirección que guarda el pedido: solo estos campos, como texto y con largo máximo. Se muestra en el panel,
    los correos y la orden de transporte, así que no se acepta cualquier JSON. Todos son opcionales: qué exige cada
    forma de entrega lo decide error_direccion_entrega (domain/logistica.py)."""

    calle = serializers.CharField(max_length=300, required=False, allow_blank=True, allow_null=True)
    numero = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    dpto_casa = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    comuna = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    ciudad = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    # Retiro en una oficina del courier: ahí se entrega la orden de transporte
    codigo_sucursal = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)


def paquete_del_pedido(items):
    """RF-02.3: el paquete del envío con las medidas del catálogo; `items` como los valida ItemPedidoSerializer."""
    return PaqueteDelPedido(catalogo_variantes()).ejecutar(
        [ItemSolicitado(i['producto_mongo_id'], i['variante_sku'], i['cantidad']) for i in items])


def regla_de_promocion(promocion):
    """La regla de dominio de un código guardado (domain/promociones.py)."""
    def decimal(valor):
        return None if valor is None else Decimal(str(valor))
    return ReglaDescuento(promocion.tipo_descuento, Decimal(str(promocion.valor_descuento)),
                          decimal(promocion.umbral_envio_gratis), decimal(promocion.monto_minimo))


def mensaje_monto_minimo(promocion):
    return f"Este código vale para compras desde ${promocion.monto_minimo:,}.".replace(',', '.')


def promociones_automaticas_vigentes():
    """Los descuentos que se aplican solos: activos, sin vencer y con usos disponibles."""
    ahora = timezone.now()
    filas = Promocion.objects.filter(automatica=True, is_active=True).filter(
        Q(fecha_expiracion__isnull=True) | Q(fecha_expiracion__gte=ahora)).order_by('id')
    return [promocion for promocion in filas if promocion.esta_vigente]


def reservar_uso_promocion(promocion_id):
    """Suma un uso solo si quedan (UPDATE condicional): dos compras al mismo tiempo no se pasan del límite."""
    con_usos = Q(usos_maximos__isnull=True) | Q(usos__lt=F('usos_maximos'))
    return Promocion.objects.filter(con_usos, pk=promocion_id, is_active=True).update(usos=F('usos') + 1) == 1


def comuna_origen_tienda():
    """Desde donde despacha la tienda: la cotización que ve el comprador y el cobro del checkout usan la misma."""
    config = ConfiguracionGlobal.objects.filter(pk=1).first()
    return config.comuna_origen if config and config.comuna_origen else 'SANTIAGO'


class ProveedorLogisticoNoDisponible(APIException):
    status_code = 503
    default_detail = 'El proveedor logístico no está disponible. Intente nuevamente.'


def catalogo_variantes():
    """Adaptador del catálogo que usa el checkout; las pruebas lo reemplazan por uno falso."""
    return MongoCatalogoVariantes()


def validar_destacados():
    """Caso de uso que valida los destacados de la landing con el catálogo (MongoDB) y el blog (PostgreSQL)."""
    from .repositorio_blog import DjangoPublicacionesVitrina
    return ValidarDestacados(MongoCatalogoVitrina(), DjangoPublicacionesVitrina())


def notificador_pedidos():
    return CorreoNotificadorPedidos()


class ItemPedidoSerializer(serializers.Serializer):
    # El nombre y el precio que envía el navegador se ignoran: se toman del catálogo
    producto_mongo_id = serializers.CharField(max_length=255)
    variante_sku = serializers.CharField(max_length=255)
    cantidad = serializers.IntegerField(min_value=1)


class RevisionCarritoSerializer(serializers.Serializer):
    """Entrada de `POST carrito/validar/`; `revisar()` compara el carrito con el catálogo vigente."""

    items = ItemPedidoSerializer(many=True, max_length=100)

    def revisar(self):
        items = [ItemSolicitado(i['producto_mongo_id'], i['variante_sku'], i['cantidad'])
                 for i in self.validated_data['items']]
        lineas = RevisarCarrito(catalogo_variantes()).ejecutar(items)
        from .acceso_exclusivos import AVISO_EXCLUSIVO, ids_sin_acceso
        restringidos = ids_sin_acceso(self.validated_data['items'], getattr(self.context.get('request'), 'user', None))
        resultado = {
            'valido': all(linea.problema is None for linea in lineas),
            'items': [{
                'producto_mongo_id': linea.producto_id,
                'variante_sku': linea.sku,
                'cantidad': linea.cantidad,
                'disponible': linea.disponible,
                'nombre': linea.nombre,
                'precio': None if linea.precio is None else str(linea.precio),
                'problema': linea.problema,
                'mensaje': linea.mensaje,
            } for linea in lineas],
        }
        for linea in resultado['items']:
            if linea['producto_mongo_id'] in restringidos:
                linea.update(problema='SUSCRIPCION_REQUERIDA', mensaje=AVISO_EXCLUSIVO, disponible=0)
                resultado['valido'] = False
        return resultado

class DatosEmpresaSerializer(serializers.Serializer):
    """Compra como empresa: los obligatorios y el RUT los valida el dominio (domain/empresa.py)."""

    razon_social = serializers.CharField(max_length=150, required=False, allow_blank=True)
    rut = serializers.CharField(max_length=20, required=False, allow_blank=True)
    giro = serializers.CharField(max_length=120, required=False, allow_blank=True)
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True)
    correo = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        try:
            return DatosEmpresa.desde(attrs).como_dict()
        except DatosEmpresaInvalidos as error:
            raise serializers.ValidationError(error.errores)


class CotizacionSolicitudSerializer(serializers.Serializer):
    """Formulario público de cotización: solo los datos del cliente; las reglas las aplica el dominio
    (domain/cotizaciones.py). Cualquier otro campo (estado, id...) se ignora."""

    como_empresa = serializers.BooleanField(default=False)
    nombre = serializers.CharField(max_length=120, required=False, allow_blank=True)
    correo = serializers.EmailField(required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=30, required=False, allow_blank=True)
    producto_id = serializers.CharField(max_length=24, required=False, allow_blank=True)
    descripcion = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    cantidad = serializers.IntegerField(required=False, allow_null=True)
    personalizacion = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    fecha_requerida = serializers.DateField(required=False, allow_null=True)
    empresa = DatosEmpresaSerializer(required=False, allow_null=True)
    # Política de Privacidad: checkbox obligatorio, desmarcado por defecto
    acepta_privacidad = serializers.BooleanField()
    # Campo trampa: oculto para las personas; si viene lleno, lo envió un bot
    sitio_web = serializers.CharField(required=False, allow_blank=True)

    def validate_acepta_privacidad(self, value):
        if value is not True:
            raise serializers.ValidationError('Debes aceptar la Política de Privacidad.')
        return value


class AdminCotizacionSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    # Los ids de las fotos: el panel las pide a admin/cotizaciones/<id>/fotos/<foto>/ con la sesión del admin
    fotos = serializers.SerializerMethodField()

    class Meta:
        model = Cotizacion
        fields = ['id', 'fecha_creacion', 'estado', 'estado_display', 'nombre', 'correo', 'telefono',
                  'producto_id', 'producto_nombre', 'descripcion', 'cantidad', 'personalizacion',
                  'fecha_requerida', 'datos_empresa', 'fotos']
        read_only_fields = fields

    def get_fotos(self, obj):
        return [foto.id for foto in obj.fotos.all()]


class ResenaProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResenaProducto
        fields = ['producto_mongo_id', 'producto_nombre', 'estrellas', 'comentario']
        read_only_fields = fields


class AdminResenaSerializer(serializers.ModelSerializer):
    """Para moderar en el panel: todo es de solo lectura (el admin no edita reseñas) y sin el correo del comprador."""
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    productos = ResenaProductoSerializer(many=True, read_only=True)

    class Meta:
        model = Resena
        fields = ['id', 'orden_id', 'fecha_creacion', 'estado', 'estado_display', 'estrellas', 'comentario',
                  'nombre_publico', 'productos']
        read_only_fields = fields


class EmpresaCompradorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmpresaComprador
        fields = ['razon_social', 'rut', 'giro', 'direccion', 'correo']


class OrdenCompraSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=0, min_value=Decimal('0'))
    # Los calcula el servidor (cotización + subtotal del catálogo); lo que envíe el navegador se ignora
    costo_envio = serializers.FloatField(read_only=True)
    total_final = serializers.FloatField(read_only=True)
    # Una entrega de la tienda o el código de un courier activo (se valida en validate)
    proveedor_logistico = serializers.CharField(max_length=30, required=False)
    # RF-02.3: lo arma el servidor con el peso y las medidas del catálogo; el que envíe el navegador se ignora
    paquete = serializers.JSONField(read_only=True)
    # RF-04.4: aceptación de Términos y Condiciones y Política de Privacidad
    acepta_terminos = serializers.BooleanField(write_only=True)
    # Hasta 100 líneas, como la revisión del carrito (RevisionCarritoSerializer)
    items = ItemPedidoSerializer(many=True, write_only=True, max_length=100)
    codigo_promocion = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, write_only=True)
    email_cliente = serializers.SerializerMethodField()
    # Invitado: ahí le llegan el pedido y el seguimiento; se guarda en minúsculas (el seguimiento no las distingue)
    email_invitado = serializers.EmailField(max_length=255, required=False, allow_blank=True, allow_null=True)
    # RF-02.3: quién recibe o retira; el courier y la tienda lo necesitan para entregar
    nombre_destinatario = serializers.CharField(max_length=120)
    telefono_destinatario = serializers.CharField(max_length=30)
    # Compra como empresa: la tienda emite la factura con estos datos (null si compra una persona)
    datos_empresa = DatosEmpresaSerializer(required=False, allow_null=True)
    # Con sesión: guardar los datos de la empresa para las próximas compras
    guardar_datos_empresa = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = OrdenCompra
        fields = [
            'id',
            'fecha_creacion',
            'estado',
            'email_invitado',
            'email_cliente',
            'metodo_pago',
            'direccion_envio_snapshot',
            'nombre_destinatario',
            'telefono_destinatario',
            'datos_empresa',
            'guardar_datos_empresa',
            'subtotal',
            'costo_envio',
            'total_final',
            'paquete',
            'id_transaccion_pasarela',
            'proveedor_logistico',
            'acepta_terminos',
            'items',
            'codigo_promocion',
        ]

    def validate_acepta_terminos(self, value):
        if value is not True:
            raise serializers.ValidationError(
                'Debes aceptar los Términos y Condiciones y la Política de Privacidad.'
            )
        return value

    def validate_email_invitado(self, value):
        return value.strip().lower() if value else value

    def validate_direccion_envio_snapshot(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('La dirección no tiene un formato válido.')
        direccion = DireccionEntregaSerializer(data=value)
        if not direccion.is_valid():
            raise serializers.ValidationError(direccion.errors)
        # Un campo nulo queda vacío: los correos y el panel lo muestran como texto
        return {campo: valor or '' for campo, valor in direccion.validated_data.items()}

    def validate_nombre_destinatario(self, value):
        try:
            return normalizar_nombre_persona(value)
        except NombreInvalido as error:
            raise serializers.ValidationError(str(error))

    def validate_telefono_destinatario(self, value):
        try:
            return normalizar_telefono_chile(value)
        except TelefonoInvalido as error:
            raise serializers.ValidationError(str(error))
    def get_email_cliente(self, obj):
        if obj.email_invitado:
            return obj.email_invitado
        if obj.usuario and obj.usuario.email:
            return obj.usuario.email
        return None


    def validate(self, data):
        # RF-04.4: el comprador acepta páginas que debe poder leer (en desarrollo no se exige)
        if settings.EXIGIR_PAGINAS_LEGALES:
            faltantes = paginas_legales_faltantes(
                PaginaLegal.objects.filter(publicada=True).values_list('tipo_pagina', flat=True))
            if faltantes:
                nombres = dict(PaginaLegal.TIPOS_PAGINA)
                raise serializers.ValidationError({'acepta_terminos': (
                    'No es posible comprar todavía: la tienda aún no publica '
                    f"{' ni '.join(nombres[tipo] for tipo in faltantes)}."
                )})

        # RN-02: el backend rechaza un medio que el admin no habilitó o no terminó de configurar
        try:
            self._medio_pago = medios_pago().exigir(data.get('metodo_pago'))
        except MedioPagoNoDisponible as error:
            raise serializers.ValidationError({'metodo_pago': str(error)})

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            if not data.get('email_invitado'):
                raise serializers.ValidationError(
                    {"email_invitado": "Debe proporcionar un correo electronico para comprar como invitado."}
                )

        proveedor = data.get('proveedor_logistico')

        # Toda orden necesita una entrega que el servidor pueda costear (RF-02.3)
        if not proveedor:
            raise serializers.ValidationError({
                'proveedor_logistico': 'Seleccione una opción de entrega cotizada.'
            })

        if proveedor in ENTREGAS_DE_LA_TIENDA:
            # Retiro o entrega coordinada: solo si el admin la activó, con el costo que él definió
            try:
                self._costo_entrega_propia = entregas_de_la_tienda().costo(proveedor)
            except EntregaNoHabilitada as error:
                raise serializers.ValidationError({'proveedor_logistico': str(error)})
        else:
            # Un courier: solo uno que la tienda tenga activo (con sus llaves cargadas)
            try:
                couriers().obtener(proveedor)
            except CourierNoActivo:
                raise serializers.ValidationError({'proveedor_logistico': 'Esa forma de entrega no está disponible.'})

        error_direccion = error_direccion_entrega(proveedor, data.get('direccion_envio_snapshot'))
        if error_direccion:
            raise serializers.ValidationError({'direccion_envio_snapshot': error_direccion})

        # RN-03: stock por variante y precios del catálogo, no los del navegador
        from .acceso_exclusivos import exigir_acceso_productos
        exigir_acceso_productos(data['items'], getattr(request, 'user', None))
        items = [ItemSolicitado(i['producto_mongo_id'], i['variante_sku'], i['cantidad'])
                 for i in data['items']]
        try:
            self._pedido = PrepararPedido(catalogo_variantes()).ejecutar(items, data['subtotal'])
        except SubtotalDesactualizado as error:
            raise serializers.ValidationError({
                'subtotal': str(error),
                'precios_vigentes': [
                    {'producto_mongo_id': l.producto_id, 'variante_sku': l.sku,
                     'nombre': l.nombre, 'precio': str(l.precio_unitario)}
                    for l in error.lineas
                ],
            })
        except ErrorPedido as error:
            raise serializers.ValidationError({'items': str(error)})

        # RF-02.3: un courier cotiza y despacha el paquete que arma el servidor con las medidas del catálogo
        self._paquete = None
        if proveedor not in ENTREGAS_DE_LA_TIENDA:
            try:
                self._paquete = paquete_del_pedido(data['items'])
            except ErrorPedido as error:
                raise serializers.ValidationError({'items': str(error)})

        return data

    @transaction.atomic
    def create(self, validated_data):
        from .acceso_exclusivos import exigir_acceso_productos
        exigir_acceso_productos(validated_data['items'], getattr(self.context.get('request'), 'user', None))
        request = self.context.get('request')
        validated_data.pop('acepta_terminos')
        validated_data.pop('items')
        codigo_promo = validated_data.pop('codigo_promocion', None)
        paquete = self._paquete
        proveedor = validated_data.get('proveedor_logistico')

        # 1. COTIZACIÓN REAL O ENTREGA DE LA TIENDA (validate ya exige comuna y arma el paquete para un courier)
        if proveedor in ENTREGAS_DE_LA_TIENDA:
            costo_envio = float(self._costo_entrega_propia)
        else:
            origen = comuna_origen_tienda()
            destino = validated_data['direccion_envio_snapshot']['comuna']

            # El costo lo cotiza el servidor con el courier elegido; el que envía el navegador se ignora
            try:
                costo_envio = float(precio_envio(proveedor, origen, destino, paquete))
            except CourierNoActivo:
                raise serializers.ValidationError({'proveedor_logistico': 'Esa forma de entrega no está disponible.'})
            except SinCobertura as error:
                raise serializers.ValidationError({'proveedor_logistico': str(error)})
            except CourierNoDisponible:
                raise ProveedorLogisticoNoDisponible()

        # RF-04.1: el código escrito y los automáticos; se aplica el que más ahorra, calculado con el subtotal del
        # catálogo (PrepararPedido ya comprobó que el del navegador coincide)
        subtotal_num = float(self._pedido.subtotal)
        descuento = 0.0
        candidatas = []
        if codigo_promo:
            escrito = Promocion.objects.filter(codigo__iexact=codigo_promo.strip(), is_active=True).order_by('id').first()
            if not escrito or not escrito.esta_vigente:
                raise serializers.ValidationError({
                    'codigo_promocion': 'El cupón ingresado no es válido o ya expiró.'
                })
            if not cumple_minimo(regla_de_promocion(escrito), self._pedido.subtotal):
                raise serializers.ValidationError({'codigo_promocion': mensaje_monto_minimo(escrito)})
            candidatas.append(escrito)
        candidatas += promociones_automaticas_vigentes()

        promo_aplicada = elegir_promocion(candidatas, self._pedido.subtotal, Decimal(str(costo_envio)),
                                          regla_de_promocion)
        if promo_aplicada:
            # El uso se cuenta aquí, dentro de la transacción: si el límite ya se alcanzó (otra compra al mismo
            # tiempo) no se aplica, y si después falla el pago, el rollback lo devuelve
            if not reservar_uso_promocion(promo_aplicada.pk):
                raise serializers.ValidationError({
                    'codigo_promocion': 'Este código ya alcanzó su límite de usos. Revisa el total antes de pagar.'
                })
            regla = regla_de_promocion(promo_aplicada)
            descuento = float(monto_descuento(regla, self._pedido.subtotal))
            if da_envio_gratis(regla, self._pedido.subtotal):
                costo_envio = 0.0
        validated_data['promocion'] = promo_aplicada

        # Suscriptor con una suscripción activa (pedido de un cliente, opcional): su descuento sobre lo que queda
        # después del cupón o la promoción, y envío gratis si su plan lo da en todas sus compras
        beneficios = beneficios_del_comprador(request)
        descuento += float(descuento_suscriptor(Decimal(str(max(0.0, subtotal_num - descuento))),
                                                beneficios.descuento))
        if beneficios.envio_gratis:
            costo_envio = 0.0

        # El total siempre lo calcula el servidor: (subtotal - descuentos) + envío cotizado; nunca negativo (RF-04.1)
        validated_data['costo_envio'] = costo_envio
        validated_data['total_final'] = max(0.0, (subtotal_num - descuento) + costo_envio)
        # La orden de transporte se genera con el mismo paquete que se cotizó
        validated_data['paquete'] = (
            {campo: str(valor) for campo, valor in asdict(paquete).items()} if paquete else None)

        # 2. ASIGNAR USUARIO
        if request and request.user.is_authenticated:
            validated_data['usuario'] = request.user
            validated_data['email_invitado'] = ''

        # 3. CREAR LA ORDEN EN BASE DE DATOS
        # DRF no guarda un serializer anidado: los datos de la empresa se asignan después de crear la orden
        datos_empresa = validated_data.pop('datos_empresa', None)
        guardar_datos_empresa = validated_data.pop('guardar_datos_empresa', False)
        orden = super().create(validated_data)
        completar = {}
        if datos_empresa:
            completar['datos_empresa'] = datos_empresa
        if self._medio_pago.codigo == CodigoMedioPago.TRANSFERENCIA:
            # El plazo de la tienda en este momento: si lo cambia después, esta orden conserva el suyo
            plazo = plazo_pago(orden.fecha_creacion, plazo_pago_transferencia(self._medio_pago))
            completar.update(fecha_limite_pago=plazo.vence, fecha_recordatorio_pago=plazo.recordar)
        if completar:
            for campo, valor in completar.items():
                setattr(orden, campo, valor)
            orden.save(update_fields=list(completar))
        if datos_empresa and guardar_datos_empresa and orden.usuario_id:
            EmpresaComprador.objects.update_or_create(usuario_id=orden.usuario_id, defaults=datos_empresa)
        DetalleOrden.objects.bulk_create([
            DetalleOrden(
                orden=orden, producto_mongo_id=linea.producto_id, variante_sku=linea.sku,
                nombre_producto_snapshot=linea.nombre,
                precio_unitario_snapshot=float(linea.precio_unitario), cantidad=linea.cantidad,
            )
            for linea in self._pedido.lineas
        ])

        # 4. INTEGRACIÓN CON PASARELAS DE PAGO
        metodo_pago = validated_data.get('metodo_pago')
        url_pago = None

        if metodo_pago in PASARELAS:
            url_retorno, url_aviso = urls_pasarela(metodo_pago, request)
            medio = pasarela(metodo_pago)
            try:
                pago = medio.iniciar(str(orden.id), orden.total_final, url_retorno, url_aviso)
            except ErrorPasarelaPago as exc:
                orden.delete()
                raise serializers.ValidationError({
                    "metodo_pago": f"No se pudo iniciar el pago con {medio.nombre}: {exc}"
                })
            url_pago = pago.url_pago
            orden.id_transaccion_pasarela = pago.referencia
            orden.save()

        # RF-04.2: resumen de la compra al comprador (si Transbank falló, la orden ya se borró arriba)
        notificador_pedidos().notificar(orden.id, EventoPedido.RECIBIDO)

        # Almacenamos temporalmente la URL para que la vista de Checkout se la pase a React
        orden.url_pago = url_pago
        return orden

class AgregarItemSerializer(serializers.Serializer):
    producto_mongo_id = serializers.CharField(max_length=255)
    variante_sku = serializers.CharField(max_length=255)
    cantidad = serializers.IntegerField(default=1, min_value=1)

    def validate(self, data):
        producto_id = data.get('producto_mongo_id')
        sku = data.get('variante_sku')
        cantidad_solicitada = data.get('cantidad', 1)

        try:
            producto = Producto.objects(id=producto_id).first()
        except MongoValidationError:
            raise serializers.ValidationError({"producto_mongo_id": "El formato del ID del producto no es valido."})

        if not producto:
            raise serializers.ValidationError({"producto_mongo_id": "El producto solicitado no existe en el catalogo."})

        from .acceso_exclusivos import exigir_acceso_productos
        exigir_acceso_productos([data], getattr(self.context.get('request'), 'user', None))

        variante_encontrada = producto.variantes.filter(sku=sku).first()
        if not variante_encontrada:
            raise serializers.ValidationError({"variante_sku": "La variante especificada no existe para este producto."})

        stock_disponible = variante_encontrada.stock
        if stock_disponible <= 0:
            raise serializers.ValidationError({"stock": "Esta variante se encuentra agotada y no puede agregarse al carrito."})
        if cantidad_solicitada > stock_disponible:
            raise serializers.ValidationError({"cantidad": f"Stock insuficiente. Solo quedan {stock_disponible} unidades disponibles."})

        return data
class AdminOrdenCompraEstadoSerializer(serializers.Serializer):
    # Solo valida la entrada; las transiciones las decide CambiarEstadoPedido
    estado = serializers.ChoiceField(choices=OrdenCompra.ESTADOS_PEDIDO)


class AdminOrdenCompraSerializer(serializers.ModelSerializer):
    """Listado del panel (RF-03.3): incluye la revisión pendiente y las transiciones permitidas."""

    email_cliente = serializers.SerializerMethodField()
    transiciones_permitidas = serializers.SerializerMethodField()
    puede_generar_orden_transporte = serializers.SerializerMethodField()
    # Documentos tributarios (domain/documentos_tributarios.py): el que corresponde y lo que falta emitir. La vista
    # pasa el modelo de emisión de la tienda en el contexto, para no leerlo por cada pedido
    documento_requerido = serializers.SerializerMethodField()
    documento_por_emitir = serializers.SerializerMethodField()

    get_email_cliente = OrdenCompraSerializer.get_email_cliente

    class Meta:
        model = OrdenCompra
        fields = [
            'id', 'fecha_creacion', 'estado', 'email_invitado', 'email_cliente', 'metodo_pago',
            'nombre_destinatario', 'telefono_destinatario',
            # La entrega coordinada la hace la tienda: necesita la dirección del comprador
            'direccion_envio_snapshot',
            # Compra como empresa: con estos datos la tienda emite la factura
            'datos_empresa',
            'total_final', 'proveedor_logistico', 'requiere_revision', 'motivo_revision',
            'motivo_cancelacion', 'transiciones_permitidas', 'numero_seguimiento_tracking',
            'error_orden_transporte', 'puede_generar_orden_transporte',
            'documento_requerido', 'documento_por_emitir', 'folio_documento', 'folio_nota_credito',
            # Pedido de un ciclo de una suscripción: el panel lo marca (vacíos en las compras normales)
            'suscripcion', 'ciclo_fecha',
        ]
        read_only_fields = fields

    def _modelo_emision(self):
        return self.context.get('modelo_emision') or ModeloEmision.VOUCHER

    def get_documento_requerido(self, obj):
        return documento_requerido(obj.metodo_pago, bool(obj.datos_empresa), self._modelo_emision())

    def get_documento_por_emitir(self, obj):
        return documento_por_emitir(obj.estado, obj.metodo_pago, bool(obj.datos_empresa), self._modelo_emision(),
                                    obj.folio_documento, obj.folio_nota_credito)

    def get_transiciones_permitidas(self, obj):
        return [estado.value for estado in transiciones_desde(obj.estado)]

    def get_puede_generar_orden_transporte(self, obj):
        """Muestra el botón del panel solo si el backend aceptaría generar la OT."""
        if not es_entrega_con_courier(obj.proveedor_logistico) or obj.numero_seguimiento_tracking:
            return False
        try:
            validar_generacion_orden_transporte(obj.estado, obj.requiere_revision)
        except OrdenTransporteNoPermitida:
            return False
        return True


class DireccionEnvioSerializer(serializers.ModelSerializer):
    class Meta:
        model = DireccionEnvio
        fields = [
            'id',
            'calle',
            'calle_numero',
            'dpto_casa',
            'comuna',
            'ciudad',
            'region',
            'codigo_postal',
            'es_predeterminado'
        ]

class PaginaLegalSerializer(serializers.ModelSerializer):
    """Listado público (enlaces del footer): sin el contenido."""

    class Meta:
        model = PaginaLegal
        fields = ['id', 'tipo_pagina', 'titulo', 'ultima_actualizacion']


class PaginaLegalDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaginaLegal
        fields = ['tipo_pagina', 'titulo', 'contenido', 'ultima_actualizacion']


class PaginaLegalAdminSerializer(serializers.ModelSerializer):
    """RF-03.5: el admin redacta, guarda como borrador y publica cada página."""

    class Meta:
        model = PaginaLegal
        fields = ['tipo_pagina', 'titulo', 'contenido', 'publicada', 'ultima_actualizacion']
        read_only_fields = ['tipo_pagina', 'ultima_actualizacion']
        extra_kwargs = {'contenido': {'allow_blank': True}}

    def validate_contenido(self, value):
        # Se muestra tal cual en la tienda: solo queda el formato del editor (XSS)
        return limpiar_html(value)

    def validate(self, data):
        publicada = data.get('publicada', self.instance.publicada if self.instance else False)
        contenido = data.get('contenido', self.instance.contenido if self.instance else '')
        if publicada and not tiene_texto(contenido):
            raise serializers.ValidationError({'contenido': 'No se puede publicar una página sin contenido.'})
        return data


class PublicacionEntradaSerializer(serializers.Serializer):
    """Formulario del panel para una publicación del blog. Las reglas (título, estado...) están en domain/blog.py."""

    titulo = serializers.CharField(required=False, allow_blank=True, default='', max_length=1000)
    resumen = serializers.CharField(required=False, allow_blank=True, default='', max_length=1000)
    contenido = serializers.CharField(required=False, allow_blank=True, default='', max_length=100_000,
                                      trim_whitespace=False)
    estado = serializers.CharField(required=False, allow_blank=True, default='')
    youtube = serializers.CharField(required=False, allow_blank=True, default='', max_length=500)
    # Sin portada ni quitar_portada, la portada queda como estaba
    portada = ArchivoImagenField(required=False)
    quitar_portada = serializers.BooleanField(required=False, default=False)

    def validate_contenido(self, value):
        # Se muestra tal cual en la tienda: solo queda el formato del editor (XSS)
        return limpiar_html(value)


class FotosPublicacionSerializer(serializers.Serializer):
    fotos = serializers.ListField(child=ArchivoImagenField(), allow_empty=False, max_length=MAX_FOTOS_PUBLICACION)


class FotosCotizacionSerializer(serializers.Serializer):
    """Las fotos de la idea del cliente: el mismo control que las del catálogo (formato real, tamaño, píxeles) y
    se vuelven a codificar, sin los datos de la cámara (ej. la ubicación GPS de una foto del celular)."""
    fotos = serializers.ListField(child=ArchivoImagenField(), required=False, max_length=MAX_FOTOS_COTIZACION)


class FotoPublicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoPublicacion
        fields = ['id', 'imagen']


class PublicacionResumenSerializer(serializers.ModelSerializer):
    """Tarjeta de la lista pública del blog: sin el texto ni la galería."""

    class Meta:
        model = Publicacion
        fields = ['titulo', 'slug', 'resumen', 'portada', 'fecha_publicacion']


class PublicacionDetalleSerializer(serializers.ModelSerializer):
    fotos = FotoPublicacionSerializer(many=True, read_only=True)

    class Meta:
        model = Publicacion
        fields = ['titulo', 'slug', 'resumen', 'contenido', 'portada', 'fotos', 'youtube_id', 'fecha_publicacion']


class PublicacionAdminSerializer(serializers.ModelSerializer):
    fotos = FotoPublicacionSerializer(many=True, read_only=True)

    class Meta:
        model = Publicacion
        fields = ['id', 'titulo', 'slug', 'resumen', 'contenido', 'portada', 'fotos', 'youtube_id', 'estado',
                  'fecha_publicacion', 'actualizada']

class MedioPagoAdminSerializer(serializers.Serializer):
    """Entrada del panel: las credenciales pueden volver enmascaradas (se conservan) o vacías (se borran)."""

    habilitado = serializers.BooleanField()
    datos = serializers.DictField(child=serializers.CharField(allow_blank=True, max_length=500),
                                  required=False, default=dict)


def medio_pago_para_panel(medio):
    """Lo que ve el admin de un medio de pago: nunca una credencial completa."""
    return {
        'codigo': medio.codigo.value,
        'nombre': medio.definicion.nombre,
        'habilitado': medio.habilitado,
        # False: el checkout aún no sabe cobrar con este medio (se pueden cargar sus datos, no se ofrece)
        'integracion_lista': medio.definicion.integracion_lista,
        # Habilitado, con sus datos completos y con la integración lista: se ofrece al comprador
        'disponible': medio.disponible,
        'faltantes': medio.faltantes,
        'campos': [{
            'nombre': campo.nombre,
            'etiqueta': campo.etiqueta,
            'secreto': campo.secreto,
            'opciones': list(campo.opciones),
            'obligatorio': campo.obligatorio,
            # Ej. ['ambiente', 'PRODUCCION']: obligatorio solo con ese valor
            'obligatorio_si': list(campo.obligatorio_si) if campo.obligatorio_si else None,
            # 'rut', 'correo' o 'numero_cuenta' (lo valida el servidor); el panel elige el teclado
            'formato': campo.formato,
        } for campo in medio.definicion.campos],
        'datos': medio.datos_visibles(),
    }


class CredencialesCourierSerializer(serializers.Serializer):
    """Entrada del panel: una llave que vuelve enmascarada se conserva y una vacía se borra."""

    datos = serializers.DictField(child=serializers.CharField(allow_blank=True, max_length=500))


def courier_para_panel(courier):
    """Lo que ve el admin de las llaves de un courier: nunca una llave completa."""
    credenciales = courier.credenciales
    return {
        'codigo': courier.codigo,
        'nombre': courier.nombre,
        'ayuda': courier.ayuda,
        'configuradas': credenciales.configuradas,
        'faltantes': credenciales.faltantes,
        # Igual que los campos de un medio de pago (medio_pago_para_panel)
        'campos': [{
            'nombre': campo.nombre,
            'etiqueta': campo.etiqueta,
            # True: llave de API, llega enmascarada
            'secreto': campo.secreto,
            'opciones': list(campo.opciones),
            'obligatorio': campo.obligatorio,
            # Ej. ['ambiente', 'PRODUCCION']: obligatorio solo con ese valor
            'obligatorio_si': list(campo.obligatorio_si) if campo.obligatorio_si else None,
            # 'rut' o 'digitos' (lo valida el servidor); el panel elige el teclado
            'formato': campo.formato,
        } for campo in credenciales.campos],
        'datos': credenciales.visibles(),
    }

class PromocionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promocion
        # fecha_expiracion: el cupón deja de valer desde ese momento (sin fecha no vence)
        fields = ['id', 'codigo', 'tipo_descuento', 'valor_descuento', 'umbral_envio_gratis', 'fecha_expiracion',
                  'is_active', 'monto_minimo', 'automatica', 'usos_maximos', 'usos']
        # Los usos los cuenta el checkout, no el admin
        read_only_fields = ['usos']

    def validate(self, attrs):
        # Las reglas están en domain/promociones.py; en una edición parcial se completan con lo guardado
        campos = ('codigo', 'tipo_descuento', 'valor_descuento', 'umbral_envio_gratis', 'monto_minimo', 'automatica',
                  'usos_maximos')
        datos = {campo: attrs.get(campo, getattr(self.instance, campo, None)) for campo in campos}
        try:
            codigo = validar_promocion(**datos)
        except PromocionInvalida as error:
            raise serializers.ValidationError(error.errores)
        # El comprador escribe el código sin distinguir mayúsculas: dos que solo difieren en eso serían el mismo
        repetidos = Promocion.objects.filter(codigo__iexact=codigo)
        if self.instance is not None:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError({'codigo': 'Ya existe un código igual.'})
        if 'codigo' in attrs:
            attrs['codigo'] = codigo
        return attrs
