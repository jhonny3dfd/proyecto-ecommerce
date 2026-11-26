"""Adaptadores Django de los puertos de suscripciones (ecommerce/application/suscripciones.py)."""

from dataclasses import asdict
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from ecommerce.application.couriers import CourierNoActivo
from ecommerce.application.suscripciones import (
    CatalogoSuscripciones, CompraNoPermitida, CotizadorDespacho, DespachoNoDisponible, Entrega, PedidoCiclo,
    PedidosSuscripcion, PlanRegistrado, ReglasCompra, RepositorioPlanes, RepositorioSuscripciones,
    SuscripcionRegistrada, VarianteElegible,
)
from ecommerce.domain.logistica import (
    ENTREGAS_DE_LA_TIENDA, CourierNoDisponible, EntregaNoHabilitada, SinCobertura, error_direccion_entrega,
    paquete_de_envio,
)
from ecommerce.domain.medios_pago import MedioPagoNoDisponible
from ecommerce.domain.suscripciones import DatosPlan, EstadoSuscripcion
from ecommerce.domain.ventas import EstadoPedido

from .models import DetalleOrden, OrdenCompra, PlanSuscripcion, Suscripcion


# ---------- Planes ----------

def datos_plan(plan: PlanSuscripcion) -> DatosPlan:
    """El plan guardado como lo entiende el dominio (ya se validó al guardarlo)."""
    return DatosPlan(
        nombre=plan.nombre, precio=plan.precio, frecuencia_semanas=plan.frecuencia_semanas, unidades=plan.unidades,
        descripcion=plan.descripcion, beneficios=tuple(plan.beneficios or ()), categorias=tuple(plan.categorias or ()),
        productos=tuple(plan.productos or ()), envio_gratis=plan.envio_gratis,
        envio_gratis_compras=plan.envio_gratis_compras, descuento=plan.descuento, activo=plan.activo)


def plan_registrado(plan: PlanSuscripcion) -> PlanRegistrado:
    return PlanRegistrado(plan.id, datos_plan(plan))


class DjangoRepositorioPlanes(RepositorioPlanes):
    def obtener(self, plan_id):
        plan = PlanSuscripcion.objects.filter(pk=plan_id).first() if str(plan_id).isdigit() else None
        return plan_registrado(plan) if plan else None


# ---------- Suscripciones ----------

def suscripcion_registrada(fila: Suscripcion) -> SuscripcionRegistrada:
    return SuscripcionRegistrada(
        id=fila.id, usuario_id=fila.usuario_id, plan=plan_registrado(fila.plan), estado=EstadoSuscripcion(fila.estado),
        producto_id=fila.producto_mongo_id, sku=fila.variante_sku, nombre_producto=fila.nombre_producto,
        entrega=Entrega(fila.proveedor_logistico, dict(fila.direccion_envio or {}), fila.nombre_destinatario,
                        fila.telefono_destinatario),
        metodo_pago=fila.metodo_pago, proxima_entrega=fila.proxima_entrega)


class DjangoRepositorioSuscripciones(RepositorioSuscripciones):
    def crear(self, usuario_id, plan_id, variante, entrega, metodo_pago, proxima_entrega):
        return Suscripcion.objects.create(
            usuario_id=usuario_id, plan_id=plan_id, producto_mongo_id=variante.producto_id,
            variante_sku=variante.sku, nombre_producto=variante.nombre, direccion_envio=entrega.direccion,
            nombre_destinatario=entrega.destinatario, telefono_destinatario=entrega.telefono,
            proveedor_logistico=entrega.proveedor_logistico, metodo_pago=metodo_pago,
            proxima_entrega=proxima_entrega).id

    def obtener(self, suscripcion_id):
        fila = Suscripcion.objects.select_related('plan').filter(pk=suscripcion_id).first()
        return suscripcion_registrada(fila) if fila else None

    def cambiar_estado(self, suscripcion_id, desde, hacia, motivo=''):
        cambios = {'estado': EstadoSuscripcion(hacia).value}
        if hacia == EstadoSuscripcion.ACTIVA and desde == EstadoSuscripcion.PENDIENTE:
            cambios['fecha_activacion'] = timezone.now()
        if hacia == EstadoSuscripcion.CANCELADA:
            cambios.update(fecha_cancelacion=timezone.now(), motivo_cancelacion=motivo[:255])
        # UPDATE condicional: si otro proceso ya la cambió, no se pisa
        return Suscripcion.objects.filter(pk=suscripcion_id, estado=EstadoSuscripcion(desde).value).update(
            **cambios) == 1

    def fijar_proxima(self, suscripcion_id, fecha):
        Suscripcion.objects.filter(pk=suscripcion_id).update(proxima_entrega=fecha)

    def avanzar_si(self, suscripcion_id, ciclo_fecha, nueva):
        return Suscripcion.objects.filter(pk=suscripcion_id, proxima_entrega=ciclo_fecha).update(
            proxima_entrega=nueva) == 1

    def cambiar_datos(self, suscripcion_id, variante=None, entrega=None, metodo_pago=None):
        cambios = {}
        if variante is not None:
            cambios.update(producto_mongo_id=variante.producto_id, variante_sku=variante.sku,
                           nombre_producto=variante.nombre)
        if entrega is not None:
            cambios.update(proveedor_logistico=entrega.proveedor_logistico, direccion_envio=entrega.direccion,
                           nombre_destinatario=entrega.destinatario, telefono_destinatario=entrega.telefono)
        if metodo_pago is not None:
            cambios['metodo_pago'] = metodo_pago
        if cambios:
            Suscripcion.objects.filter(pk=suscripcion_id).update(**cambios)

    def ids_por_avisar(self, hasta):
        return list(Suscripcion.objects.filter(estado=EstadoSuscripcion.ACTIVA.value, proxima_entrega__lte=hasta)
                    .order_by('proxima_entrega', 'id').values_list('id', flat=True))

    def ids_con_ciclo_vencido(self, hoy):
        return list(Suscripcion.objects.filter(
            estado__in=[EstadoSuscripcion.ACTIVA.value, EstadoSuscripcion.PENDIENTE.value], proxima_entrega__lt=hoy,
        ).order_by('id').values_list('id', flat=True))

    def planes_activos_de(self, usuario_id):
        filas = Suscripcion.objects.filter(usuario_id=usuario_id, estado=EstadoSuscripcion.ACTIVA.value)
        return [datos_plan(fila.plan) for fila in filas.select_related('plan')]


# ---------- Pedidos de los ciclos ----------

class DjangoPedidosSuscripcion(PedidosSuscripcion):
    """Cada ciclo es un OrdenCompra Pendiente con una línea: la variante elegida por las unidades del plan, al precio
    del plan. Se paga, descuenta stock y se despacha como cualquier pedido."""

    def __init__(self, catalogo: CatalogoSuscripciones):
        self.catalogo = catalogo

    def crear(self, suscripcion, ciclo_fecha, costo_envio):
        plan = suscripcion.plan.datos
        fila = Suscripcion.objects.select_related('usuario').get(pk=suscripcion.id)
        variante = self.catalogo.variante(suscripcion.producto_id, suscripcion.sku)
        paquete = None
        if suscripcion.entrega.proveedor_logistico not in ENTREGAS_DE_LA_TIENDA and variante is not None:
            paquete = {campo: str(valor) for campo, valor in asdict(
                paquete_de_envio([(variante.medidas, plan.unidades)])).items()}
        subtotal = Decimal(plan.precio)
        try:
            # Savepoint: si el ciclo ya tiene pedido (restricción única), solo se deshace este intento
            with transaction.atomic():
                orden = OrdenCompra.objects.create(
                    usuario=fila.usuario, email_invitado='', estado=EstadoPedido.PENDIENTE.value,
                    metodo_pago=suscripcion.metodo_pago, direccion_envio_snapshot=suscripcion.entrega.direccion,
                    nombre_destinatario=suscripcion.entrega.destinatario,
                    telefono_destinatario=suscripcion.entrega.telefono,
                    proveedor_logistico=suscripcion.entrega.proveedor_logistico, paquete=paquete,
                    subtotal=float(subtotal), costo_envio=float(costo_envio),
                    total_final=float(subtotal + Decimal(costo_envio)), suscripcion_id=suscripcion.id,
                    ciclo_fecha=ciclo_fecha)
                DetalleOrden.objects.create(
                    orden=orden, producto_mongo_id=suscripcion.producto_id, variante_sku=suscripcion.sku,
                    nombre_producto_snapshot=f'{suscripcion.nombre_producto} (suscripción {plan.nombre})'[:255],
                    precio_unitario_snapshot=float(subtotal / plan.unidades), cantidad=plan.unidades)
        except IntegrityError:
            return None
        return orden.id

    @staticmethod
    def _pedido(orden) -> PedidoCiclo:
        return PedidoCiclo(orden.id, orden.suscripcion_id, orden.ciclo_fecha, EstadoPedido(orden.estado))

    def del_ciclo(self, suscripcion_id, ciclo_fecha):
        orden = (OrdenCompra.objects.filter(suscripcion_id=suscripcion_id, ciclo_fecha=ciclo_fecha)
                 .exclude(estado=EstadoPedido.CANCELADO.value).first())
        return self._pedido(orden) if orden else None

    def pendientes(self, suscripcion_id):
        return [self._pedido(orden) for orden in OrdenCompra.objects.filter(
            suscripcion_id=suscripcion_id, estado=EstadoPedido.PENDIENTE.value).order_by('ciclo_fecha', 'id')]

    def ciclo_de(self, orden_id):
        orden = OrdenCompra.objects.filter(pk=orden_id, suscripcion__isnull=False).first()
        return self._pedido(orden) if orden else None

    def cancelar(self, orden_id, motivo):
        return OrdenCompra.objects.filter(pk=orden_id, estado=EstadoPedido.PENDIENTE.value).update(
            estado=EstadoPedido.CANCELADO.value, motivo_cancelacion=motivo[:255]) == 1


# ---------- Despacho y reglas de la tienda ----------

class DespachoSuscripcion(CotizadorDespacho):
    """Lo mismo que cobraría el checkout: la entrega de la tienda con su costo, o la cotización del courier con el
    paquete de la variante por las unidades del plan."""

    def __init__(self, catalogo: CatalogoSuscripciones):
        self.catalogo = catalogo

    def costo(self, suscripcion):
        # Importados aquí: serializers.py importa este módulo a través de las vistas
        from .serializers import comuna_origen_tienda, entregas_de_la_tienda, precio_envio
        proveedor = suscripcion.entrega.proveedor_logistico
        if proveedor in ENTREGAS_DE_LA_TIENDA:
            try:
                return entregas_de_la_tienda().costo(proveedor)
            except EntregaNoHabilitada as error:
                raise DespachoNoDisponible(str(error)) from error
        variante = self.catalogo.variante(suscripcion.producto_id, suscripcion.sku)
        if variante is None:
            raise DespachoNoDisponible('El producto de la suscripción ya no está disponible.')
        paquete = paquete_de_envio([(variante.medidas, suscripcion.plan.datos.unidades)])
        try:
            return Decimal(precio_envio(proveedor, comuna_origen_tienda(),
                                        suscripcion.entrega.direccion.get('comuna'), paquete))
        except (CourierNoActivo, SinCobertura, CourierNoDisponible) as error:
            raise DespachoNoDisponible(str(error) or 'No se pudo cotizar el despacho.') from error


class ReglasCompraTienda(ReglasCompra):
    """RN-02 y RF-02.3: las mismas reglas del checkout (medios habilitados y configurados, entregas activas)."""

    def validar(self, metodo_pago, entrega):
        from .serializers import couriers, entregas_de_la_tienda, medios_pago
        try:
            medios_pago().exigir(metodo_pago)
        except MedioPagoNoDisponible as error:
            raise CompraNoPermitida(str(error)) from error
        proveedor = entrega.proveedor_logistico
        if not proveedor:
            raise CompraNoPermitida('Elige cómo quieres recibir tus entregas.')
        if proveedor in ENTREGAS_DE_LA_TIENDA:
            try:
                entregas_de_la_tienda().costo(proveedor)
            except EntregaNoHabilitada as error:
                raise CompraNoPermitida(str(error)) from error
        else:
            try:
                couriers().obtener(proveedor)
            except CourierNoActivo:
                raise CompraNoPermitida('Esa forma de entrega no está disponible.') from None
        error = error_direccion_entrega(proveedor, entrega.direccion)
        if error:
            raise CompraNoPermitida(error)


# ---------- Consultas del panel ----------

def suscripciones_del_panel(estado: str = '', plan_id: str = '', pago_pendiente: bool = False):
    """Lista de suscriptores con filtros. "Pago pendiente": activas con un pedido de ciclo sin pagar."""
    filas = Suscripcion.objects.select_related('plan', 'usuario').order_by(F('proxima_entrega').asc(nulls_last=True),
                                                                            'id')
    if estado:
        filas = filas.filter(estado=estado)
    if plan_id and str(plan_id).isdigit():
        filas = filas.filter(plan_id=plan_id)
    if pago_pendiente:
        filas = filas.filter(Q(pedidos__estado=EstadoPedido.PENDIENTE.value)).distinct()
    return filas


def dias_aviso_tienda() -> int:
    from .models import ConfiguracionGlobal
    from ecommerce.domain.suscripciones import DIAS_AVISO_POR_DEFECTO
    config = ConfiguracionGlobal.objects.filter(pk=1).values('suscripciones_dias_aviso').first()
    return config['suscripciones_dias_aviso'] if config else DIAS_AVISO_POR_DEFECTO


def suscripciones_activas_en_tienda() -> bool:
    from .models import ConfiguracionGlobal
    return ConfiguracionGlobal.objects.filter(pk=1, suscripciones_activas=True).exists()


def hoy_local() -> date:
    return timezone.localdate()
