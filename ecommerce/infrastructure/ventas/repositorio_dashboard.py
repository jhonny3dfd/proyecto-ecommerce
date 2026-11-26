"""Adaptadores Django (PostgreSQL) de los puertos MetricasVentas y PendientesTienda del dashboard (RF-03.1)."""

from datetime import datetime, time, timedelta

from django.db.models import Case, Count, F, IntegerField, Max, Min, Q, Sum, When
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce, Lower, TruncDate, TruncMonth, Upper
from django.utils import timezone

from ecommerce.application.dashboard import (
    ConteoPendientes, Grupo, MetricasVentas, PendientesTienda, ProductoVendido, PuntoSerie, ResumenClientes,
    ResumenVentas, UsoCupon,
)
from ecommerce.application.exportacion_ventas import LineaVendida, VentaPeriodo, VentasPeriodo
from ecommerce.domain.cotizaciones import EstadoCotizacion
from ecommerce.domain.dashboard import Agrupacion
from ecommerce.domain.documentos_tributarios import ModeloEmision
from ecommerce.domain.logistica import NOMBRES_ENTREGAS_DE_LA_TIENDA, RETIRO_LOCAL
from ecommerce.domain.medios_pago import MEDIOS_PAGO, CodigoMedioPago
from ecommerce.domain.resenas import EstadoResena
from ecommerce.domain.ventas import ESTADOS_CON_ORDEN_TRANSPORTE, ESTADOS_PAGADOS, EstadoPedido

from .couriers import COURIERS
from .models import ConfiguracionGlobal, Cotizacion, DetalleOrden, OrdenCompra, Resena
from .repositorio_documentos import filtro_documento_pendiente

# Un pedido pagado antes de que existiera fecha_pago, o marcado a mano desde /admin/, cuenta por su creación
FECHA_VENTA = Coalesce('fecha_pago', 'fecha_creacion')
# El comprador: el correo de su cuenta o el que dejó como invitado, sin distinguir mayúsculas
CORREO_CLIENTE = Lower(Coalesce('usuario__email', 'email_invitado'))
NOMBRES_MEDIOS_PAGO = {**dict(OrdenCompra.METODOS_PAGO), **{m.codigo.value: m.nombre for m in MEDIOS_PAGO}}


def _limites(periodo):
    """El periodo en fechas locales de la tienda: desde las 00:00 del primer día hasta antes de las 00:00 del día
    siguiente al último."""
    zona = timezone.get_current_timezone()
    inicio = datetime.combine(periodo.desde, time.min, tzinfo=zona) if periodo.desde else None
    fin = datetime.combine(periodo.hasta + timedelta(days=1), time.min, tzinfo=zona)
    return inicio, fin


def _en_periodo(ordenes, periodo, campo):
    inicio, fin = _limites(periodo)
    ordenes = ordenes.filter(**{f'{campo}__lt': fin})
    return ordenes.filter(**{f'{campo}__gte': inicio}) if inicio else ordenes


def _pagadas():
    return OrdenCompra.objects.filter(estado__in=[estado.value for estado in ESTADOS_PAGADOS]).annotate(
        fecha_venta=FECHA_VENTA)


def _ventas(periodo):
    return _en_periodo(_pagadas(), periodo, 'fecha_venta')


def _entero(valor):
    return round(valor or 0)


def _nombre_entrega(codigo):
    codigo = (codigo or '').upper()
    if codigo in NOMBRES_ENTREGAS_DE_LA_TIENDA:
        return NOMBRES_ENTREGAS_DE_LA_TIENDA[codigo]
    if codigo in COURIERS:
        return COURIERS[codigo].nombre
    return codigo.title() or 'Sin entrega'


class DjangoMetricasVentas(MetricasVentas):
    def resumen(self, periodo):
        datos = _ventas(periodo).aggregate(total=Sum('total_final'), pedidos=Count('id'))
        return ResumenVentas(_entero(datos['total']), datos['pedidos'])

    def serie(self, periodo):
        truncar = TruncMonth if periodo.agrupacion == Agrupacion.MES else TruncDate
        filas = (_ventas(periodo).annotate(punto=truncar('fecha_venta')).values('punto')
                 .annotate(total=Sum('total_final'), pedidos=Count('id')).order_by('punto'))
        return [PuntoSerie(_fecha(fila['punto']), _entero(fila['total']), fila['pedidos']) for fila in filas]

    def mas_vendidos(self, periodo, limite):
        filas = (DetalleOrden.objects.filter(orden__in=_ventas(periodo).values('id'))
                 .values('producto_mongo_id')
                 .annotate(nombre=Max('nombre_producto_snapshot'), unidades=Sum('cantidad'),
                           total=Sum(F('cantidad') * F('precio_unitario_snapshot')))
                 .order_by('-unidades', '-total', 'producto_mongo_id')[:limite])
        return [ProductoVendido(fila['producto_mongo_id'], fila['nombre'], fila['unidades'], _entero(fila['total']))
                for fila in filas]

    def _agrupar(self, ordenes, campo):
        return ordenes.values(clave=campo).annotate(total=Sum('total_final'), pedidos=Count('id'))

    def por_medio_pago(self, periodo):
        return [Grupo(fila['clave'], NOMBRES_MEDIOS_PAGO.get(fila['clave'], fila['clave']), _entero(fila['total']),
                      fila['pedidos'])
                for fila in self._agrupar(_ventas(periodo), F('metodo_pago'))]

    def por_entrega(self, periodo):
        grupos = {}
        # Los pedidos antiguos guardaron el courier en minúsculas ('chilexpress'): se juntan con los nuevos
        for fila in self._agrupar(_ventas(periodo), Upper('proveedor_logistico')):
            clave = fila['clave'] or ''
            actual = grupos.get(clave)
            grupos[clave] = Grupo(clave, _nombre_entrega(clave), _entero(fila['total']) + (actual.total if actual else 0),
                                  fila['pedidos'] + (actual.pedidos if actual else 0))
        return list(grupos.values())

    def por_comuna(self, periodo, limite):
        comuna = Upper(KeyTextTransform('comuna', 'direccion_envio_snapshot'))
        ordenes = _ventas(periodo).exclude(proveedor_logistico=RETIRO_LOCAL)
        filas = (self._agrupar(ordenes, comuna).exclude(clave__isnull=True).exclude(clave='')
                 .order_by('-total', 'clave')[:limite])
        return [Grupo(fila['clave'], fila['clave'].title(), _entero(fila['total']), fila['pedidos']) for fila in filas]

    def cancelaciones(self, periodo):
        canceladas = _en_periodo(OrdenCompra.objects.filter(estado=EstadoPedido.CANCELADO.value), periodo,
                                 'fecha_creacion')
        return [(fila['motivo_cancelacion'], fila['cantidad'])
                for fila in canceladas.values('motivo_cancelacion').annotate(cantidad=Count('id'))]

    def cupones(self, periodo):
        filas = (_ventas(periodo).filter(promocion__isnull=False).values('promocion__codigo')
                 .annotate(usos=Count('id'), descontado=Sum(F('subtotal') + F('costo_envio') - F('total_final'))))
        return [UsoCupon(fila['promocion__codigo'], fila['usos'], max(_entero(fila['descontado']), 0)) for fila in filas]

    def clientes(self, periodo):
        compradores = (_ventas(periodo).annotate(cliente=CORREO_CLIENTE).exclude(cliente__isnull=True)
                       .values('cliente').annotate(
                           registrado=Max(Case(When(usuario__isnull=False, then=1), default=0,
                                               output_field=IntegerField()))))
        registrado = {fila['cliente']: bool(fila['registrado']) for fila in compradores}
        primeras = (_pagadas().annotate(cliente=CORREO_CLIENTE).filter(cliente__in=list(registrado))
                    .values('cliente').annotate(primera=Min('fecha_venta')))
        inicio, _ = _limites(periodo)
        nuevos = sum(1 for fila in primeras if inicio is None or fila['primera'] >= inicio)
        registrados = sum(registrado.values())
        return ResumenClientes(nuevos=nuevos, recurrentes=len(registrado) - nuevos, registrados=registrados,
                               invitados=len(registrado) - registrados)

    def calificaciones(self):
        if not ConfiguracionGlobal.objects.filter(pk=1, resenas_activas=True).exists():
            return None
        return list(Resena.objects.filter(estado=EstadoResena.APROBADA.value).values_list('estrellas', flat=True))


def _fecha(valor):
    return valor.date() if isinstance(valor, datetime) else valor


def _direccion(orden):
    """Calle, número y departamento del despacho. Un retiro en el local no tiene dirección del comprador."""
    if orden.proveedor_logistico == RETIRO_LOCAL:
        return '', ''
    direccion = orden.direccion_envio_snapshot or {}
    texto = ' '.join(str(direccion.get(campo) or '') for campo in ('calle', 'numero')).strip()
    if direccion.get('dpto_casa'):
        texto = f"{texto}, {direccion['dpto_casa']}".strip(', ')
    return texto, str(direccion.get('comuna') or '')


class DjangoVentasPeriodo(VentasPeriodo):
    """Las mismas ventas que cuenta el dashboard (`_ventas`), cada una con su comprador y sus productos."""

    def listar(self, periodo):
        ordenes = (_ventas(periodo).select_related('usuario', 'promocion').prefetch_related('detalles')
                   .order_by('fecha_venta', 'id'))
        return [self._venta(orden) for orden in ordenes]

    @staticmethod
    def _venta(orden):
        usuario = orden.usuario
        empresa = orden.datos_empresa or {}
        direccion, comuna = _direccion(orden)
        nombre_cuenta = ' '.join(filter(None, [usuario.nombre, usuario.apellido_paterno,
                                                usuario.apellido_materno])) if usuario else ''
        return VentaPeriodo(
            numero=orden.id,
            fecha=timezone.localtime(orden.fecha_venta).replace(tzinfo=None),
            estado=EstadoPedido(orden.estado),
            # Un invitado no deja más nombre que el de quien recibe
            cliente=nombre_cuenta or orden.nombre_destinatario,
            correo=(usuario.email if usuario else orden.email_invitado) or '',
            telefono=(usuario.telefono if usuario else '') or orden.telefono_destinatario,
            registrado=usuario is not None,
            destinatario=orden.nombre_destinatario,
            telefono_destinatario=orden.telefono_destinatario,
            entrega=_nombre_entrega(orden.proveedor_logistico),
            direccion=direccion,
            comuna=comuna,
            numero_seguimiento=orden.numero_seguimiento_tracking or '',
            medio_pago=NOMBRES_MEDIOS_PAGO.get(orden.metodo_pago, orden.metodo_pago),
            subtotal=_entero(orden.subtotal),
            costo_envio=_entero(orden.costo_envio),
            total=_entero(orden.total_final),
            cupon=orden.promocion.codigo if orden.promocion else '',
            razon_social=str(empresa.get('razon_social') or ''),
            rut_empresa=str(empresa.get('rut') or ''),
            giro=str(empresa.get('giro') or ''),
            folio_documento=orden.folio_documento,
            lineas=tuple(LineaVendida(detalle.nombre_producto_snapshot, detalle.variante_sku, detalle.cantidad,
                                      _entero(detalle.precio_unitario_snapshot))
                         for detalle in sorted(orden.detalles.all(), key=lambda detalle: detalle.id)),
        )


class DjangoPendientesTienda(PendientesTienda):
    def __init__(self, modelo_emision: ModeloEmision):
        self.modelo_emision = modelo_emision

    def contar(self, por_vencer_antes):
        transferencia = Q(estado=EstadoPedido.PENDIENTE.value, metodo_pago=CodigoMedioPago.TRANSFERENCIA.value)
        con_orden_transporte = [estado.value for estado in ESTADOS_CON_ORDEN_TRANSPORTE]
        conteo = OrdenCompra.objects.aggregate(
            por_preparar=Count('id', filter=Q(estado=EstadoPedido.PAGADO.value, requiere_revision=False)),
            transferencias=Count('id', filter=transferencia),
            transferencias_por_vencer=Count('id', filter=transferencia & Q(fecha_limite_pago__lt=por_vencer_antes)),
            revision=Count('id', filter=Q(requiere_revision=True)),
            orden_transporte=Count('id', filter=Q(estado__in=con_orden_transporte) & ~Q(error_orden_transporte='')),
            documentos=Count('id', filter=filtro_documento_pendiente(self.modelo_emision)),
        )
        return ConteoPendientes(
            **conteo,
            cotizaciones=Cotizacion.objects.filter(estado=EstadoCotizacion.NUEVA.value).count(),
            resenas=Resena.objects.filter(estado=EstadoResena.PENDIENTE.value).count(),
        )
