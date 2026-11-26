from rest_framework import generics, status, serializers
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from django.core import signing
from django.shortcuts import redirect
from django.db import transaction
from django.db.models import F, Q, Sum, Count
from django.db import transaction
from django.db.models.functions import TruncDate
from .models import (
    ConfiguracionGlobal, Cotizacion, OrdenCompra, Carrito, DireccionEnvio, EmpresaComprador, FotoCotizacion,
    PaginaLegal, Promocion, Publicacion, ProyectoDestacadoSobreMi, Resena,
)
from .serializers import PromocionSerializer
from rest_framework.permissions import AllowAny

from django.utils import timezone
import logging
import math
import os
import hmac
import hashlib
import json
import base64
from django.http import FileResponse, HttpResponseRedirect, HttpResponse
from dataclasses import asdict
from decimal import Decimal
from math import ceil

from ecommerce.application.couriers import (
    ComunasConCobertura, ConfigurarCourier, CotizarEnvio, CourierNoActivo, TransportistaSegunProveedor,
)
from ecommerce.domain.logistica import (
    ENTREGA_COORDINADA, ENTREGAS_DE_LA_TIENDA, ESTADO_NO_DISPONIBLE, NOMBRES_ENTREGAS_DE_LA_TIENDA, CourierNoDisponible,
    CredencialesInvalidas, ErrorOrdenTransporte, SinCobertura, aviso_entrega_coordinada,
    es_entrega_con_courier, estado_entrega_de_la_tienda,
)
from ecommerce.infrastructure.usuarios.permissions import IsEmprendedor, IsAdministrador
from ecommerce.application.ventas import (
    MOTIVO_PAGO_ANULADO, CambiarEstadoPedido, ConfirmarPago,
    GenerarOrdenTransporte, OrdenNoEncontrada, PedidoModificado, ResolverRevision, ResultadoPago,
    SinRevisionPendiente, RegistrarPagoFueraPlazo, PagoFueraPlazoNoPermitido
)
from ecommerce.application.banner import ActualizarBanners
from ecommerce.application.blog import (
    SIN_CAMBIO, AgregarFotos, BlogDesactivado, EliminarPublicacion, FotoNoEncontrada, GuardarPublicacion,
    PublicacionNoEncontrada, QuitarFoto, VerBlog, VerPublicacion,
)
from ecommerce.application.cotizaciones import (
    CambiarEstadoCotizacion, CotizacionNoEncontrada, FormularioCotizacionDesactivado, SolicitarCotizacion,
)
from ecommerce.application.documentos_tributarios import (
    PedidoNoEncontrado as PedidoParaDocumentarNoEncontrado, RegistrarFolio, SinDocumentoPorRegistrar,
)
from ecommerce.application.dashboard import ETIQUETAS_CAUSA_CANCELACION, ResumenDashboard, TareasPendientes
from ecommerce.application.exportacion_ventas import ExportarVentas
from ecommerce.application.medios_pago import ConfigurarMedioPago
from ecommerce.application.pagos import (
    AplicarResultadoPago, ConciliarPagoOrden, ErrorPasarelaPago, FirmaAvisoInvalida, ProcesarAvisoPago,
)
from ecommerce.application.resenas import (
    EnviarResena, ModerarResena, PedidoNoEncontrado, PrepararFormularioResena, ResenaNoEncontrada,
    ResenasDeLaTienda, ResenasDeProducto, ResenasDesactivadas,
)
from ecommerce.domain.dashboard import PeriodoInvalido, resolver_periodo
from ecommerce.domain.documentos_tributarios import FolioInvalido
from ecommerce.domain.medios_pago import CodigoMedioPago, DatosMedioPagoInvalidos, EstadoPago
from ecommerce.domain.ventas import (
    ESTADOS_CON_ORDEN_TRANSPORTE, ESTADOS_PAGADOS, ErrorPedido, EstadoPedido, OrdenTransporteNoPermitida,
    TransicionNoPermitida,
)
from ecommerce.domain.banner import (EstructuraBannerInvalida, LimiteFotosBannerExcedido, TextosFotoInvalidos,
    LimiteVideosBannerExcedido, VideoBannerInvalido)
from ecommerce.domain.sobre_mi import (
    ProyectosSobreMiInvalidos, SobreMiNoDisponible, construir_contacto_sobre_mi,
    exigir_sobre_mi_disponible, fotos_sobre_mi, muestra_proyectos_sobre_mi, validar_ids_proyectos_sobre_mi,
)
from ecommerce.domain.blog import LimiteFotosExcedido, PublicacionInvalida
from ecommerce.domain.cotizaciones import CotizacionInvalida
from ecommerce.domain.resenas import (
    ModeracionNoPermitida, PedidoNoEntregado, PlazoResenaVencido, ResenaInvalida, ResenaYaEnviada, puede_resenarse,
)
from bson.errors import InvalidId
from mongoengine.errors import ValidationError as MongoValidationError
from ecommerce.infrastructure.catalogo.documents import Producto
from ecommerce.infrastructure.catalogo.repositorio_variantes import (
    MongoInventarioVariantes, MongoNombresProductos, MongoStockCatalogo, fotos_de_variantes,
)
from ecommerce.infrastructure.catalogo.upload_handlers import CatalogoImageUploadHandler

from .models import (
    ConfiguracionGlobal, Cotizacion, OrdenCompra, Carrito, DireccionEnvio, EmpresaComprador, FotoCotizacion,
    FotoBanner, PaginaLegal, Promocion, Publicacion, Resena,
)
from .almacen_privado import almacen_privado
from .permissions import CanCheckout
from .planilla_xlsx import TIPO_XLSX, escribir_xlsx
from .repositorio_dashboard import DjangoMetricasVentas, DjangoPendientesTienda, DjangoVentasPeriodo
from .pasarelas import pasarela
from .serializers import (
    ConfiguracionGlobalSerializer,
    ConfiguracionNegocioSerializer,
    ImagenNegocioField,
    OrdenCompraSerializer,
    RevisionCarritoSerializer,
    DireccionEnvioSerializer,
    EmpresaCompradorSerializer,
    CotizacionSolicitudSerializer,
    AdminCotizacionSerializer,
    AdminResenaSerializer,
    AdminOrdenCompraEstadoSerializer,
    AdminOrdenCompraSerializer,
    PaginaLegalSerializer,
    PaginaLegalDetalleSerializer,
    PaginaLegalAdminSerializer,
    FotosCotizacionSerializer,
    FotosPublicacionSerializer,
    PublicacionAdminSerializer,
    PublicacionDetalleSerializer,
    PublicacionEntradaSerializer,
    PublicacionResumenSerializer,
    MedioPagoAdminSerializer,
    CredencialesCourierSerializer,
    comuna_origen_tienda,
    couriers,
    courier_para_panel,
    medio_pago_para_panel,
    medios_pago,
    mensaje_monto_minimo,
    paquete_del_pedido,
    promociones_automaticas_vigentes,
    regla_de_promocion,
)
from ecommerce.domain.promociones import cumple_minimo, monto_descuento
from .adapters.correo import CorreoNotificadorCotizaciones, CorreoNotificadorPedidos
from .repositorio_cotizaciones import DjangoRepositorioCotizaciones
from .repositorio_documentos import DjangoPedidosDocumentos, filtro_documento_pendiente, modelo_emision_tienda
from .enlaces_resena import orden_del_token, token_resena
from .repositorio_resenas import DjangoPedidosParaResenar, DjangoRepositorioResenas
from .html_seguro import tiene_texto
from .instrucciones_pago import instrucciones_transferencia
from .repositorio_blog import DjangoRepositorioPublicaciones
from .repositorio_banner import DjangoRepositorioBanners
from .couriers import CODIGOS_COURIERS, DjangoRepositorioCredencialesCourier
from .couriers.chilexpress import ChilexpressCourier
from .repositorio_medios_pago import DjangoRepositorioMediosPago
from .repositorio_ordenes import DjangoRepositorioOrdenes
from .servicio_suscripciones import al_pagar_pedido


def inventario_variantes():
    return MongoInventarioVariantes()


def transportista_ordenes():
    """RF-02.3: la OT la genera el courier que eligió el comprador (las pruebas lo reemplazan)."""
    return TransportistaSegunProveedor(couriers())


def generar_orden_transporte():
    return GenerarOrdenTransporte(DjangoRepositorioOrdenes(), transportista_ordenes())


# Firma de los primeros bytes de la etiqueta → su tipo y extensión
FORMATOS_ETIQUETA = (
    (b'%PDF', 'application/pdf', 'pdf'),
    (b'\xff\xd8\xff', 'image/jpeg', 'jpg'),
    (b'\x89PNG', 'image/png', 'png'),
)


def consultar_estado_envio(proveedor, codigo_seguimiento):
    """RF-02.4: el estado del envío en la línea de tiempo estándar, según su courier."""
    try:
        return couriers().obtener(proveedor).consultar_estado(codigo_seguimiento)
    except CourierNoActivo:
        return ESTADO_NO_DISPONIBLE


def notificador_pedidos():
    return CorreoNotificadorPedidos()


def solicitar_cotizacion():
    return SolicitarCotizacion(DjangoRepositorioCotizaciones(), CorreoNotificadorCotizaciones(), MongoNombresProductos())


def confirmar_pago():
    # Si el pedido es el de un ciclo de una suscripción, al pagarse la suscripción avanza (al_pagar_pedido)
    return ConfirmarPago(DjangoRepositorioOrdenes(), inventario_variantes(), generar_orden_transporte(),
                         notificador_pedidos(), al_pagar_pedido)

def pasarela_mercado_pago():
    return pasarela(CodigoMedioPago.MERCADO_PAGO)


def pasarela_transbank():
    return pasarela(CodigoMedioPago.TRANSBANK)


def aplicar_resultado_pago():
    return AplicarResultadoPago(confirmar_pago())


def sincronizar_orden_con_mercadopago(orden):
    """Pone al día una orden PENDIENTE de Mercado Pago con sus intentos de pago (ver ConciliarPagoOrden)."""
    if not orden or orden.estado != EstadoPedido.PENDIENTE or (orden.metodo_pago or '').upper() != 'MERCADO_PAGO':
        return getattr(orden, 'estado', None)

    adapter = pasarela_mercado_pago()
    if not adapter.access_token:
        return orden.estado

    try:
        resultado = ConciliarPagoOrden(adapter, aplicar_resultado_pago()).ejecutar(orden.id)
        if resultado != ResultadoPago.PENDIENTE:
            orden.refresh_from_db()
    except Exception as exc:
        logger.warning(f"Error sincronizando orden {orden.id} con Mercado Pago: {exc}")

    return getattr(orden, 'estado', None)


def cambiar_estado_pedido():
    return CambiarEstadoPedido(DjangoRepositorioOrdenes(), inventario_variantes(), generar_orden_transporte(),
                               notificador_pedidos(), al_pagar_pedido)


class PaginacionPedidos(PageNumberPagination):
    """De a 20 con ?pagina=N, como las cotizaciones y las reseñas: responde { count, next, previous, results }."""
    page_size = 20
    page_query_param = 'pagina'


class AdminOrdenCompraListView(generics.ListAPIView):
    """GET ?estado=PAGADO&requiere_revision=true&documento=pendiente&orden_transporte=error&pagina=N: los pedidos del
    panel, los más recientes primero. documento=pendiente deja los que tienen boleta, factura o nota de crédito por
    emitir; orden_transporte=error, los que esperan su orden de transporte y fallaron al generarla."""
    serializer_class = AdminOrdenCompraSerializer
    permission_classes = [IsAdministrador]
    pagination_class = PaginacionPedidos

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.modelo_emision = modelo_emision_tienda()

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'modelo_emision': self.modelo_emision}

    def get_queryset(self):
        ordenes = OrdenCompra.objects.order_by('-fecha_creacion')
        estado = self.request.query_params.get('estado')
        if estado:
            ordenes = ordenes.filter(estado=estado)
        if self.request.query_params.get('requiere_revision') == 'true':
            ordenes = ordenes.filter(requiere_revision=True)
        if self.request.query_params.get('documento') == 'pendiente':
            ordenes = ordenes.filter(filtro_documento_pendiente(self.modelo_emision))
        if self.request.query_params.get('orden_transporte') == 'error':
            ordenes = ordenes.filter(estado__in=[e.value for e in ESTADOS_CON_ORDEN_TRANSPORTE]).exclude(
                error_orden_transporte='')
        return ordenes


class AdminDocumentoOrdenView(APIView):
    """POST admin/ordenes/<pk>/documento/ { folio }: anota (o corrige) el folio de la boleta o factura que la
    tienda emitió por su cuenta o, en un pedido cancelado, el de su nota de crédito. Responde el pedido."""
    permission_classes = [IsAdministrador]

    def post(self, request, pk):
        modelo = modelo_emision_tienda()
        try:
            RegistrarFolio(DjangoPedidosDocumentos()).ejecutar(pk, request.data.get('folio'), modelo)
        except PedidoParaDocumentarNoEncontrado as error:
            return Response({'detail': str(error)}, status=status.HTTP_404_NOT_FOUND)
        except (FolioInvalido, SinDocumentoPorRegistrar) as error:
            return Response({'folio': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        orden = OrdenCompra.objects.get(id=pk)
        return Response(AdminOrdenCompraSerializer(orden, context={'request': request, 'modelo_emision': modelo}).data)


class AdminSincronizarPagosView(APIView):
    """
    Sincronización bajo demanda para el administrador.
    Realiza una única llamada optimizada a la API de Mercado Pago (/v1/payments/search)
    para buscar los pagos recientes y conciliar órdenes pendientes sin demorar la navegación normal.
    """
    permission_classes = [IsAdministrador]

    def post(self, request):
        adapter = pasarela_mercado_pago()
        if not adapter.access_token:
            return Response({"error": "Mercado Pago no está configurado."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            try:
                pagos = adapter.pagos_recientes(30)
            except ErrorPasarelaPago as exc:
                return Response({"error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

            caso = aplicar_resultado_pago()
            actualizadas = 0

            # Solo los resultados definitivos de órdenes pendientes de Mercado Pago
            for pago in pagos:
                if pago.estado not in (EstadoPago.APROBADO, EstadoPago.RECHAZADO) or not pago.orden_id.isdigit():
                    continue
                orden = OrdenCompra.objects.filter(id=int(pago.orden_id), estado=EstadoPedido.PENDIENTE).first()
                if orden and orden.metodo_pago == 'MERCADO_PAGO':
                    caso.ejecutar(pago)
                    actualizadas += 1

            return Response({
                "mensaje": f"Sincronización completada. Se revisaron {len(pagos)} pagos recientes y se actualizaron {actualizadas} órdenes.",
                "ordenes_actualizadas": actualizadas
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Error en sincronización batch de Mercado Pago")
            return Response({"error": f"Error de sincronización: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdminResolverRevisionView(APIView):
    """El admin marca como resuelta la revisión de una orden."""
    permission_classes = [IsAdministrador]

    def post(self, request, pk):
        try:
            ResolverRevision(DjangoRepositorioOrdenes()).ejecutar(pk)
        except OrdenNoEncontrada:
            return Response({'detail': 'Orden no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except SinRevisionPendiente as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
        return Response({'id': pk, 'requiere_revision': False})

class AdminRegistrarPagoFueraPlazoView(APIView):
    """Registra un pago recibido después de cancelar la orden por vencimiento."""
    permission_classes = [IsAdministrador]

    def post(self, request, pk):
        try:
            RegistrarPagoFueraPlazo(DjangoRepositorioOrdenes()).ejecutar(pk)
        except OrdenNoEncontrada:
            return Response(
                {'detail': 'Orden no encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except PagoFueraPlazoNoPermitido as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({
            'id': pk,
            'estado': 'CANCELADO',
            'requiere_revision': True,
            'motivo_revision': RegistrarPagoFueraPlazo.MOTIVO_REVISION,
        })

class AdminOrdenTransporteView(APIView):
    """RF-02.3: el admin genera o reintenta la orden de transporte de un pedido pagado."""
    permission_classes = [IsAdministrador]

    def post(self, request, pk):
        try:
            numero_ot = generar_orden_transporte().reintentar(pk)
        except OrdenNoEncontrada:
            return Response({'detail': 'Orden no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except OrdenTransporteNoPermitida as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)
        except ErrorOrdenTransporte as error:
            # El transportista falló: el error ya quedó guardado en la orden
            return Response({'detail': str(error)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({'id': pk, 'numero_seguimiento_tracking': numero_ot})


class AdminOrdenCompraPatchView(APIView):
    """RF-03.3: cambio de estado manual del admin (solo las transiciones permitidas)."""
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        serializer = AdminOrdenCompraEstadoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            estado = cambiar_estado_pedido().ejecutar(pk, serializer.validated_data['estado'])
        except OrdenNoEncontrada:
            return Response({'detail': 'Orden no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        except TransicionNoPermitida as error:
            return Response({'estado': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        except PedidoModificado as error:
            return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)

        orden = OrdenCompra.objects.get(id=pk)
        return Response({
            'id': orden.id,
            'estado': estado.value,
            'requiere_revision': orden.requiere_revision,
            'motivo_revision': orden.motivo_revision,
        })


logger = logging.getLogger(__name__)


class CarritoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        carrito, created = Carrito.objects.get_or_create(usuario=request.user)
        return Response({"items": carrito.items})

    def post(self, request):
        carrito, created = Carrito.objects.get_or_create(usuario=request.user)
        items = request.data.get('items', [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            return Response({'items': ['Envía una lista de productos.']}, status=status.HTTP_400_BAD_REQUEST)
        from .acceso_exclusivos import exigir_acceso_productos
        exigir_acceso_productos(items, request.user)
        for item in items:
            p_id = item.get('producto_mongo_id') or item.get('producto_id') or item.get('id')
            if p_id:
                try:
                    p = Producto.objects(id=p_id).only('coleccion_privada').first()
                except (MongoValidationError, InvalidId):
                    p = None
                if p and getattr(p, 'coleccion_privada', False):
                    return Response(
                        {"items": ["No se pueden agregar productos de colección privada al carrito."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
        carrito.items = items
        carrito.save()
        return Response({"items": carrito.items})


class ValidarCarritoView(APIView):
    """RN-03: compara el carrito (también el de invitados, que vive en el navegador) con el stock vigente."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RevisionCarritoSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.revisar())


class CheckoutAPIView(generics.CreateAPIView):
    queryset = OrdenCompra.objects.all()
    serializer_class = OrdenCompraSerializer
    permission_classes = [CanCheckout]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        orden = serializer.instance
        # El detalle de la orden lo guarda el serializer con los precios del catálogo

        try:
            # Respuesta hacia React
            respuesta_data = serializer.data
            respuesta_data['mensaje'] = "Orden creada con éxito."
            respuesta_data['orden_id'] = orden.id
            respuesta_data['token_verificacion'] = token_verificacion_pago(orden.id)

            # Si el serializer generó una URL de Transbank, la inyectamos en la respuesta
            if hasattr(orden, 'url_pago') and orden.url_pago:
                respuesta_data['url_pago'] = orden.url_pago
                respuesta_data['mensaje'] = "Orden creada. Redirigiendo al pago..."

            # Transferencia: el comprador ve a qué cuenta transferir en /pedido-recibido
            instrucciones = instrucciones_transferencia(orden)
            if instrucciones:
                respuesta_data['instrucciones_pago'] = instrucciones

            headers = self.get_success_headers(serializer.data)
            return Response(respuesta_data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Exception as e:
            return Response(
                {"error": f"Error al generar pago con la pasarela: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class TransbankRetornoView(APIView):
    permission_classes = [AllowAny]  # Permite acceso público desde la redirección externa de Webpay

    def get(self, request):
        # Transbank envía 'token_ws' en pagos normales, o 'TBK_TOKEN' y 'TBK_ORDEN_COMPRA' si el usuario anula
        token = request.GET.get('token_ws') or request.POST.get('token_ws')
        tbk_token = request.GET.get('TBK_TOKEN')
        tbk_orden = request.GET.get('TBK_ORDEN_COMPRA')

        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

        # Anulación del comprador en el portal de Transbank
        if tbk_token and not token:
            orden_id_limpio = (tbk_orden or '').replace('ORD-', '')
            if confirmar_pago().rechazar(orden_id_limpio, MOTIVO_PAGO_ANULADO):
                logger.info(f"Orden {orden_id_limpio} cancelada por anulación en Transbank.")
            else:
                orden_id_limpio = ''
            # Página pública: el invitado no tiene acceso a /mis-pedidos
            destino = f"{frontend_url}/pago-cancelado"
            return HttpResponseRedirect(f"{destino}?orden={orden_id_limpio}" if orden_id_limpio else destino)

        if not token:
            return Response({"error": "Token no proporcionado"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Confirmar transacción con Transbank
        try:
            pago = pasarela_transbank().resultado(token)
        except ErrorPasarelaPago:
            return Response({"error": "Error al comunicar con Transbank"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            orden = OrdenCompra.objects.get(id=pago.orden_id)
        except (OrdenCompra.DoesNotExist, ValueError):
            return Response({"error": "Orden no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        caso = aplicar_resultado_pago()
        if pago.estado != EstadoPago.APROBADO:
            caso.ejecutar(pago)
            return HttpResponseRedirect(f"{frontend_url}/pago-rechazado?orden={orden.id}")

        # 2. Estado y stock de la orden (idempotente, stock todo o nada)
        try:
            resultado = caso.ejecutar(pago)
        except Exception:
            # El pago ya está aprobado: la orden quedó marcada para revisión del admin
            logger.exception(f"Error al descontar stock de la orden {orden.id}")
            resultado = ResultadoPago.EN_REVISION

        orden.refresh_from_db()
        if resultado == ResultadoPago.EN_REVISION:
            logger.error(f"La orden {orden.id} requiere revisión del admin: {orden.motivo_revision}")
        elif resultado == ResultadoPago.REPETIDO:
            logger.info(f"Confirmación repetida de la orden {orden.id}; se omite.")
        elif resultado == ResultadoPago.PAGADO and orden.error_orden_transporte:
            # El pago queda firme; el error queda guardado en la orden
            logger.error(f"No se generó la OT de la orden {orden.id}: {orden.error_orden_transporte}")

        # El comprador sabe que su pago llegó, pero no se le promete un pedido que el admin debe revisar
        revision = '&revision=1' if orden.requiere_revision else ''
        return HttpResponseRedirect(f"{frontend_url}/pago-exitoso?orden={orden.id}{revision}")

class MercadoPagoWebhookView(APIView):
    """Recibe las notificaciones webhook de Mercado Pago y delega en el caso de uso."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        x_signature = request.headers.get('x-signature', '')
        x_request_id = request.headers.get('x-request-id', '')

        data_id = (
            request.query_params.get('data.id')
            or request.query_params.get('id')
            or (request.data.get('data', {}) if isinstance(request.data, dict) else {}).get('id')
            or (request.data.get('id') if isinstance(request.data, dict) else '')
            or ''
        )
        topic = (
            request.query_params.get('type')
            or request.query_params.get('topic')
            or (request.data.get('type') if isinstance(request.data, dict) else None)
            or (request.data.get('topic') if isinstance(request.data, dict) else None)
            or 'payment'
        )

        caso = ProcesarAvisoPago(pasarela_mercado_pago(), aplicar_resultado_pago())
        try:
            resultado = caso.ejecutar(
                firma=x_signature,
                id_peticion=x_request_id,
                referencia=str(data_id),
                es_pago=str(topic) in ('payment', 'payment.created', 'payment.updated'),
            )
        except FirmaAvisoInvalida:
            return Response({"detail": "Firma inválida."}, status=status.HTTP_401_UNAUTHORIZED)
        except ErrorPasarelaPago as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"status": str(resultado)}, status=status.HTTP_200_OK)


class MercadoPagoRetornoView(APIView):
    """
    Redirige al comprador al volver de Mercado Pago (/pago-exitoso, /pago-rechazado o /pago-cancelado).
    Principio Zero-Trust: los parámetros de retorno de la URL nunca modifican el estado de la orden por sí solos.
    Si se proporciona un payment_id, se consulta siempre a la API de Mercado Pago para verificar el estado real y
    la coincidencia de la orden antes de aplicar cualquier aprobación, rechazo o anulación.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        orden_id = (
            request.GET.get('external_reference')
            or request.GET.get('orden')
            or ''
        ).replace('ORD-', '').strip()
        payment_id = request.GET.get('payment_id') or request.GET.get('collection_id') or ''

        orden = OrdenCompra.objects.filter(id=orden_id).first() if orden_id.isdigit() else None

        # 1. Si la orden ya está pagada (ej. el webhook llegó antes que el retorno del navegador):
        if orden and orden.estado in ESTADOS_PAGADOS:
            revision = '&revision=1' if orden.requiere_revision else ''
            return HttpResponseRedirect(f"{frontend_url}/pago-exitoso?orden={orden.id}{revision}")

        # 2. Si viene payment_id: SIEMPRE consultar a Mercado Pago (nunca confiar en query params de la URL)
        if payment_id:
            try:
                pago = pasarela_mercado_pago().resultado(payment_id)
            except Exception as exc:
                logger.error("Error consultando pago %s de Mercado Pago en retorno: %s", payment_id, exc)
                if orden:
                    orden.refresh_from_db()
                    if orden.estado in ESTADOS_PAGADOS:
                        revision = '&revision=1' if orden.requiere_revision else ''
                        return HttpResponseRedirect(f"{frontend_url}/pago-exitoso?orden={orden.id}{revision}")
                # Seguridad: NUNCA alterar la orden en BD ante fallos de consulta externa
                sufijo = f"?orden={orden_id}" if orden_id else ""
                return HttpResponseRedirect(f"{frontend_url}/pago-cancelado{sufijo}")

            # Validar pertenencia estricta del pago a la orden (anti-hijacking y Zero-Trust):
            # Un pago sin external_reference (vacía o nula) o con referencia a otra orden NO debe
            # aprobar, rechazar ni cancelar la orden indicada en la URL.
            pago_orden_id = str(pago.orden_id or "").strip()
            if not pago_orden_id:
                logger.warning(
                    "Pago %s de Mercado Pago no tiene external_reference válida; no se puede asociar a la orden %s",
                    payment_id, orden_id
                )
                return HttpResponseRedirect(f"{frontend_url}/pago-cancelado")

            if orden_id and str(pago_orden_id) != str(orden_id):
                logger.warning(
                    "Discrepancia de orden en retorno de Mercado Pago: URL=%s vs MP=%s",
                    orden_id, pago_orden_id
                )
                return HttpResponseRedirect(f"{frontend_url}/pago-cancelado")

            orden_id = pago_orden_id
            if orden is None and orden_id.isdigit():
                orden = OrdenCompra.objects.filter(id=int(orden_id)).first()

            if not orden:
                logger.warning("Orden %s asociada al pago %s no existe", orden_id, payment_id)
                return HttpResponseRedirect(f"{frontend_url}/pago-cancelado")

            caso = aplicar_resultado_pago()
            if pago.estado == EstadoPago.APROBADO:
                try:
                    caso.ejecutar(pago)
                except Exception:
                    logger.exception("Error al descontar stock de la orden %s", orden.id)
                orden.refresh_from_db()
                revision = '&revision=1' if orden.requiere_revision else ''
                return HttpResponseRedirect(f"{frontend_url}/pago-exitoso?orden={orden.id}{revision}")

            resultado = caso.ejecutar(pago)
            if resultado == ResultadoPago.RECHAZADO:
                return HttpResponseRedirect(f"{frontend_url}/pago-rechazado?orden={orden.id}")
            if resultado == ResultadoPago.PENDIENTE:
                return HttpResponseRedirect(f"{frontend_url}/pedido-recibido?orden={orden_id}")
            # Anulado o devuelto antes de que la orden se pagara
            return HttpResponseRedirect(f"{frontend_url}/pago-cancelado?orden={orden.id}")

        # 3. Si NO hay payment_id (ej. el comprador abandonó el flujo en la pasarela o canceló):
        # Los parámetros de retorno de la URL por sí solos NUNCA deben cancelar la orden en la BD.
        # Se redirige legítimamente al usuario a /pago-cancelado para que pueda reintentar o cambiar de medio.
        sufijo = f"?orden={orden_id}" if orden_id else ""
        return HttpResponseRedirect(f"{frontend_url}/pago-cancelado{sufijo}")


SAL_VERIFICAR_PAGO = 'ventas.verificar-pago'


def token_verificacion_pago(orden_id) -> str:
    """Lo recibe quien crea la orden: sin él no se puede consultar su pago (los IDs son correlativos)."""
    return signing.dumps(str(orden_id), salt=SAL_VERIFICAR_PAGO)


def token_verificacion_valido(token, orden_id) -> bool:
    try:
        return signing.loads(token, salt=SAL_VERIFICAR_PAGO) == str(orden_id)
    except signing.BadSignature:
        return False


class VerificarEstadoPagoView(APIView):
    """
    Consulta y sincroniza el estado de una orden.
    Permite al frontend chequear el pago de Mercado Pago (polling/verificación)
    para vaciar el carrito y redirigir a /pago-exitoso tan pronto como el pago se acredite.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        orden_id = request.query_params.get('orden_id') or request.query_params.get('orden')
        if not orden_id or not str(orden_id).isdigit():
            return Response({"error": "ID de orden no proporcionado o inválido."}, status=status.HTTP_400_BAD_REQUEST)

        # Sin el token de la orden se responde igual que si no existiera, y no se consulta a Mercado Pago
        if not token_verificacion_valido(request.query_params.get('token', ''), orden_id):
            return Response({"error": "Orden no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        orden = OrdenCompra.objects.filter(id=int(orden_id)).first()
        if not orden:
            return Response({"error": "Orden no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if orden.estado == EstadoPedido.PENDIENTE and (orden.metodo_pago or '').upper() == 'MERCADO_PAGO':
            sincronizar_orden_con_mercadopago(orden)
            orden.refresh_from_db()

        return Response({
            "orden_id": orden.id,
            "estado": orden.estado,
            "pagado": orden.estado in ESTADOS_PAGADOS,
            "cancelado": orden.estado == EstadoPedido.CANCELADO,
            "requiere_revision": orden.requiere_revision,
        }, status=status.HTTP_200_OK)


class CotizacionEnvioView(APIView):
    """POST {destino, items, proveedor?}: el costo del envío por courier que ve el comprador (RF-02.3).

    Es la misma cotización que cobra el checkout: el paquete lo arma el servidor con las medidas del catálogo y el
    origen es la comuna de la tienda. Peso, medidas u origen enviados por el navegador se ignoran.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        destino = request.data.get('destino')
        if not destino:
            return Response(
                {"error": "El código de comuna de destino es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Los mismos productos que el carrito: hasta 100 líneas con su cantidad
        entrada = RevisionCarritoSerializer(data=request.data)
        if not entrada.is_valid():
            return Response({"error": "Indica los productos del carrito que se van a enviar."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            paquete = paquete_del_pedido(entrada.validated_data['items'])
        except ErrorPedido as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        # Con un proveedor cotiza ese; sin él, todos los couriers activos (el comprador elige)
        proveedor = request.data.get('proveedor') or None

        # Comuna sin cobertura → 400; courier caído o tarifa inválida → 503
        try:
            opciones = CotizarEnvio(couriers()).ejecutar(comuna_origen_tienda(), destino, paquete, proveedor)
        except CourierNoActivo:
            return Response({"error": "No hay envío por courier disponible en esta tienda."},
                            status=status.HTTP_400_BAD_REQUEST)
        except SinCobertura as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except CourierNoDisponible as error:
            return Response({"error": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({"opciones": [{**asdict(opcion), "moneda": "CLP"} for opcion in opciones]},
                        status=status.HTTP_200_OK)


class ConfiguracionGlobalAPIView(generics.RetrieveAPIView):
    serializer_class = ConfiguracionGlobalSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_object(self):
        configuracion = ConfiguracionGlobal.objects.prefetch_related('fotos_banner').filter(id=1).first()
        if configuracion is None:
            raise NotFound('No existe una configuración de tienda.')
        return configuracion


class ConfiguracionNegocioView(APIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    # Solo el administrador de la tienda puede ver y modificar la configuración
    permission_classes = [IsEmprendedor]

    def get_object(self):
        obj = ConfiguracionGlobal.objects.prefetch_related('fotos_banner').filter(id=1).first()
        if obj is None:
            obj, _ = ConfiguracionGlobal.objects.get_or_create(id=1)
        return obj

    def get(self, request):
        config = self.get_object()
        # Con la request, las imágenes salen con URL absoluta (el panel corre en otro puerto u origen)
        serializer = ConfiguracionNegocioSerializer(config, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        config = self.get_object()
        serializer = ConfiguracionNegocioSerializer(config, data=request.data, partial=True,
                                                    context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                serializer.save()
                if 'banner_orden' in request.data:
                    ActualizarBanners(DjangoRepositorioBanners()).ejecutar(
                        config.id,
                        request.data.get('banner_orden'),
                        request.FILES.getlist('banner_fotos'),
                        request.FILES.getlist('banner_videos')
                    )
        except (EstructuraBannerInvalida, TextosFotoInvalidos) as exc:
            return Response({'banner_orden': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except LimiteFotosBannerExcedido as exc:
            return Response({'banner_fotos': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except (LimiteVideosBannerExcedido, VideoBannerInvalido) as exc:
            return Response({'banner_videos': [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)

        config = self.get_object()
        respuesta = ConfiguracionNegocioSerializer(config, context={'request': request})
        return Response(respuesta.data, status=status.HTTP_200_OK)

    def patch(self, request):
        return self.put(request)


class DashboardOperativoView(APIView):
    permission_classes = [IsEmprendedor]

    def get(self, request):
        emprendedor_id = str(request.user.pk)
        return Response({
            "mensaje": "bienvenido al panel de Control",
            "emprendedor_id": emprendedor_id
        })


class ReglasCheckoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        configuracion = ConfiguracionGlobal.objects.filter(id=1).first()
        modo = configuracion.modo_autenticacion if configuracion and configuracion.modo_autenticacion else 'INVITADO'
        
        return Response({
            "modo_autenticacion": modo
        }, status=status.HTTP_200_OK)


def instrucciones_entrega_de_la_tienda(proveedor):
    """Cómo recibe el comprador un pedido que entrega la propia tienda (se muestra en el seguimiento)."""
    config = ConfiguracionGlobal.objects.filter(pk=1).first()
    if proveedor == ENTREGA_COORDINADA:
        return aviso_entrega_coordinada(config.instrucciones_entrega_coordinada if config else '')
    partes = [config.calle_origen, config.numero_origen, config.comuna_origen] if config else []
    direccion = ' '.join(str(parte) for parte in partes if parte)
    return (f'Retíralo en {direccion} presentando tu número de orden.' if direccion
            else 'Retíralo en el local presentando tu número de orden.')


class SeguimientoEnvioView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        numero_orden = request.data.get('numero_orden')
        email = str(request.data.get('email') or '').strip()

        if not numero_orden or not email:
            return Response(
                {"error": "El número de orden y el correo son obligatorios para consultar el seguimiento."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            orden = OrdenCompra.objects.get(
                # El correo sin distinguir mayúsculas: el comprador no recuerda cómo lo escribió
                Q(id=numero_orden) & (Q(email_invitado__iexact=email) | Q(usuario__email__iexact=email))
            )
        # Un número de orden no numérico recibe la misma respuesta genérica (RF-02.4)
        except (OrdenCompra.DoesNotExist, ValueError):
            return Response(
                {"error": "No se encontró un pedido que coincida con esos datos. Verifica la información."},
                status=status.HTTP_404_NOT_FOUND
            )

        if orden.proveedor_logistico in ENTREGAS_DE_LA_TIENDA:
            # Retiro o entrega coordinada: no hay courier ni código; el avance es el estado del pedido
            return Response({
                "numero_orden": orden.id,
                "entrega_de_la_tienda": True,
                "proveedor": NOMBRES_ENTREGAS_DE_LA_TIENDA[orden.proveedor_logistico],
                "estado_actual": estado_entrega_de_la_tienda(orden.proveedor_logistico, orden.estado),
                "instrucciones": instrucciones_entrega_de_la_tienda(orden.proveedor_logistico),
                "linea_tiempo_estandar": [],
                "codigo_seguimiento": None,
            }, status=status.HTTP_200_OK)

        # Los pedidos anteriores a guardar el courier se enviaban con Chilexpress
        proveedor = orden.proveedor_logistico or ChilexpressCourier.codigo
        codigo = orden.numero_seguimiento_tracking
        # Los estados finales tienen prioridad sobre el tipo de entrega
        if orden.estado == 'CANCELADO':
            estado_estandarizado = 'Cancelado'
        elif orden.estado == 'ENTREGADO':
            estado_estandarizado = 'Entregado'
        elif not codigo or not codigo.strip():
            estado_estandarizado = 'Pendiente de despacho'
        else:
            estado_estandarizado = consultar_estado_envio(proveedor, codigo)

        linea_tiempo = [
            'En origen',
            'En tránsito',
            'En reparto',
            'Entregado',
        ]

        return Response({
            "numero_orden": orden.id,
            "estado_actual": estado_estandarizado,
            "linea_tiempo_estandar": linea_tiempo,
            "proveedor": proveedor,
            "codigo_seguimiento": codigo or '',
        }, status=status.HTTP_200_OK)


class HistorialPedidosAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ordenes = list(OrdenCompra.objects.filter(usuario=request.user).order_by('-fecha_creacion')
                       .prefetch_related('detalles'))
        # La foto de cada producto comprado, tal como está hoy en el catálogo (una consulta para todos los pedidos)
        fotos = fotos_de_variantes({(d.producto_mongo_id, d.variante_sku) for orden in ordenes
                                    for d in orden.detalles.all()}, request)
        # "Dejar reseña": el mismo enlace firmado del correo, solo para el dueño del pedido
        con_resenas = resenas_activas()
        resenados = set(Resena.objects.filter(orden__usuario=request.user).values_list('orden_id', flat=True))
        ahora = timezone.now()
        data = []
        for orden in ordenes:
            detalles = [{
                "producto_mongo_id": d.producto_mongo_id,
                "variante_sku": d.variante_sku,
                "nombre_producto": d.nombre_producto_snapshot,
                "precio_unitario": d.precio_unitario_snapshot,
                "cantidad": d.cantidad,
                **fotos.get((d.producto_mongo_id, d.variante_sku), {'imagen': None, 'variante': ''}),
            } for d in orden.detalles.all()]

            data.append({
                "id": orden.id,
                "fecha": orden.fecha_creacion,
                "estado": orden.estado,
                "metodo_pago": orden.metodo_pago,
                "subtotal": orden.subtotal,
                "costo_envio": orden.costo_envio,
                "total_final": orden.total_final,
                "direccion": orden.direccion_envio_snapshot,
                "detalles": detalles,
                # --- AGREGAR ESTAS DOS LÍNEAS ---
                "id_transaccion_pasarela": orden.id_transaccion_pasarela,
                "proveedor_logistico": orden.proveedor_logistico,
                "token_resena": token_resena(orden.id) if con_resenas and puede_resenarse(
                    orden.estado, orden.fecha_entrega, orden.id in resenados, ahora) else None,
                "resena_enviada": orden.id in resenados,
            })
            
        return Response(data, status=status.HTTP_200_OK)

class ComunasCoberturaAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        # Las comunas que atiende al menos un courier activo
        try:
            comunas = ComunasConCobertura(couriers()).ejecutar()
        except CourierNoActivo:
            return Response({"error": "No hay envío por courier disponible en esta tienda."},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except CourierNoDisponible as error:
            return Response({"error": str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"comunas": comunas}, status=status.HTTP_200_OK)

class DireccionEnvioListCreateView(generics.ListCreateAPIView):
    """
    GET: Lista todas las direcciones del usuario autenticado.
    POST: Crea una nueva dirección para el usuario autenticado.
    """
    serializer_class = DireccionEnvioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Retorna solo las direcciones del usuario actual, ordenadas por principal primero
        return DireccionEnvio.objects.filter(usuario=self.request.user).order_by('-es_predeterminado', '-id')

    def perform_create(self, serializer):
        # Asigna automáticamente el usuario autenticado al crear la dirección
        serializer.save(usuario=self.request.user)

class DireccionEnvioDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Obtiene una dirección específica.
    PUT/PATCH: Actualiza una dirección específica (ej. hacerla principal).
    DELETE: Elimina una dirección.
    """
    serializer_class = DireccionEnvioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Seguridad: Un usuario solo puede ver/editar/eliminar SUS propias direcciones
        return DireccionEnvio.objects.filter(usuario=self.request.user)

class EmpresaCompradorView(APIView):
    """GET: los datos de empresa que el comprador guardó en una compra anterior (204 si no hay).

    Se guardan desde el checkout, cuando marca "Guardar para mis próximas compras".
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        empresa = EmpresaComprador.objects.filter(usuario=request.user).first()
        if empresa is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(EmpresaCompradorSerializer(empresa).data)


MENSAJE_COTIZACION_RECIBIDA = 'Recibimos tu solicitud. Te enviamos una copia a tu correo y la tienda te contactará pronto.'


class CotizacionThrottle(SimpleRateThrottle):
    """Contra el spam: pocas solicitudes por hora desde la misma IP (DEFAULT_THROTTLE_RATES['cotizaciones'])."""
    scope = 'cotizaciones'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class CotizacionCreateView(APIView):
    """POST /api/ventas/cotizaciones/: el formulario público de cotización y encargos."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [CotizacionThrottle]

    def post(self, request):
        # Con fotos llega como multipart: los datos van como JSON en "datos" y las fotos en "fotos"
        con_archivos = (request.content_type or '').startswith('multipart/')
        if con_archivos:
            try:
                entrada = json.loads(request.data.get('datos') or '{}')
            except ValueError:
                entrada = None
            if not isinstance(entrada, dict):
                return Response({'detail': 'Los datos de la cotización no tienen un formato válido.'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            entrada = request.data
        serializer = CotizacionSolicitudSerializer(data=entrada)
        serializer.is_valid(raise_exception=True)
        datos = dict(serializer.validated_data)
        if datos.pop('sitio_web', ''):
            # Campo trampa lleno: lo envió un bot. Se responde como si nada para no darle pistas
            return Response({'mensaje': MENSAJE_COTIZACION_RECIBIDA}, status=status.HTTP_201_CREATED)
        fotos = FotosCotizacionSerializer(data={'fotos': request.FILES.getlist('fotos') if con_archivos else []})
        fotos.is_valid(raise_exception=True)
        config = ConfiguracionGlobal.objects.filter(pk=1).first()
        try:
            solicitar_cotizacion().ejecutar(datos, formulario_activo=bool(config and config.cotizaciones_activas),
                                            hoy=timezone.localdate(), fotos=fotos.validated_data.get('fotos', []))
        except FormularioCotizacionDesactivado as error:
            return Response({'detail': str(error)}, status=status.HTTP_403_FORBIDDEN)
        except CotizacionInvalida as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)
        return Response({'mensaje': MENSAJE_COTIZACION_RECIBIDA}, status=status.HTTP_201_CREATED)


class PaginacionCotizaciones(PageNumberPagination):
    """De a 20 con ?pagina=N: responde { count, next, previous, results }."""
    page_size = 20
    page_query_param = 'pagina'


class AdminCotizacionListView(generics.ListAPIView):
    """Las solicitudes de cotización, de la más reciente a la más antigua, paginadas."""
    serializer_class = AdminCotizacionSerializer
    permission_classes = [IsAdministrador]
    pagination_class = PaginacionCotizaciones
    queryset = Cotizacion.objects.prefetch_related('fotos')


# Las fotos se guardan con la extensión del formato que detectó ArchivoImagenField
TIPOS_FOTO = {'.jpg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}


class AdminFotoCotizacionView(APIView):
    """GET admin/cotizaciones/<id>/fotos/<foto>/: una foto que adjuntó el cliente. Solo el admin, con su sesión:
    el archivo no está en media (que se publica) sino en ARCHIVOS_PRIVADOS_ROOT."""
    permission_classes = [IsAdministrador]

    def get(self, request, pk, foto_id):
        foto = FotoCotizacion.objects.filter(id=foto_id, cotizacion_id=pk).first()
        extension = os.path.splitext(foto.ruta)[1].lower() if foto else ''
        almacen = almacen_privado()
        if foto is None or extension not in TIPOS_FOTO or not almacen.exists(foto.ruta):
            return Response({'detail': 'Foto no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        respuesta = FileResponse(almacen.open(foto.ruta, 'rb'), content_type=TIPOS_FOTO[extension])
        # Una imagen y nada más: sin ejecutar nada si alguien la abre directo, y sin quedar en cachés compartidas
        respuesta['Content-Disposition'] = 'inline'
        respuesta['X-Content-Type-Options'] = 'nosniff'
        respuesta['Content-Security-Policy'] = "default-src 'none'; sandbox"
        respuesta['Cache-Control'] = 'private, no-store'
        return respuesta


class AdminCotizacionEstadoView(APIView):
    """PATCH {estado}: la tienda registra si la respondió, la aceptaron o la descartó."""
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        try:
            CambiarEstadoCotizacion(DjangoRepositorioCotizaciones()).ejecutar(pk, request.data.get('estado'))
        except CotizacionNoEncontrada as error:
            raise NotFound(str(error))
        except ValueError:
            return Response({'estado': ['Estado no válido.']}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminCotizacionSerializer(Cotizacion.objects.get(pk=pk)).data)


def resenas_activas():
    config = ConfiguracionGlobal.objects.filter(pk=1).first()
    return bool(config and config.resenas_activas)


ENLACE_RESENA_INVALIDO = 'El enlace para dejar la reseña no es válido o ya venció.'
MENSAJE_RESENA_RECIBIDA = '¡Gracias por tu reseña! La tienda la revisará antes de publicarla.'
# El pedido existe y el enlace es válido, pero ya no se puede (o todavía no se puede) reseñar
ERRORES_PEDIDO_RESENA = (PedidoNoEntregado, ResenaYaEnviada, PlazoResenaVencido)


def error_resena(error):
    if isinstance(error, PedidoNoEncontrado):
        return Response({'detail': ENLACE_RESENA_INVALIDO}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(error, ResenasDesactivadas):
        return Response({'detail': str(error)}, status=status.HTTP_403_FORBIDDEN)
    return Response({'detail': str(error)}, status=status.HTTP_409_CONFLICT)


class ResenaThrottle(CotizacionThrottle):
    """Contra el spam en el envío de reseñas, por IP (DEFAULT_THROTTLE_RATES['resenas'])."""
    scope = 'resenas'


class ResenaFormularioView(APIView):
    """GET /api/ventas/resenas/formulario/?t=<token>: el pedido que se va a reseñar (enlace del correo de entrega)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        orden_id = orden_del_token(request.query_params.get('t'))
        if orden_id is None:
            raise NotFound(ENLACE_RESENA_INVALIDO)
        try:
            formulario = PrepararFormularioResena(DjangoPedidosParaResenar()).ejecutar(
                orden_id, resenas_activas(), timezone.now())
        except (PedidoNoEncontrado, ResenasDesactivadas, *ERRORES_PEDIDO_RESENA) as error:
            return error_resena(error)
        return Response(asdict(formulario))


class ResenaEnvioView(APIView):
    """POST /api/ventas/resenas/ {token, estrellas, comentario, nombre_publico, acepta_publicacion, productos}.

    La reseña queda pendiente hasta que el admin la apruebe.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser]
    throttle_classes = [ResenaThrottle]

    def post(self, request):
        datos = request.data if isinstance(request.data, dict) else {}
        orden_id = orden_del_token(datos.get('token'))
        if orden_id is None:
            raise NotFound(ENLACE_RESENA_INVALIDO)
        try:
            EnviarResena(DjangoPedidosParaResenar(), DjangoRepositorioResenas()).ejecutar(
                orden_id, datos, resenas_activas(), timezone.now())
        except (PedidoNoEncontrado, ResenasDesactivadas, *ERRORES_PEDIDO_RESENA) as error:
            return error_resena(error)
        except ResenaInvalida as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)
        return Response({'mensaje': MENSAJE_RESENA_RECIBIDA}, status=status.HTTP_201_CREATED)


class ResenasTiendaView(APIView):
    """GET /api/ventas/resenas/tienda/: promedio y últimas reseñas aprobadas, para la landing."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response(asdict(ResenasDeLaTienda(DjangoRepositorioResenas()).ejecutar(resenas_activas())))


class ResenasProductoView(APIView):
    """GET /api/ventas/resenas/producto/<id>/: promedio y reseñas aprobadas del producto, para su ficha."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, producto_id):
        resumen = ResenasDeProducto(DjangoRepositorioResenas()).ejecutar(producto_id, resenas_activas())
        return Response(asdict(resumen))


class PaginacionResenas(PaginacionCotizaciones):
    """Igual que las cotizaciones: de a 20 con ?pagina=N."""


class AdminResenaListView(generics.ListAPIView):
    """GET ?estado=PENDIENTE|APROBADA|OCULTA&pagina=N: las reseñas para moderar, las más recientes primero."""
    serializer_class = AdminResenaSerializer
    permission_classes = [IsAdministrador]
    pagination_class = PaginacionResenas

    def get_queryset(self):
        resenas = Resena.objects.prefetch_related('productos')
        estado = self.request.query_params.get('estado')
        return resenas.filter(estado=estado) if estado else resenas


class AdminResenaEstadoView(APIView):
    """PATCH {estado}: el admin aprueba u oculta la reseña. No hay forma de crearlas ni de editarlas."""
    permission_classes = [IsAdministrador]

    def patch(self, request, pk):
        try:
            ModerarResena(DjangoRepositorioResenas()).ejecutar(pk, request.data.get('estado'))
        except ResenaNoEncontrada as error:
            raise NotFound(str(error))
        except ModeracionNoPermitida as error:
            return Response({'estado': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({'estado': ['Estado no válido.']}, status=status.HTTP_400_BAD_REQUEST)
        return Response(AdminResenaSerializer(Resena.objects.prefetch_related('productos').get(pk=pk)).data)


class SucursalesCourierAPIView(APIView):
    """
    GET /api/ventas/logistica/sucursales/?comuna=MAIPU&proveedor=CHILEXPRESS
    Las oficinas del courier en una comuna; sin proveedor, las del primer courier activo que tiene oficinas.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        comuna = request.query_params.get('comuna')
        if not comuna:
            return Response({"error": "Debe especificar una comuna."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            proveedor = request.query_params.get('proveedor')
            if proveedor:
                courier = couriers().obtener(proveedor)
            else:
                courier = next((c for c in couriers().activos() if c.con_sucursales), None)
                if courier is None:
                    raise CourierNoActivo()
            if not courier.con_sucursales:
                raise CourierNoActivo()
            sucursales = courier.sucursales(comuna)
        except CourierNoActivo:
            return Response({"error": "No hay retiro en sucursal disponible en esta tienda."},
                            status=status.HTTP_400_BAD_REQUEST)
        except (SinCobertura, CourierNoDisponible) as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"sucursales": [asdict(sucursal) for sucursal in sucursales]}, status=status.HTTP_200_OK)

class DescargarEtiquetaView(APIView):
    permission_classes = [IsEmprendedor]

    def get(self, request, orden_id):
        try:
            orden = OrdenCompra.objects.get(id=orden_id)
        except OrdenCompra.DoesNotExist:
            return Response({"error": "Orden no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        if not es_entrega_con_courier(orden.proveedor_logistico) or not orden.id_transaccion_pasarela:
            return Response({"error": "Esta orden no tiene una etiqueta de courier válida."}, status=status.HTTP_400_BAD_REQUEST)

        # Extraemos el número de OT de la cadena "TOKEN | OT: 123456789"
        try:
            partes = orden.id_transaccion_pasarela.split('OT: ')
            if len(partes) > 1:
                numero_ot = partes[1].strip()
            else:
                return Response({"error": "No se encontró el número de OT."}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({"error": "Formato de OT inválido."}, status=status.HTTP_400_BAD_REQUEST)

        # La etiqueta la entrega el courier del pedido
        try:
            etiqueta_base64 = couriers().obtener(orden.proveedor_logistico).etiqueta(numero_ot)
        except CourierNoActivo:
            return Response({"error": "El courier de este pedido no tiene sus llaves cargadas en el panel."},
                            status=status.HTTP_400_BAD_REQUEST)
        except CourierNoDisponible as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            archivo = base64.b64decode(etiqueta_base64)
        except Exception:
            return Response({"error": "Error al procesar la etiqueta."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # El courier puede entregarla como PDF o como imagen (Chilexpress manda un JPEG): se descarga con su formato
        tipo, extension = next(((tipo, ext) for firma, tipo, ext in FORMATOS_ETIQUETA if archivo.startswith(firma)),
                               ('application/octet-stream', 'bin'))
        response = HttpResponse(archivo, content_type=tipo)
        response['Content-Disposition'] = f'attachment; filename="Etiqueta_OT_{numero_ot}.{extension}"'
        return response

def _periodo_json(periodo):
    return {'desde': periodo.desde, 'hasta': periodo.hasta} if periodo else None


def _nombre_cliente(orden):
    if orden.usuario:
        nombre = ' '.join(filter(None, [orden.usuario.nombre, orden.usuario.apellido_paterno]))
        return nombre or orden.usuario.email
    return orden.email_invitado


def _variante_json(variante):
    return {'producto_id': variante.producto_id, 'producto': variante.producto, 'sku': variante.sku,
            'detalle': variante.detalle, 'stock': variante.stock}


class DashboardMetricasView(APIView):
    """RF-03.1: GET ?periodo=ESTE_MES (o PERSONALIZADO&desde=AAAA-MM-DD&hasta=AAAA-MM-DD). Las ventas del periodo
    por la fecha del pago, contra el periodo anterior, su detalle y los 5 pedidos más recientes."""
    permission_classes = [IsEmprendedor]

    def get(self, request):
        parametros = request.query_params
        try:
            periodo = resolver_periodo(parametros.get('periodo'), timezone.localdate(),
                                       parametros.get('desde'), parametros.get('hasta'))
        except PeriodoInvalido as error:
            return Response({'periodo': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        dashboard = ResumenDashboard(DjangoMetricasVentas()).ejecutar(periodo)
        ultimas = OrdenCompra.objects.select_related('usuario').order_by('-fecha_creacion')[:5]

        return Response({
            'periodo': {**_periodo_json(periodo), 'clave': periodo.clave, 'agrupacion': periodo.agrupacion},
            'anterior': _periodo_json(dashboard.anterior),
            'tarjetas': asdict(dashboard.tarjetas),
            'serie': [asdict(punto) for punto in dashboard.serie],
            'mas_vendidos': [asdict(producto) for producto in dashboard.mas_vendidos],
            'ultimas_ordenes': [{
                'id': orden.id, 'fecha_creacion': orden.fecha_creacion, 'estado': orden.estado,
                'total_final': round(orden.total_final), 'cliente': _nombre_cliente(orden),
            } for orden in ultimas],
            'detalles': {
                'medios_pago': [asdict(barra) for barra in dashboard.medios_pago],
                'entregas': [asdict(barra) for barra in dashboard.entregas],
                'comunas': [asdict(barra) for barra in dashboard.comunas],
                'cancelaciones': [{'causa': causa, 'nombre': ETIQUETAS_CAUSA_CANCELACION[causa], 'cantidad': cantidad}
                                  for causa, cantidad in dashboard.cancelaciones],
                'cupones': [asdict(cupon) for cupon in dashboard.cupones],
                'clientes': asdict(dashboard.clientes),
                'calificacion': asdict(dashboard.calificacion) if dashboard.calificacion else None,
            },
        }, status=status.HTTP_200_OK)


class DashboardExportarVentasView(APIView):
    """RF-03.1: GET con el mismo periodo que las métricas. Descarga un Excel con las ventas de ese periodo (los
    pedidos pagados, por la fecha del pago) y los datos de cada comprador."""
    permission_classes = [IsEmprendedor]

    def get(self, request):
        parametros = request.query_params
        try:
            periodo = resolver_periodo(parametros.get('periodo'), timezone.localdate(),
                                       parametros.get('desde'), parametros.get('hasta'))
        except PeriodoInvalido as error:
            return Response({'periodo': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        planilla = ExportarVentas(DjangoVentasPeriodo()).ejecutar(periodo)

        response = HttpResponse(escribir_xlsx(planilla), content_type=TIPO_XLSX)
        response['Content-Disposition'] = f'attachment; filename="{planilla.nombre}.xlsx"'
        # Trae datos personales de los compradores: que no quede guardado en cachés intermedias
        response['Cache-Control'] = 'no-store'
        return response


class DashboardPendientesView(APIView):
    """RF-03.1: "Para hoy", lo que el admin tiene que atender. Solo trae lo que no está en cero."""
    permission_classes = [IsEmprendedor]

    def get(self, request):
        para_hoy = TareasPendientes(DjangoPendientesTienda(modelo_emision_tienda()),
                                    MongoStockCatalogo()).ejecutar(timezone.now())
        return Response({
            'al_dia': para_hoy.al_dia,
            'tareas': [asdict(tarea) for tarea in para_hoy.tareas],
            'agotadas': [_variante_json(variante) for variante in para_hoy.agotadas],
            'stock_bajo': [_variante_json(variante) for variante in para_hoy.stock_bajo],
        })


class PaginaLegalListView(generics.ListAPIView):
    # RF-03.5: el footer solo enlaza las páginas publicadas
    queryset = PaginaLegal.objects.filter(publicada=True).only(
        'id', 'tipo_pagina', 'titulo', 'ultima_actualizacion',
    )
    serializer_class = PaginaLegalSerializer
    permission_classes = [AllowAny]
    authentication_classes = []


def tipo_pagina_legal(tipo):
    """El tipo llega en la URL en cualquier formato (ej. 'terminos'); None si no es válido."""
    tipo = tipo.upper()
    return tipo if tipo in dict(PaginaLegal.TIPOS_PAGINA) else None


class PaginaLegalDetalleView(APIView):
    """Página pública /legal/<tipo>: un borrador responde igual que una página inexistente."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, tipo):
        pagina = PaginaLegal.objects.filter(tipo_pagina=tipo.upper(), publicada=True).first()
        if pagina is None:
            return Response({'detail': 'Página no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(PaginaLegalDetalleSerializer(pagina).data)


class AdminPaginasLegalesView(APIView):
    """Las tres páginas legales para el editor del admin, aunque aún no estén redactadas."""
    permission_classes = [IsAdministrador]

    def get(self, request):
        existentes = {pagina.tipo_pagina: pagina for pagina in PaginaLegal.objects.all()}
        return Response([
            PaginaLegalAdminSerializer(existentes[tipo]).data if tipo in existentes else {
                'tipo_pagina': tipo, 'titulo': nombre, 'contenido': '',
                'publicada': False, 'ultima_actualizacion': None,
            }
            for tipo, nombre in PaginaLegal.TIPOS_PAGINA
        ])


class AdminPaginaLegalView(APIView):
    """RF-03.5: el admin crea o actualiza una página legal por tipo."""
    permission_classes = [IsAdministrador]

    def put(self, request, tipo):
        tipo = tipo_pagina_legal(tipo)
        if tipo is None:
            return Response({'detail': 'Página no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        pagina = PaginaLegal.objects.filter(tipo_pagina=tipo).first()
        serializer = PaginaLegalAdminSerializer(pagina, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(tipo_pagina=tipo)
        return Response(serializer.data, status=status.HTTP_200_OK if pagina else status.HTTP_201_CREATED)


def repositorio_publicaciones():
    return DjangoRepositorioPublicaciones()


def blog_activo():
    config = ConfiguracionGlobal.objects.filter(pk=1).first()
    return bool(config and config.blog_activo)


def publicacion_para_panel(publicacion_id, request):
    publicacion = Publicacion.objects.prefetch_related('fotos').get(id=publicacion_id)
    return PublicacionAdminSerializer(publicacion, context={'request': request}).data

class SobreMiPublicoView(APIView):
    """Información pública de la página Sobre mí. Responde 404 si está desactivada."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        configuracion = ConfiguracionGlobal.objects.filter(pk=1).first()

        try:
            exigir_sobre_mi_disponible(configuracion.sobre_mi_activo if configuracion else False)
        except SobreMiNoDisponible as error:
            raise NotFound(str(error)) from error

        publicaciones = []
        # Con el blog apagado los proyectos no se muestran (domain/sobre_mi.py)
        if muestra_proyectos_sobre_mi(configuracion.blog_activo):
            proyectos = (
                ProyectoDestacadoSobreMi.objects
                .filter(
                    configuracion=configuracion,
                    publicacion__estado='PUBLICADA',
                )
                .select_related('publicacion')
                .order_by('orden', 'id')
            )
            publicaciones = [proyecto.publicacion for proyecto in proyectos]

        contacto = construir_contacto_sobre_mi(
            telefono=configuracion.telefono_comercial,
            correo=configuracion.correo_contacto,
            instagram=configuracion.instagram_usuario,
        )

        return Response({
            'nombre': configuracion.sobre_mi_nombre,
            'biografia': configuracion.sobre_mi_biografia,
            'proyectos': PublicacionResumenSerializer(
                publicaciones,
                many=True,
                context={'request': request},
            ).data,
            'contacto': contacto,
            'fotos': fotos_sobre_mi([
                (request.build_absolute_uri(foto.url) if foto else None, alt)
                for foto, alt in ((configuracion.sobre_mi_foto_1, configuracion.sobre_mi_foto_1_alt),
                                  (configuracion.sobre_mi_foto_2, configuracion.sobre_mi_foto_2_alt))
            ]),
        })


class AdminSobreMiProyectosView(APIView):
    """Consultar y guardar los proyectos destacados de Sobre mí."""

    permission_classes = [IsAdministrador]

    def get(self, request):
        configuracion = ConfiguracionGlobal.objects.filter(pk=1).first()

        if not configuracion:
            return Response({'proyectos': []})

        proyectos = (
            ProyectoDestacadoSobreMi.objects
            .filter(configuracion=configuracion)
            .order_by('orden', 'id')
        )

        return Response({
            'proyectos': list(proyectos.values_list('publicacion_id', flat=True))
        })

    @transaction.atomic
    def put(self, request):
        configuracion = ConfiguracionGlobal.objects.filter(pk=1).first()

        if not configuracion:
            raise NotFound('Configuración de la tienda no encontrada.')

        try:
            ids = validar_ids_proyectos_sobre_mi(request.data.get('proyectos'))
        except ProyectosSobreMiInvalidos as error:
            return Response(
                {'proyectos': [str(error)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existentes = set(
            Publicacion.objects.filter(id__in=ids)
            .values_list('id', flat=True)
        )

        if existentes != set(ids):
            return Response(
                {'proyectos': ['Una o más publicaciones no existen.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ProyectoDestacadoSobreMi.objects.filter(
            configuracion=configuracion
        ).delete()

        ProyectoDestacadoSobreMi.objects.bulk_create([
            ProyectoDestacadoSobreMi(
                configuracion=configuracion,
                publicacion_id=pk,
                orden=indice,
            )
            for indice, pk in enumerate(ids)
        ])

        return Response({'proyectos': ids})

class BlogPublicoView(APIView):
    """GET /api/ventas/blog/?pagina=N: las publicaciones del blog, si el admin lo activó (RF-01.1)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        try:
            pagina = max(int(request.query_params.get('pagina', 1)), 1)
        except ValueError:
            pagina = 1
        caso = VerBlog(repositorio_publicaciones())
        try:
            resultado = caso.ejecutar(blog_activo(), pagina)
        except BlogDesactivado as error:
            raise NotFound(str(error))
        publicaciones = Publicacion.objects.in_bulk(resultado.ids)
        return Response({
            'resultados': PublicacionResumenSerializer(
                [publicaciones[i] for i in resultado.ids if i in publicaciones], many=True,
                context={'request': request}).data,
            'total': resultado.total,
            'pagina': pagina,
            'paginas': ceil(resultado.total / caso.por_pagina),
        })


class BlogPublicacionView(APIView):
    """GET /api/ventas/blog/<slug>/: un borrador responde igual que una publicación inexistente."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, slug):
        try:
            publicacion_id = VerPublicacion(repositorio_publicaciones()).ejecutar(slug, blog_activo())
        except (BlogDesactivado, PublicacionNoEncontrada) as error:
            raise NotFound(str(error))
        publicacion = Publicacion.objects.prefetch_related('fotos').get(id=publicacion_id)
        return Response(PublicacionDetalleSerializer(publicacion, context={'request': request}).data)


class SubidaFotosBlogMixin:
    """Corta subidas de demasiados archivos o muy pesados antes de que Django los escriba (como el catálogo)."""

    def initialize_request(self, request, *args, **kwargs):
        request.upload_handlers.insert(0, CatalogoImageUploadHandler(request))
        return super().initialize_request(request, *args, **kwargs)


def guardar_publicacion(request, publicacion_id, estado_http):
    """Crea (id None) o edita una publicación con lo que envió el panel."""
    serializer = PublicacionEntradaSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    datos = dict(serializer.validated_data)
    portada = datos.pop('portada', None)
    if portada is None:
        portada = None if datos.pop('quitar_portada') else SIN_CAMBIO
    try:
        publicacion_id = GuardarPublicacion(repositorio_publicaciones()).ejecutar(
            publicacion_id, datos, contenido_tiene_texto=tiene_texto(datos['contenido']), ahora=timezone.now(),
            portada=portada)
    except PublicacionNoEncontrada as error:
        raise NotFound(str(error))
    except PublicacionInvalida as error:
        return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)
    return Response(publicacion_para_panel(publicacion_id, request), status=estado_http)


class AdminBlogView(SubidaFotosBlogMixin, APIView):
    """GET todas las publicaciones (los borradores primero) y POST para crear una. Funciona con el blog apagado."""
    permission_classes = [IsAdministrador]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request):
        publicaciones = Publicacion.objects.prefetch_related('fotos').order_by(
            F('fecha_publicacion').desc(nulls_first=True), '-id')
        return Response(PublicacionAdminSerializer(publicaciones, many=True, context={'request': request}).data)

    def post(self, request):
        return guardar_publicacion(request, None, status.HTTP_201_CREATED)


class AdminPublicacionView(SubidaFotosBlogMixin, APIView):
    """GET, PUT (el formulario completo) y DELETE de una publicación."""
    permission_classes = [IsAdministrador]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get(self, request, pk):
        if not Publicacion.objects.filter(id=pk).exists():
            raise NotFound('Publicación no encontrada.')
        return Response(publicacion_para_panel(pk, request))

    def put(self, request, pk):
        return guardar_publicacion(request, pk, status.HTTP_200_OK)

    def delete(self, request, pk):
        try:
            EliminarPublicacion(repositorio_publicaciones()).ejecutar(pk)
        except PublicacionNoEncontrada as error:
            raise NotFound(str(error))
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminFotosPublicacionView(SubidaFotosBlogMixin, APIView):
    """POST multipart con el campo `fotos` repetido por archivo: se agregan al final de la galería."""
    permission_classes = [IsAdministrador]
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        serializer = FotosPublicacionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            AgregarFotos(repositorio_publicaciones()).ejecutar(pk, serializer.validated_data['fotos'])
        except PublicacionNoEncontrada as error:
            raise NotFound(str(error))
        except LimiteFotosExcedido as error:
            return Response({'fotos': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(publicacion_para_panel(pk, request), status=status.HTTP_201_CREATED)


class AdminFotoPublicacionView(APIView):
    """DELETE de una foto de la galería; responde la publicación actualizada."""
    permission_classes = [IsAdministrador]

    def delete(self, request, pk, foto_id):
        try:
            QuitarFoto(repositorio_publicaciones()).ejecutar(pk, foto_id)
        except FotoNoEncontrada as error:
            raise NotFound(str(error))
        return Response(publicacion_para_panel(pk, request))

def codigo_medio_pago(codigo):
    """Código válido de medio de pago (sin distinguir mayúsculas), o None."""
    try:
        return CodigoMedioPago(codigo.upper())
    except ValueError:
        return None


class AdminMediosPagoView(APIView):
    """RN-02: los medios de pago con su estado; las credenciales van enmascaradas."""
    permission_classes = [IsAdministrador]

    def get(self, request):
        return Response([medio_pago_para_panel(medio) for medio in medios_pago().listar()])


class AdminMedioPagoView(APIView):
    """El admin habilita un medio de pago y carga sus datos (se puede guardar incompleto)."""
    permission_classes = [IsAdministrador]

    def put(self, request, codigo):
        codigo = codigo_medio_pago(codigo)
        if codigo is None:
            return Response({'detail': 'Medio de pago no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MedioPagoAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            medio = ConfigurarMedioPago(DjangoRepositorioMediosPago()).ejecutar(
                codigo, serializer.validated_data['habilitado'], serializer.validated_data['datos'])
        except DatosMedioPagoInvalidos as error:
            return Response({'datos': error.errores}, status=status.HTTP_400_BAD_REQUEST)
        return Response(medio_pago_para_panel(medio))


class AdminCouriersView(APIView):
    """RNF-03: cada courier que la tienda puede usar, con sus llaves enmascaradas, para cargarlas en el panel."""
    permission_classes = [IsAdministrador]

    def get(self, request):
        registro = couriers()
        return Response([courier_para_panel(registro.obtener(codigo, solo_activos=False))
                         for codigo in CODIGOS_COURIERS])


class AdminCourierView(APIView):
    """RNF-03: el admin carga o reemplaza las llaves de un courier; solo se devuelven enmascaradas."""
    permission_classes = [IsAdministrador]

    def put(self, request, codigo):
        serializer = CredencialesCourierSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        registro = couriers()
        try:
            ConfigurarCourier(DjangoRepositorioCredencialesCourier(), registro).ejecutar(
                codigo, serializer.validated_data['datos'])
        except CourierNoActivo:
            return Response({'detail': 'Courier no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        except CredencialesInvalidas as error:
            return Response({'datos': error.errores}, status=status.HTTP_400_BAD_REQUEST)
        return Response(courier_para_panel(registro.obtener(codigo, solo_activos=False)))

class ValidarPromocionAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        codigo = str(request.data.get('codigo') or '').strip().upper()
        try:
            subtotal = float(request.data.get('subtotal', 0))
        except (TypeError, ValueError):
            subtotal = -1.0
        # "nan" o "inf" también se convierten a float
        if not math.isfinite(subtotal) or subtotal < 0:
            return Response({"error": "El subtotal no es válido."}, status=status.HTTP_400_BAD_REQUEST)

        if not codigo:
            return Response({"error": "Debes ingresar un código."}, status=status.HTTP_400_BAD_REQUEST)

        # first(): si quedaron códigos antiguos que solo difieren en mayúsculas, get() fallaba con un error 500
        promo = Promocion.objects.filter(codigo__iexact=codigo, is_active=True).order_by('id').first()
        if promo is None:
            return Response({"error": "Código inválido o expirado."}, status=status.HTTP_404_NOT_FOUND)

        if not promo.esta_vigente:
            return Response({"error": "Código inválido o expirado."}, status=status.HTTP_400_BAD_REQUEST)

        # El mismo cálculo que el checkout (domain/promociones.py): nunca más que el subtotal ni bajo el mínimo
        regla = regla_de_promocion(promo)
        if not cumple_minimo(regla, Decimal(str(subtotal))):
            return Response({"error": mensaje_monto_minimo(promo), "monto_minimo": promo.monto_minimo},
                            status=status.HTTP_400_BAD_REQUEST)
        descuento = monto_descuento(regla, Decimal(str(subtotal)))

        return Response({
            "codigo": promo.codigo,
            "tipo_descuento": promo.tipo_descuento,
            "valor_descuento": promo.valor_descuento,
            "descuento": round(descuento),
            "umbral_envio_gratis": promo.umbral_envio_gratis,
            "monto_minimo": promo.monto_minimo,
        }, status=status.HTTP_200_OK)


class PromocionesAutomaticasAPIView(APIView):
    """GET /api/ventas/promociones/automaticas/: los descuentos que se aplican solos desde un monto (RF-04.1).

    Para la vista previa del checkout ("te faltan $X para el descuento"). Sin el código ni el id: un automático no
    se escribe, y el cobro lo decide el servidor al pagar.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response([{
            'tipo_descuento': promo.tipo_descuento,
            'valor_descuento': promo.valor_descuento,
            'monto_minimo': promo.monto_minimo,
            'umbral_envio_gratis': promo.umbral_envio_gratis,
        } for promo in promociones_automaticas_vigentes()])


class LinkifyWebhookAPIView(APIView):
    # Permitir que Linkify acceda sin token de usuario
    permission_classes = [AllowAny]
    authentication_classes = []

    def _obtener_secret_key(self):
        """Extrae la clave secreta de Linkify desde la configuración de medios de pago"""
        try:
            # Asumiendo que el código del medio es TRANSFERENCIA
            medio = medios_pago().exigir(CodigoMedioPago.TRANSFERENCIA)
            # Retorna el secret guardado, o string vacío si no existe
            return medio.datos.get('linkify_secret', '')
        except Exception:
            return ''

    def verificar_firma(self, request, content):
            firma_recibida = request.headers.get("X-Linkify-Confirmation")
            if not firma_recibida:
                return False
                
            secret = self._obtener_secret_key()
            if not secret:
                return False

            firma_calculada = hmac.new(
                secret.encode('utf-8'),
                content,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(firma_recibida, firma_calculada)

    def get(self, request, *args, **kwargs):
        """Petición inicial de Linkify para consultar el monto de la orden[cite: 4]"""
        encoded_data = request.query_params.get('encoded_data', '')
        
        # Validar seguridad con el string crudo[cite: 4]
        if not self.verificar_firma(request, encoded_data.encode('utf-8')):
            return Response({"message": "Firma inválida"}, status=status.HTTP_403_FORBIDDEN)

        try:
            datos = json.loads(encoded_data)
        except ValueError:
            return Response({"message": "Datos inválidos"}, status=status.HTTP_400_BAD_REQUEST)

        # Buscar la orden real en la base de datos
        orden_id = str(datos.get("id", "")) if isinstance(datos, dict) else ""
        orden = OrdenCompra.objects.filter(id=int(orden_id)).first() if orden_id.isdigit() else None
        if orden is None:
            return Response({"message": "Orden no encontrada"}, status=status.HTTP_404_NOT_FOUND)

        respuesta = {
            "amount": int(round(orden.total_final)),
            "description": f"Orden #{orden.id}",
            "currency": "CLP"
        }
        return Response(respuesta, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """Notificación de transferencia validada por Linkify]"""
        cuerpo = request.body # Usar request.body crudo para no romper el HMAC
        
        # 1. Seguridad: Verificar firma]
        if not self.verificar_firma(request, cuerpo):
            return Response({
                "message": "Firma de seguridad inválida", 
                "notify_merchant": False
            }, status=status.HTTP_403_FORBIDDEN)

        datos_pago = json.loads(cuerpo)
        
        if datos_pago.get("action") != "notification":
            return Response({"status": "rejected", "message": "Acción ignorada"}, status=status.HTTP_200_OK)

        orden_id = datos_pago.get("id")
        completeness = datos_pago.get("completeness")
        
      # 2. Lógica de negocio
        try:
            # Mismas dependencias que los demás pagos: la OT la genera el caso de uso a partir del envío de la orden
            caso_uso = confirmar_pago()
            
            pago_exacto = (completeness == "exact")
            
            # CAMBIO AQUÍ: Usar aprobar() en lugar de ejecutar()
            caso_uso.aprobar(
                orden_id=orden_id,
                pago_exacto=pago_exacto 
            )

            # 3. Respuesta de éxito
            return Response({
                "status": "accepted",
                "message": "Pago verificado correctamente",
                "restart": False
            }, status=status.HTTP_200_OK)

        except Exception as e:
            # Respuesta de error
            print(f"Error en webhook: {str(e)}") # Opcional: sirve para ver el error exacto en la consola si vuelve a fallar
            return Response({
                "message": f"Error procesando la orden: {str(e)}",
                "notify_merchant": True
            }, status=status.HTTP_400_BAD_REQUEST)


class PromocionListCreateView(generics.ListCreateAPIView):
    # Los cupones los gestiona solo el admin; el comprador los valida en promociones/validar/
    permission_classes = [IsAdministrador]
    queryset = Promocion.objects.all().order_by('-id')
    serializer_class = PromocionSerializer


class PromocionDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdministrador]
    queryset = Promocion.objects.all()
    serializer_class = PromocionSerializer
