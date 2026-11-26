from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from mongoengine import Document, EmbeddedDocument, fields

from ecommerce.domain.catalogo import (
    COLORES_ETIQUETA_PRODUCTO,
    LARGO_ETIQUETA_PRODUCTO,
    ColeccionPrivadaInvalida,
    validar_obra_no_es_version_de_otra,
    validar_version_a_la_venta,
)

class Variante(EmbeddedDocument):
    sku = fields.StringField(required=True, unique=True)
    precio = fields.DecimalField(required=True, precision=2)
    precio_oferta = fields.DecimalField(null=True, precision=2)
    stock = fields.IntField(required=True, default=0)
    imagen_especifica = fields.StringField(null=True, blank=True)
    atributos_variables = fields.DictField(default=dict)
    
    # --- CAMPOS LOGÍSTICOS A NIVEL DE SKU (MEJOR PRÁCTICA) ---
    peso_kg = fields.FloatField(default=1.0)
    alto_cm = fields.IntField(default=10)
    ancho_cm = fields.IntField(default=10)
    largo_cm = fields.IntField(default=10)

class Producto(Document):
    meta = {
        'collection': 'productos',
        'indexes': [
            'activo',
            'publicado',
            'categoria',
            'fecha_creacion',
            'colecciones',
            ('activo', 'publicado', 'colecciones'),
            ('activo', 'publicado', 'categoria'),
            ('activo', 'publicado', '-fecha_creacion'),
            ('activo', 'publicado', 'precio_minimo_vigente'),
            ('activo', 'publicado', '-precio_minimo_vigente'),
            ('activo', 'publicado', 'variantes.precio'),
            'variantes.sku',
            # Índices sobre rutas internas de atributos y comodín dinámico (SCRUM-179 / E03)
            {'fields': [('activo', 1), ('publicado', 1), ('categoria', 1), ('atributos_globales.color', 1)]},
            {'fields': [('activo', 1), ('publicado', 1), ('categoria', 1), ('atributos_globales.capacidad_gb', 1)]},
            {'fields': [('activo', 1), ('publicado', 1), ('categoria', 1), ('atributos_globales.talla', 1)]},
            {'fields': [('activo', 1), ('publicado', 1), ('categoria', 1), ('atributos_globales.marca', 1)]},
            {'fields': [('atributos_globales.color', 1)]},
            {'fields': [('atributos_globales.capacidad_gb', 1)]},
            {'fields': [('atributos_globales.$**', 1)]},
        ],
    }

    nombre = fields.StringField(required=True, max_length=255)
    descripcion = fields.StringField(null=True, blank=True)
    categoria = fields.StringField(required=True)
    meta_titulo = fields.StringField(max_length=60, null=True, blank=True)
    meta_descripcion = fields.StringField(max_length=160, null=True, blank=True)
    etiqueta = fields.StringField(default='', max_length=LARGO_ETIQUETA_PRODUCTO)
    etiqueta_color = fields.StringField(default='primary', choices=COLORES_ETIQUETA_PRODUCTO)
    solo_suscriptores = fields.BooleanField(default=False)
    planes_suscripcion = fields.ListField(fields.IntField(min_value=1), default=list)
    # Managed images use storage keys internally; serializers expose their URLs.
    # Existing external HTTP(S) URLs remain supported.
    imagenes = fields.ListField(fields.StringField(), default=list)
    # Video de YouTube opcional de la ficha (pedido de Alan): solo el ID, validado por domain/youtube.py.
    # Los productos anteriores no lo tienen y se leen con ''
    youtube_id = fields.StringField(default='', max_length=11)
    fecha_creacion = fields.DateTimeField(required=True)
    activo = fields.BooleanField(default=True)
    publicado = fields.BooleanField(default=False)
    atributos_globales = fields.DictField(default=dict)
    colecciones = fields.ListField(fields.StringField(), default=list)
    
    # Colección privada y enlace a versión disponible en print (SCRUM-197)
    coleccion_privada = fields.BooleanField(default=False)
    version_a_la_venta = fields.StringField(null=True, blank=True)
    texto_boton_version = fields.StringField(default='Disponible en print', max_length=100)

    # Campo calculado para ordenamiento O(1) de precio vigente (SCRUM-179 / E01)
    precio_minimo_vigente = fields.DecimalField(null=True, precision=2)

    # relación de 1 a N embebida dentro del mismo documento
    variantes = fields.EmbeddedDocumentListField(Variante)

    def actualizar_precio_minimo_vigente(self):
        """Calcula el precio mínimo vigente considerando precio_oferta y múltiples variantes (E01)."""
        precios = []
        for v in (self.variantes or []):
            if v.precio is None:
                continue
            try:
                p = float(v.precio)
            except (ValueError, TypeError):
                continue
            if v.precio_oferta is not None:
                try:
                    o = float(v.precio_oferta)
                    if 0 < o < p:
                        precios.append(o)
                    else:
                        precios.append(p)
                except (ValueError, TypeError):
                    precios.append(p)
            else:
                precios.append(p)
        self.precio_minimo_vigente = min(precios) if precios else None
        return self.precio_minimo_vigente

    def clean(self):
        super().clean()
        self.actualizar_precio_minimo_vigente()

        # Validaciones de Colección privada en el dominio (SCRUM-197)
        if self.version_a_la_venta:
            version_id = str(self.version_a_la_venta).strip()
            try:
                target = Producto.objects(id=version_id).first()
            except Exception:
                raise MongoValidationError('El producto seleccionado como versión a la venta no es válido.')
            try:
                validar_version_a_la_venta(
                    producto_id=str(self.id) if self.id else None,
                    version_id=version_id,
                    target_existe=bool(target),
                    target_es_coleccion_privada=bool(getattr(target, 'coleccion_privada', False)) if target else False,
                )
            except ColeccionPrivadaInvalida as error:
                raise MongoValidationError(str(error))

        if self.coleccion_privada and self.id:
            referenciador = Producto.objects(version_a_la_venta=str(self.id)).first()
            try:
                validar_obra_no_es_version_de_otra(
                    producto_id=str(self.id),
                    coleccion_privada=self.coleccion_privada,
                    nombre_referenciador=referenciador.nombre if referenciador else None,
                )
            except ColeccionPrivadaInvalida as error:
                raise MongoValidationError(str(error))

    def save(self, *args, **kwargs):
        self.actualizar_precio_minimo_vigente()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.categoria})"

    @classmethod
    def reducir_stock_variante(cls, producto_id, sku, cantidad):
        """Descuenta stock de una variante de forma atómica y condicional (RN-03).

        Un único update filtra por stock suficiente, así dos compras simultáneas de la última
        unidad producen una sola venta. Devuelve False si no hay stock o no existe el SKU.
        Un producto de colección privada nunca descuenta stock (rechazado).
        """
        cantidad = int(cantidad)
        if cantidad < 1:
            return False
        try:
            id_producto = ObjectId(producto_id)
        except (InvalidId, TypeError):
            return False
        resultado = cls._get_collection().update_one(
            {'_id': id_producto,
             'coleccion_privada': {'$ne': True},
             'variantes': {'$elemMatch': {'sku': str(sku), 'stock': {'$gte': cantidad}}}},
            {'$inc': {'variantes.$.stock': -cantidad}},
        )
        return resultado.modified_count == 1

    @classmethod
    def reponer_stock_variante(cls, producto_id, sku, cantidad):
        """Devuelve stock a una variante (pago sin stock o pedido cancelado). False si no existe."""
        cantidad = int(cantidad)
        if cantidad < 1:
            return False
        try:
            id_producto = ObjectId(producto_id)
        except (InvalidId, TypeError):
            return False
        resultado = cls._get_collection().update_one(
            {'_id': id_producto, 'variantes.sku': str(sku)},
            {'$inc': {'variantes.$.stock': cantidad}},
        )
        return resultado.modified_count == 1


class ImagenPendienteBorrado(Document):
    """Durable, idempotent cleanup intents for files owned by the catalog."""

    meta = {'collection': 'imagenes_catalogo_pendientes_borrado'}
    clave = fields.StringField(required=True, unique=True)
    fecha_creacion = fields.DateTimeField(default=lambda: datetime.now(timezone.utc))
