import logging
import math
import re

from bson.errors import InvalidId
from django.conf import settings
from mongoengine.errors import MongoEngineException, ValidationError as MongoValidationError
from pymongo.errors import PyMongoError
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.domain.imagenes import (
    AlmacenamientoImagenNoDisponible,
    GaleriaEnConflicto,
    LimiteGaleriaExcedido,
)
from ecommerce.application.vitrina import SeleccionarVitrina
from ecommerce.domain.destacados import TITULO_POR_DEFECTO, ModoVitrina, TipoDestacado, ids_por_tipo
from ecommerce.infrastructure.usuarios.permissions import IsAdministrador
from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal, Publicacion
from ecommerce.infrastructure.ventas.repositorio_blog import DjangoPublicacionesVitrina
from ecommerce.infrastructure.ventas.repositorio_ventas import DjangoVentasPorProducto

from ecommerce.infrastructure.ventas.models import ConfiguracionGlobal
from ecommerce.domain.catalogo import limpiar_colecciones, ordenar_categorias

from .documents import ImagenPendienteBorrado, Producto
from .image_adapters import eliminar_producto, servicio_galeria
from .images import (
    CLAVE_IMAGEN, GaleriaUploadSerializer, descriptor_imagen,
    es_imagen_gestionada, url_imagen,
)
from .permissions import LecturaPublicaEscrituraAdmin
from .repositorio_vitrina import MongoCatalogoVitrina
from .serializers import ProductoSerializer
from .upload_handlers import CatalogoImageUploadHandler


logger = logging.getLogger(__name__)


class CatalogoAPIView(APIView):
    def get_object(self, id):
        try:
            return Producto.objects.get(id=id)
        except (Producto.DoesNotExist, MongoValidationError, InvalidId) as exc:
            raise NotFound('Producto no encontrado.') from exc

    def handle_exception(self, exc):
        if isinstance(exc, GaleriaEnConflicto):
            return Response(
                {'detail': 'La galería cambió durante la operación. Recarga el producto y vuelve a intentarlo.'},
                status=status.HTTP_409_CONFLICT,
            )
        if isinstance(exc, LimiteGaleriaExcedido):
            return Response({'imagenes': ['Se ha superado el límite de imágenes por producto.']}, status=400)
        if isinstance(exc, MongoValidationError):
            return Response({'detail': 'Los datos del producto no son válidos.'}, status=400)
        if isinstance(exc, (AlmacenamientoImagenNoDisponible, MongoEngineException, PyMongoError, OSError)):
            logger.exception('Fallo de persistencia en el catálogo')
            return Response({'detail': 'El catálogo o su almacenamiento no están disponibles. Inténtalo nuevamente.'}, status=503)
        return super().handle_exception(exc)


def obtener_versiones_publicadas(productos) -> set[str]:
    """Retorna los IDs de las versiones a la venta que están publicadas, activas y no son privadas."""
    versiones_ids = [str(p.version_a_la_venta) for p in productos if getattr(p, 'version_a_la_venta', None)]
    if not versiones_ids:
        return set()
    try:
        return {
            str(p.id) for p in Producto.objects(
                id__in=versiones_ids, activo=True, publicado=True, coleccion_privada__ne=True
            ).only('id')
        }
    except Exception:
        return set()


def seleccionar_vitrina():
    """Las pruebas lo reemplazan para no depender de las ventas ni del catálogo reales."""
    return SeleccionarVitrina(DjangoVentasPorProducto(), MongoCatalogoVitrina(),
                              publicaciones=DjangoPublicacionesVitrina())


class VitrinaView(CatalogoAPIView):
    """RF-01.1: secciones de la landing (pública): más vendidos o destacados, y últimos agregados.

    Cada destacado sale como {tipo, id, nombre, imagen, enlace}; los productos agregan su categoría y sus variantes.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        configuracion = ConfiguracionGlobal.objects.filter(pk=1).values(
            'vitrina_modo', 'destacados', 'destacados_titulo', 'blog_activo').first() or {}
        vitrina = seleccionar_vitrina().ejecutar(
            configuracion.get('vitrina_modo', ModoVitrina.MAS_VENDIDOS), configuracion.get('destacados') or [],
            bool(configuracion.get('blog_activo')))

        ids_destacados = ids_por_tipo(vitrina.destacados, TipoDestacado.PRODUCTO)
        ids = set(vitrina.mas_vendidos) | set(vitrina.recientes) | set(ids_destacados)
        productos = {str(p.id): p for p in Producto.objects(id__in=list(ids))} if ids else {}
        id_publicaciones = ids_por_tipo(vitrina.destacados, TipoDestacado.PUBLICACION)
        publicaciones = ({str(p.pk): p for p in Publicacion.objects.filter(pk__in=id_publicaciones)}
                         if id_publicaciones else {})

        def serializar(lista):
            prods = [productos[i] for i in lista if i in productos]
            versiones_publicadas = obtener_versiones_publicadas(prods)
            return ProductoSerializer(prods, many=True,
                                      context={'request': request, 'versiones_publicadas': versiones_publicadas}).data

        def destacado(elegido):
            if elegido['tipo'] == TipoDestacado.PRODUCTO:
                producto = productos.get(elegido['id'])
                if producto is None:
                    return None
                datos = ProductoSerializer(producto, context={'request': request}).data
                return {'tipo': elegido['tipo'], 'id': elegido['id'], 'nombre': datos['nombre'],
                        'categoria': datos.get('categoria') or '', 'imagen': (datos.get('imagenes') or [None])[0],
                        'enlace': f'/catalogo/producto/{elegido["id"]}', 'variantes': datos.get('variantes', []),
                        'coleccion_privada': datos.get('coleccion_privada', False),
                        'etiqueta': datos['etiqueta'], 'etiqueta_color': datos['etiqueta_color']}
            publicacion = publicaciones.get(elegido['id'])
            if publicacion is None:
                return None
            portada = request.build_absolute_uri(publicacion.portada.url) if publicacion.portada else None
            return {'tipo': elegido['tipo'], 'id': elegido['id'], 'nombre': publicacion.titulo, 'imagen': portada,
                    'enlace': f'/blog/{publicacion.slug}'}

        # Entre la selección y la lectura pudo despublicarse algo: se descarta sin romper la sección
        destacados = [datos for datos in map(destacado, vitrina.destacados) if datos]
        return Response({
            'mas_vendidos': serializar(vitrina.mas_vendidos),
            'recientes': serializar(vitrina.recientes),
            'destacados': destacados,
            'destacados_titulo': configuracion.get('destacados_titulo') or TITULO_POR_DEFECTO,
        })


def obtener_filtros_catalogo(orden_categorias=None):
    """RF-01.3: extrae las categorías y valores de atributos disponibles de productos activos y publicados."""
    try:
        # Una lectura proyectada conserva las opciones de todas las páginas sin
        # consultar e hidratar de nuevo los productos de cada categoría.
        prods = Producto.objects.filter(activo=True, publicado=True).only(
            'categoria', 'atributos_globales', 'colecciones'
        ).as_pymongo()
        atributos = {}
        colecciones_activas = []
        for producto in prods:
            cols = producto.get('colecciones', [])
            if isinstance(cols, list):
                colecciones_activas.extend(c.strip() for c in cols if isinstance(c, str))
            cat = producto.get('categoria')
            if not cat:
                continue
            opciones = atributos.setdefault(cat, {})
            valores = producto.get('atributos_globales')
            if isinstance(valores, dict):
                for clave, valor in valores.items():
                    opciones.setdefault(clave, set())
                    if valor is not None and str(valor).strip():
                        opciones[clave].add(str(valor))
        if orden_categorias is None:
            orden_categorias = ConfiguracionGlobal.objects.filter(pk=1).values_list('orden_categorias', flat=True).first() or []
        categorias = ordenar_categorias(atributos, orden_categorias)
        atributos = {cat: {clave: sorted(valores) for clave, valores in atributos[cat].items()}
                     for cat in categorias}
        # Ordenar antes de deduplicar elige una escritura existente de forma
        # determinista, independientemente del orden de lectura de los productos.
        colecciones = limpiar_colecciones(sorted(colecciones_activas))
        return {'categorias': categorias, 'atributos': atributos, 'colecciones': colecciones}
    except Exception as exc:
        logger.warning('No se pudieron obtener los filtros de catálogo: %s', exc)
        return {'categorias': [], 'atributos': {}, 'colecciones': []}

def obtener_colecciones_vigentes():
    """Extrae colecciones únicas solo de productos activos y publicados"""
    productos_vigentes = Producto.objects.filter(activo=True, publicado=True)
    colecciones_disponibles = set()
    
    for prod in productos_vigentes:
        if hasattr(prod, 'colecciones') and prod.colecciones:
            for col in prod.colecciones:
                if col:
                    colecciones_disponibles.add(col.strip())
                    
    return sorted(list(colecciones_disponibles))

class FiltrosCatalogoView(CatalogoAPIView):
    """RF-01.3: entrega las categorías y opciones de atributos disponibles en el catálogo."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(obtener_filtros_catalogo())


class ProductoListCreateView(CatalogoAPIView):
    permission_classes = [LecturaPublicaEscrituraAdmin]

    def get(self, request):
        productos = Producto.objects.filter(activo=True)
        if not IsAdministrador().has_permission(request, self):
            # El público solo ve lo publicado; el admin también ve los borradores (inventario)
            productos = productos.filter(publicado=True)

        # 1. Filtro por categoría en servidor (SCRUM-179, RF-01.3)
        categoria = request.query_params.get('categoria', '').strip()
        if categoria:
            productos = productos.filter(categoria=categoria)

        coleccion = request.query_params.get('coleccion', '').strip()
        if coleccion:
            productos = productos.filter(colecciones__iregex=f"^{re.escape(coleccion)}$")

        # 2. Filtros por atributos globales en servidor (SCRUM-179, RF-01.3 / E02)
        param_reservados = {'page', 'page_size', 'limite', 'categoria','coleccion', 'orden', 'todos', 'sin_paginar', 'format'}
        for clave, valor in request.query_params.items():
            if clave in param_reservados or not valor:
                continue
            nombre_atributo = clave
            if nombre_atributo.startswith('atributo_'):
                nombre_atributo = nombre_atributo[len('atributo_'):]
            elif nombre_atributo.startswith('attr_'):
                nombre_atributo = nombre_atributo[len('attr_'):]

            val_str = str(valor).strip()
            valores_posibles = [val_str]
            # Soportar búsqueda de atributos numéricos (int / float) preservando strings (E02)
            try:
                valores_posibles.append(int(val_str))
            except ValueError:
                pass
            try:
                val_flt = float(val_str)
                if val_flt not in valores_posibles:
                    valores_posibles.append(val_flt)
            except ValueError:
                pass
            if val_str.lower() in ('true', 'false'):
                valores_posibles.append(val_str.lower() == 'true')

            if len(valores_posibles) == 1:
                productos = productos.filter(**{f"atributos_globales__{nombre_atributo}": val_str})
            else:
                productos = productos.filter(**{f"atributos_globales__{nombre_atributo}__in": valores_posibles})

        # La lista completa conserva su formato y orden, pero respeta los filtros.
        sin_paginar = request.query_params.get('todos') == 'true' or request.query_params.get('sin_paginar') == 'true'
        if sin_paginar:
            prods = list(productos)
            versiones_publicadas = obtener_versiones_publicadas(prods)
            serializer = ProductoSerializer(prods, many=True, context={'request': request, 'versiones_publicadas': versiones_publicadas})
            return Response(serializer.data)

        # 3. Paginación y orden en servidor (SCRUM-179)
        config = ConfiguracionGlobal.objects.filter(pk=1).values('orden_catalogo', 'orden_categorias').first() or {}
        orden = request.query_params.get('orden', config.get('orden_catalogo', 'destacados')).strip()
        if orden not in ('destacados', 'recientes', 'precio-asc', 'precio-desc', 'nombre'):
            orden = config.get('orden_catalogo', 'destacados')
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = min(100, max(1, int(request.query_params.get('page_size', request.query_params.get('limite', 24)))))
        except (ValueError, TypeError):
            page_size = 24

        productos_pagina = None
        total_count = None
        total_pages = None

        # Orden por precio con consideración de precio_oferta y múltiples variantes (SCRUM-179 / E01)
        if orden in ('precio-asc', 'precio-desc'):
            sort_dir = 1 if orden == 'precio-asc' else -1
            try:
                query_filter = getattr(productos, '_query', None)
                if isinstance(query_filter, dict):
                    collection = Producto._get_collection()
                    pipeline = [
                        {'$match': query_filter},
                        {
                            '$addFields': {
                                '_precio_efectivo': {
                                    '$min': {
                                        '$map': {
                                            'input': {'$ifNull': ['$variantes', []]},
                                            'as': 'v',
                                            'in': {
                                                '$cond': [
                                                    {
                                                        '$and': [
                                                            {'$ne': ['$$v.precio_oferta', None]},
                                                            {'$gt': ['$$v.precio_oferta', 0]},
                                                            {'$lt': ['$$v.precio_oferta', '$$v.precio']}
                                                        ]
                                                    },
                                                    '$$v.precio_oferta',
                                                    '$$v.precio'
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        {'$sort': {'_precio_efectivo': sort_dir, '_id': 1}},
                        {
                            '$facet': {
                                'total': [{'$count': 'count'}],
                                'results': [
                                    {'$skip': (page - 1) * page_size},
                                    {'$limit': page_size}
                                ]
                            }
                        }
                    ]
                    facet_res = list(collection.aggregate(pipeline))
                    if facet_res and isinstance(facet_res, list):
                        info = facet_res[0]
                        total_count = info['total'][0]['count'] if info.get('total') else 0
                        raw_docs = info.get('results', [])
                        for d in raw_docs:
                            d.pop('_precio_efectivo', None)
                        productos_pagina = [Producto._from_son(d) for d in raw_docs]
                        total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1
            except Exception as exc:
                logger.debug('Fallback de ordenamiento por agregacion de precio: %s', exc)

            if productos_pagina is None:
                try:
                    productos = productos.order_by('precio_minimo_vigente' if orden == 'precio-asc' else '-precio_minimo_vigente', 'id')
                except Exception:
                    try:
                        productos = productos.order_by('variantes.precio' if orden == 'precio-asc' else '-variantes.precio', 'id')
                    except Exception:
                        pass

        elif orden == 'destacados' and config.get('orden_categorias'):
            prioridades = config['orden_categorias']
            pipeline = [
                {'$match': productos._query},
                {'$addFields': {'_orden_categoria': {
                    '$let': {
                        'vars': {'posicion': {'$indexOfArray': [{'$literal': prioridades}, '$categoria']}},
                        'in': {'$cond': [{'$gte': ['$$posicion', 0]}, '$$posicion', len(prioridades)]},
                    },
                }}},
                {'$sort': {'_orden_categoria': 1, 'categoria': 1, 'fecha_creacion': -1, '_id': 1}},
                {'$facet': {
                    'total': [{'$count': 'count'}],
                    'results': [{'$skip': (page - 1) * page_size}, {'$limit': page_size}],
                }},
            ]
            info = next(Producto._get_collection().aggregate(pipeline, allowDiskUse=True))
            total_count = info['total'][0]['count'] if info['total'] else 0
            total_pages = max(1, math.ceil(total_count / page_size))
            for documento in info['results']:
                documento.pop('_orden_categoria', None)
            productos_pagina = [Producto._from_son(documento) for documento in info['results']]
        elif orden == 'recientes':
            productos = productos.order_by('-fecha_creacion', 'id')
        elif orden == 'nombre':
            productos = productos.order_by('nombre', 'id')
        else:
            productos = productos.order_by('-fecha_creacion', 'id')

        if productos_pagina is None:
            total_count = productos.count()
            total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1
            offset = (page - 1) * page_size
            productos_pagina = list(productos[offset:offset + page_size])

        versiones_publicadas = obtener_versiones_publicadas(productos_pagina)
        serializer = ProductoSerializer(productos_pagina, many=True, context={'request': request, 'versiones_publicadas': versiones_publicadas})
        return Response({
            'count': total_count,
            'total_pages': total_pages,
            'current_page': page,
            'page_size': page_size,
            'results': serializer.data,
            'filtros': obtener_filtros_catalogo(config.get('orden_categorias', [])),
            'orden': orden,
        })

    def post(self, request):
        serializer = ProductoSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProductoDetailView(CatalogoAPIView):
    permission_classes = [LecturaPublicaEscrituraAdmin]

    def get(self, request, id):
        producto = self.get_object(id)
        # Un borrador o un producto inactivo no existe para el público (misma respuesta que uno inexistente)
        if not (producto.activo and producto.publicado) and not IsAdministrador().has_permission(request, self):
            raise NotFound('Producto no encontrado.')
        return Response(ProductoSerializer(producto, context={'request': request}).data)

    def put(self, request, id):
        return self.actualizar(request, id, partial=False)

    def patch(self, request, id):
        return self.actualizar(request, id, partial=True)

    def actualizar(self, request, id, partial):
        producto = self.get_object(id)
        serializer = ProductoSerializer(
            producto, data=request.data, partial=partial, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, id):
        eliminar_producto(self.get_object(id))
        return Response(status=status.HTTP_204_NO_CONTENT)


def respuesta_galeria(producto_id, claves, request):
    return {
        'producto_id': str(producto_id),
        'imagenes': [url_imagen(clave, request) for clave in claves],
        'archivos': [
            descriptor_imagen(clave, request) for clave in claves
            if es_imagen_gestionada(clave, producto_id)
        ],
    }


class ProductoImagenListCreateView(CatalogoAPIView):
    permission_classes = [IsAdministrador]
    parser_classes = [MultiPartParser]

    def initialize_request(self, request, *args, **kwargs):
        request.upload_handlers.insert(0, CatalogoImageUploadHandler(request))
        return super().initialize_request(request, *args, **kwargs)

    def get(self, request, id):
        producto = self.get_object(id)
        return Response(respuesta_galeria(producto.id, producto.imagenes, request))

    def post(self, request, id):
        producto = self.get_object(id)
        serializer = GaleriaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if set(request.data) != {'imagenes'}:
            raise ValidationError({'imagenes': 'Usa únicamente el campo multipart imagenes, repetido para cada archivo.'})
        galeria, subidas = servicio_galeria().subir(
            str(producto.id), list(producto.imagenes), serializer.validated_data['imagenes'],
            settings.CATALOGO_IMAGEN_MAX_GALERIA,
        )
        data = respuesta_galeria(producto.id, galeria, request)
        data['subidas'] = [descriptor_imagen(clave, request) for clave in subidas]
        return Response(data, status=status.HTTP_201_CREATED)


class ProductoImagenDetailView(CatalogoAPIView):
    permission_classes = [IsAdministrador]

    def delete(self, request, id, imagen_id):
        producto = self.get_object(id)
        clave = next((clave for clave in producto.imagenes if (
            es_imagen_gestionada(clave, producto.id) and CLAVE_IMAGEN.fullmatch(clave)['id'] == imagen_id
        )), None)
        servicio = servicio_galeria()
        if clave is None:
            # Retrying a detach whose physical deletion failed is idempotent.
            candidatas = [
                f'catalogo/productos/{producto.id}/{imagen_id}.{extension}'
                for extension in ('jpg', 'png', 'webp')
            ]
            pendiente = ImagenPendienteBorrado.objects(clave__in=candidatas).first()
            if pendiente is None:
                raise NotFound('Imagen no encontrada en este producto.')
            servicio.limpiar_pendiente(pendiente.clave)
        else:
            servicio.eliminar(str(producto.id), list(producto.imagenes), clave)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductoEnlaceImagenView(CatalogoAPIView):
    """DELETE ?url=...: quita de la galería una imagen cargada como enlace externo (las subidas usan su id)."""
    permission_classes = [IsAdministrador]

    def delete(self, request, id):
        producto = self.get_object(id)
        url = request.query_params.get('url', '')
        if url not in producto.imagenes or es_imagen_gestionada(url):
            raise NotFound('Enlace no encontrado en este producto.')
        servicio_galeria().quitar_enlace(str(producto.id), list(producto.imagenes), url)
        return Response(status=status.HTTP_204_NO_CONTENT)
