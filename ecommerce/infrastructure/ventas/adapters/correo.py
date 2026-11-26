"""Adaptadores SMTP (Django) de los puertos NotificadorPedidos, NotificadorCotizaciones y
NotificadorSuscripciones: correos al comprador (RF-04.2)."""

import logging
import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from ecommerce.application.cotizaciones import NotificadorCotizaciones
from ecommerce.application.suscripciones import NotificadorSuscripciones
from ecommerce.application.ventas import MOTIVO_PAGO_ANULADO, MOTIVO_PAGO_VENCIDO, NotificadorPedidos
from ecommerce.domain.empresa import DatosEmpresa
from ecommerce.domain.suscripciones import EventoSuscripcion, frecuencia_legible
from ecommerce.domain.logistica import DIRECCION_POR_ACORDAR, ENTREGA_COORDINADA, aviso_entrega_coordinada
from ecommerce.domain.ventas import EstadoPedido, EventoPedido

from ..enlaces_resena import url_resena
from ..instrucciones_pago import fecha_limite_pago, instrucciones_transferencia
from ..models import ConfiguracionGlobal, Cotizacion, OrdenCompra, Resena, Suscripcion

logger = logging.getLogger(__name__)

ASUNTOS = {
    EventoPedido.RECIBIDO: 'Recibimos tu pedido #{id}',
    EventoPedido.PAGO_APROBADO: 'Pago confirmado: pedido #{id}',
    EventoPedido.PAGO_EN_REVISION: 'Recibimos el pago de tu pedido #{id}',
    EventoPedido.PAGO_RECHAZADO: 'No se pudo completar el pago del pedido #{id}',
    EventoPedido.RECORDATORIO_PAGO: 'Recuerda pagar tu pedido #{id}',
    EventoPedido.CANCELADO: 'Tu pedido #{id} fue cancelado',
    EventoPedido.EN_PREPARACION: 'Estamos preparando tu pedido #{id}',
    EventoPedido.DESPACHADO: 'Tu pedido #{id} va en camino',
    EventoPedido.ENTREGADO: 'Tu pedido #{id} fue entregado',
}
# Con retiro en el local "despachado" significa que el pedido ya se puede retirar
ASUNTOS_RETIRO_LOCAL = {
    EventoPedido.DESPACHADO: 'Tu pedido #{id} está listo para retirar',
    EventoPedido.ENTREGADO: 'Retiraste tu pedido #{id}',
}


def pesos(valor) -> str:
    """Formato chileno: $12.990"""
    return f"${int(round(float(valor or 0))):,}".replace(',', '.')


class CorreoNotificadorPedidos(NotificadorPedidos):
    def notificar(self, orden_id, evento):
        # RF-04.2: no se avisan cambios que luego hagan rollback
        transaction.on_commit(lambda: self._enviar(orden_id, EventoPedido(evento)))

    def _enviar(self, orden_id, evento):
        try:
            orden = OrdenCompra.objects.select_related('usuario').prefetch_related('detalles').get(id=orden_id)
            destinatario = orden.email_invitado or (orden.usuario.email if orden.usuario else '')
            if not destinatario:
                logger.warning('La orden %s no tiene correo de contacto; no se envía %s', orden_id, evento)
                return
            contexto = self._contexto(orden)
            plantilla = f'ventas/correos/{evento.value.lower()}'
            asuntos = ASUNTOS_RETIRO_LOCAL if contexto['es_retiro_local'] else {}
            asunto = asuntos.get(evento, ASUNTOS[evento]).format(id=orden.id)
            correo = EmailMultiAlternatives(
                subject=f"{asunto} | {contexto['tienda']}",
                body=render_to_string(f'{plantilla}.txt', contexto),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[destinatario],
                # Si el comprador responde, le llega a la tienda: el remitente (ej. ventas@ con Resend) puede no
                # tener buzón. Sin correo de contacto, la respuesta va al remitente, como antes
                reply_to=[contexto['correo_contacto']] if contexto['correo_contacto'] else None,
            )
            correo.attach_alternative(render_to_string(f'{plantilla}.html', contexto), 'text/html')
            correo.send()
        except Exception:
            # El cambio de la orden ya quedó guardado: solo se registra (sin datos del comprador)
            logger.exception('No se pudo enviar el correo %s de la orden %s', evento, orden_id)

    @staticmethod
    def _contexto(orden):
        config = ConfiguracionGlobal.objects.filter(pk=1).first()
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        return {
            'tienda': config.nombre_tienda if config and config.nombre_tienda else 'Nuestra tienda',
            # A dónde llegan las respuestas del comprador (Configuración > Contacto y Redes)
            'correo_contacto': (config.correo_contacto or '').strip() if config else '',
            'orden': orden,
            'detalles': [{
                'nombre': detalle.nombre_producto_snapshot,
                'cantidad': detalle.cantidad,
                'precio_unitario': pesos(detalle.precio_unitario_snapshot),
                'total': pesos(detalle.precio_unitario_snapshot * detalle.cantidad),
            } for detalle in orden.detalles.all()],
            'subtotal': pesos(orden.subtotal),
            'costo_envio': pesos(orden.costo_envio),
            'total': pesos(orden.total_final),
            'metodo_pago': orden.get_metodo_pago_display(),
            'anulado_por_comprador': orden.motivo_cancelacion == MOTIVO_PAGO_ANULADO,
            'pago_vencido': orden.motivo_cancelacion == MOTIVO_PAGO_VENCIDO,
            # Horas que tuvo para transferir (el plazo de la tienda al crear la orden)
            'plazo_pago_horas': round((fecha_limite_pago(orden) - orden.fecha_creacion).total_seconds() / 3600),
            'es_retiro_local': orden.proveedor_logistico == 'RETIRO_LOCAL',
            'es_entrega_coordinada': orden.proveedor_logistico == ENTREGA_COORDINADA,
            # Cómo se coordina la entrega (lo escribe el admin); vacío si la entrega no es coordinada
            'aviso_entrega_coordinada': CorreoNotificadorPedidos._aviso_entrega_coordinada(orden, config),
            'transportista': (orden.proveedor_logistico or '').capitalize(),
            # Compra como empresa: [(etiqueta, valor)] con los datos para la factura; vacío si compró una persona
            'datos_factura': [(etiqueta, (orden.datos_empresa or {}).get(campo, ''))
                              for campo, etiqueta in DatosEmpresa.CAMPOS] if orden.datos_empresa else [],
            # Número de la orden de transporte (RF-02.3), si ya se generó
            'numero_ot': orden.numero_seguimiento_tracking or '',
            # Datos bancarios, monto y referencia si la orden se paga por transferencia (None si no)
            'transferencia': CorreoNotificadorPedidos._transferencia(orden),
            'entrega': CorreoNotificadorPedidos._entrega(orden, config),
            # RF-02.4: el invitado consulta con su número de orden y su correo
            'url_seguimiento': f'{frontend_url}/seguimiento?orden={orden.id}',
            'url_resena': CorreoNotificadorPedidos._url_resena(orden, config),
        }

    @staticmethod
    def _url_resena(orden, config):
        """Solo en el correo de entrega y con las reseñas activas; vacío si el pedido ya tiene reseña."""
        if not (config and config.resenas_activas) or orden.estado != EstadoPedido.ENTREGADO:
            return ''
        if Resena.objects.filter(orden_id=orden.id).exists():
            return ''
        return url_resena(orden.id)

    @staticmethod
    def _transferencia(orden):
        instrucciones = instrucciones_transferencia(orden)
        if instrucciones:
            instrucciones['monto'] = pesos(instrucciones['monto'])
            # Hora de Chile (TIME_ZONE), ej. 16-10-2026 a las 14:30
            instrucciones['vence'] = timezone.localtime(instrucciones['vence']).strftime('%d-%m-%Y a las %H:%M')
        return instrucciones

    @staticmethod
    def _aviso_entrega_coordinada(orden, config):
        if orden.proveedor_logistico != ENTREGA_COORDINADA:
            return ''
        return aviso_entrega_coordinada(config.instrucciones_entrega_coordinada if config else '')

    @staticmethod
    def _entrega(orden, config):
        direccion = orden.direccion_envio_snapshot or {}
        if orden.proveedor_logistico == 'RETIRO_LOCAL':
            partes = [config.calle_origen, config.numero_origen, config.comuna_origen] if config else []
            return 'Retiro en el local: ' + ' '.join(p for p in partes if p)
        texto = ' '.join(str(direccion.get(c) or '') for c in ('calle', 'numero')).strip()
        if direccion.get('dpto_casa') and not direccion.get('codigo_sucursal'):
            texto += f", {direccion['dpto_casa']}"
        if direccion.get('comuna'):
            texto += f", {direccion['comuna']}"
        if orden.proveedor_logistico == ENTREGA_COORDINADA:
            return f'Entrega coordinada: {texto or DIRECCION_POR_ACORDAR}'
        tipo = 'Retiro en sucursal' if direccion.get('codigo_sucursal') else 'Despacho a domicilio'
        proveedor = (orden.proveedor_logistico or '').capitalize()
        return f'{tipo} ({proveedor}): {texto}' if proveedor else f'{tipo}: {texto}'


class CorreoNotificadorCotizaciones(NotificadorCotizaciones):
    """Avisa a la tienda de una solicitud de cotización y le confirma al cliente que llegó."""

    def notificar_nueva(self, cotizacion_id):
        # Igual que los pedidos: no se avisa una solicitud que luego haga rollback
        transaction.on_commit(lambda: self._enviar(cotizacion_id))

    def _enviar(self, cotizacion_id):
        try:
            cotizacion = Cotizacion.objects.get(id=cotizacion_id)
            config = ConfiguracionGlobal.objects.filter(pk=1).first()
            tienda = config.nombre_tienda if config and config.nombre_tienda else 'Nuestra tienda'
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
            contexto = {
                'tienda': tienda, 'cotizacion': cotizacion, 'url_panel': f'{frontend_url}/admin',
                'detalle': self._detalle(cotizacion),
                'datos_factura': [(etiqueta, cotizacion.datos_empresa.get(campo, ''))
                                  for campo, etiqueta in DatosEmpresa.CAMPOS] if cotizacion.datos_empresa else [],
            }
            correos_tienda = self._correos_tienda(config)
            if correos_tienda:
                # Responder este correo le llega al cliente
                self._mandar('cotizacion_tienda', f'Nueva solicitud de cotización #{cotizacion.id} | {tienda}',
                             contexto, correos_tienda, responder_a=[cotizacion.correo])
            else:
                logger.warning('La tienda no tiene correo de contacto ni administradores: la cotización %s '
                               'solo queda en el panel', cotizacion_id)
            self._mandar('cotizacion_recibida', f'Recibimos tu solicitud de cotización #{cotizacion.id} | {tienda}',
                         contexto, [cotizacion.correo], responder_a=correos_tienda[:1])
        except Exception:
            # La solicitud ya quedó guardada y se ve en el panel: solo se registra (sin datos del cliente)
            logger.exception('No se pudo enviar el aviso de la cotización %s', cotizacion_id)

    @staticmethod
    def _mandar(plantilla, asunto, contexto, para, responder_a):
        correo = EmailMultiAlternatives(
            subject=asunto, body=render_to_string(f'ventas/correos/{plantilla}.txt', contexto),
            from_email=settings.DEFAULT_FROM_EMAIL, to=para, reply_to=responder_a or None,
        )
        correo.attach_alternative(render_to_string(f'ventas/correos/{plantilla}.html', contexto), 'text/html')
        correo.send()

    @staticmethod
    def _correos_tienda(config):
        """El correo de contacto de la tienda; si no lo cargó, el de sus administradores."""
        if config and config.correo_contacto:
            return [config.correo_contacto]
        return list(get_user_model().objects.filter(rol='ADMIN', is_active=True)
                    .exclude(email='').order_by('id').values_list('email', flat=True))

    @staticmethod
    def _detalle(cotizacion):
        filas = [('Producto', cotizacion.producto_nombre or 'Descrito por el cliente')]
        if cotizacion.descripcion:
            filas.append(('Qué necesita', cotizacion.descripcion))
        filas.append(('Cantidad', str(cotizacion.cantidad)))
        if cotizacion.personalizacion:
            filas.append(('Personalización', cotizacion.personalizacion))
        if cotizacion.fecha_requerida:
            filas.append(('Lo necesita para el', cotizacion.fecha_requerida.strftime('%d-%m-%Y')))
        # Las fotos no van en el correo: son privadas y se ven solo en el panel de la tienda
        cantidad_fotos = cotizacion.fotos.count()
        if cantidad_fotos:
            filas.append(('Fotos', f"{cantidad_fotos} {'adjunta' if cantidad_fotos == 1 else 'adjuntas'}"))
        filas += [('Nombre', cotizacion.nombre), ('Correo', cotizacion.correo), ('Teléfono', cotizacion.telefono)]
        return filas



MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
         'noviembre', 'diciembre')


def fecha_larga(fecha) -> str:
    """11 de noviembre de 2026"""
    return f'{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}' if fecha else ''


ASUNTOS_SUSCRIPCION = {
    EventoSuscripcion.ACTIVADA: 'Tu suscripción {plan} está activa',
    EventoSuscripcion.AVISO_COBRO: 'Paga tu próxima entrega de {plan}',
    EventoSuscripcion.CICLO_NO_PAGADO: 'No recibimos el pago de tu entrega de {plan}',
    EventoSuscripcion.PAUSADA: 'Pausaste tu suscripción {plan}',
    EventoSuscripcion.REANUDADA: 'Reanudaste tu suscripción {plan}',
    EventoSuscripcion.CANCELADA: 'Cancelaste tu suscripción {plan}',
    EventoSuscripcion.NO_ACTIVADA: 'Tu suscripción {plan} no se activó',
}


class CorreoNotificadorSuscripciones(NotificadorSuscripciones):
    """Hitos de la suscripción. El pago aprobado o rechazado de cada ciclo lo avisa el correo del pedido."""

    def notificar(self, suscripcion_id, evento, orden_id=None):
        # Como los pedidos: no se avisa un cambio que luego haga rollback
        transaction.on_commit(lambda: self._enviar(suscripcion_id, EventoSuscripcion(evento), orden_id))

    def _enviar(self, suscripcion_id, evento, orden_id):
        try:
            suscripcion = Suscripcion.objects.select_related('plan', 'usuario').get(id=suscripcion_id)
            if not suscripcion.usuario.email:
                return
            contexto = self._contexto(suscripcion, orden_id)
            plantilla = f'ventas/correos/suscripcion_{evento.value.lower()}'
            asunto = ASUNTOS_SUSCRIPCION[evento].format(plan=suscripcion.plan.nombre)
            correo = EmailMultiAlternatives(
                subject=f"{asunto} | {contexto['tienda']}",
                body=render_to_string(f'{plantilla}.txt', contexto),
                from_email=settings.DEFAULT_FROM_EMAIL, to=[suscripcion.usuario.email],
                reply_to=[contexto['correo_contacto']] if contexto['correo_contacto'] else None,
            )
            correo.attach_alternative(render_to_string(f'{plantilla}.html', contexto), 'text/html')
            correo.send()
        except Exception:
            logger.exception('No se pudo enviar el correo %s de la suscripción %s', evento, suscripcion_id)

    @staticmethod
    def _contexto(suscripcion, orden_id):
        config = ConfiguracionGlobal.objects.filter(pk=1).first()
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        orden = OrdenCompra.objects.prefetch_related('detalles').filter(pk=orden_id).first() if orden_id else None
        contexto = {
            'tienda': config.nombre_tienda if config and config.nombre_tienda else 'Nuestra tienda',
            'correo_contacto': (config.correo_contacto or '').strip() if config else '',
            'suscripcion': suscripcion,
            'plan': suscripcion.plan,
            'frecuencia': frecuencia_legible(suscripcion.plan.frecuencia_semanas).lower(),
            'producto': suscripcion.nombre_producto,
            'unidades': suscripcion.plan.unidades,
            'proxima_entrega': fecha_larga(suscripcion.proxima_entrega),
            'url_suscripciones': f'{frontend_url}/mis-suscripciones',
            'orden': orden,
        }
        if orden is not None:
            contexto.update({
                'total': pesos(orden.total_final),
                'costo_envio': pesos(orden.costo_envio),
                'fecha_ciclo': fecha_larga(orden.ciclo_fecha),
                'url_pagar': f'{frontend_url}/mis-suscripciones/pagar/{orden.id}',
                'transferencia': CorreoNotificadorPedidos._transferencia(orden),
                'entrega': CorreoNotificadorPedidos._entrega(orden, config),
            })
        return contexto
