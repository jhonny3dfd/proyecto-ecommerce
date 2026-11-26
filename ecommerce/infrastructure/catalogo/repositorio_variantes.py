"""Adaptadores MongoDB de los puertos CatalogoVariantes, InventarioVariantes, NombresProductos, StockCatalogo y
CatalogoSuscripciones."""

from decimal import Decimal

from bson import ObjectId
from bson.errors import InvalidId
from mongoengine.errors import ValidationError as MongoValidationError

from ecommerce.application.cotizaciones import NombresProductos
from ecommerce.application.dashboard import StockCatalogo, VariantePocoStock
from ecommerce.application.suscripciones import CatalogoSuscripciones, VarianteElegible
from ecommerce.application.ventas import CatalogoVariantes, InventarioVariantes
from ecommerce.domain.logistica import MedidasEnvio
from ecommerce.domain.ventas import VarianteCatalogo

from .documents import Producto
from .images import url_imagen


class MongoCatalogoVariantes(CatalogoVariantes):
    def obtener(self, producto_id, sku):
        try:
            producto = Producto.objects(id=producto_id).first()
        except MongoValidationError:
            # ID con formato inválido: se trata igual que un producto inexistente
            return None
        if producto is None:
            return None

        variante = next((v for v in producto.variantes if str(v.sku) == str(sku)), None)
        if variante is None:
            return None

        # Si la variante tiene precio_oferta válido (> 0 y menor al precio normal), se usa como precio vigente
        tiene_oferta = (
            getattr(variante, 'precio_oferta', None) is not None
            and variante.precio_oferta > 0
            and (variante.precio is None or variante.precio_oferta < variante.precio)
        )
        precio_vigente = variante.precio_oferta if tiene_oferta else variante.precio

        return VarianteCatalogo(
            # Mismo nombre que muestra el carrito del frontend
            nombre=f'{producto.nombre} - {variante.sku}',
            precio=Decimal(precio_vigente),
            stock=int(variante.stock),
            disponible=bool(producto.activo and producto.publicado and not getattr(producto, 'coleccion_privada', False)),
            medidas=MedidasEnvio(*(Decimal(str(getattr(variante, campo) or 0))
                                   for campo in ('peso_kg', 'alto_cm', 'ancho_cm', 'largo_cm'))),
        )


def _medidas(variante) -> MedidasEnvio:
    return MedidasEnvio(*(Decimal(str(getattr(variante, campo) or 0))
                          for campo in ('peso_kg', 'alto_cm', 'ancho_cm', 'largo_cm')))


class MongoCatalogoSuscripciones(CatalogoSuscripciones):
    """La variante que el cliente recibe en su suscripción, con la categoría del producto (el plan admite productos
    por categoría o puntuales)."""

    def variante(self, producto_id, sku):
        try:
            producto = Producto.objects(id=producto_id).first()
        except MongoValidationError:
            return None
        if producto is None:
            return None
        variante = next((v for v in producto.variantes if str(v.sku) == str(sku)), None)
        if variante is None:
            return None
        # "Catuai Amarillo - Grano": los valores de sus atributos; sin atributos, el SKU
        detalle = ', '.join(str(valor) for valor in (variante.atributos_variables or {}).values() if valor)
        return VarianteElegible(
            producto_id=str(producto.id), sku=str(variante.sku), nombre=f'{producto.nombre} - {detalle or variante.sku}',
            categoria=producto.categoria or '', stock=int(variante.stock),
            disponible=bool(producto.activo and producto.publicado and not getattr(producto, 'coleccion_privada', False)),
            medidas=_medidas(variante),
        )


class MongoInventarioVariantes(InventarioVariantes):
    def descontar(self, producto_id, sku, cantidad):
        return Producto.reducir_stock_variante(producto_id, sku, cantidad)

    def reponer(self, producto_id, sku, cantidad):
        Producto.reponer_stock_variante(producto_id, sku, cantidad)


class MongoNombresProductos(NombresProductos):
    """Para cotizar: solo productos activos y publicados (un borrador no existe para el público)."""

    def nombre(self, producto_id):
        try:
            producto = Producto.objects(id=producto_id, activo=True, publicado=True).only('nombre').first()
        except (MongoValidationError, InvalidId):
            return None
        return producto.nombre if producto else None


class MongoStockCatalogo(StockCatalogo):
    """Para "Para hoy" del dashboard: las variantes de productos activos (publicados o en borrador) con poco stock.
    Un producto dado de baja ya no se vende: no avisa."""

    def con_poco_stock(self, umbral):
        productos = Producto.objects(activo=True, variantes__stock__lte=umbral).only('nombre', 'variantes')
        return [
            VariantePocoStock(
                producto_id=str(producto.id), producto=producto.nombre, sku=str(variante.sku),
                detalle=' · '.join(f'{nombre}: {valor}' for nombre, valor in (variante.atributos_variables or {}).items()),
                stock=int(variante.stock or 0),
            )
            for producto in productos for variante in producto.variantes if int(variante.stock or 0) <= umbral
        ]


def _texto_variante(variante):
    return ' · '.join(f'{nombre}: {valor}' for nombre, valor in (variante.atributos_variables or {}).items())


def fotos_de_variantes(pares, request=None):
    """Para "Mis pedidos": la foto que tiene hoy en el catálogo cada variante comprada (la suya o, si no tiene, la
    primera del producto) y el texto de su variante. Una sola consulta para todos los pedidos.

    Devuelve {(producto_id, sku): {'imagen': url o None, 'variante': 'Talla: M'}}. Un producto borrado o con un id
    inválido no aparece: el historial lo muestra sin foto.
    """
    ids = {str(producto_id) for producto_id, _ in pares if ObjectId.is_valid(str(producto_id))}
    if not ids:
        return {}
    fotos = {}
    for producto in Producto.objects(id__in=list(ids)).only('imagenes', 'variantes'):
        portada = next(iter(producto.imagenes or []), None)
        for variante in producto.variantes:
            imagen = variante.imagen_especifica or portada
            fotos[(str(producto.id), str(variante.sku))] = {
                'imagen': url_imagen(imagen, request) if imagen else None,
                'variante': _texto_variante(variante),
            }
    return {par: fotos[par] for par in ((str(p), str(s)) for p, s in pares) if par in fotos}
