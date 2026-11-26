"""API de suscripciones (pedido de un cliente, opcional y apagado por defecto). Vistas delgadas: validan la entrada,
llaman a los casos de uso (ecommerce/application/suscripciones.py) y serializan la respuesta.

- Pública: planes activos y qué se puede elegir en cada uno (404 con el módulo apagado).
- Cliente con sesión: suscribirse, Mis suscripciones (acciones y cambios) y pagar un pedido propio pendiente.
- Panel: planes (crear, editar, ordenar, borrar sin suscripciones) y la lista de suscriptores.
"""

from bson import ObjectId
from bson.errors import InvalidId
from django.db import transaction
from django.db.models import Q
from rest_framework import status
from rest_framework.exceptions import NotFound, NotAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.application.pagos import ErrorPasarelaPago
from ecommerce.application.suscripciones import (
    CambiosSuscripcion, Entrega, ErrorSuscripcion, SolicitudSuscripcion, SuscripcionNoEncontrada,
)
from ecommerce.domain.suscripciones import (
    ESTADOS_DE_ACCION, ETIQUETAS_ESTADO_SUSCRIPCION, AccionNoPermitida, AccionSuscripcion, DatosPlan,
    EstadoSuscripcion, PlanInvalido, frecuencia_legible,
)
from ecommerce.domain.ventas import (
    EstadoPedido, NombreInvalido, TelefonoInvalido, normalizar_nombre_persona, normalizar_telefono_chile,
)

from ..catalogo.documents import Producto
from .acceso_exclusivos import AVISO_EXCLUSIVO, exigir_acceso_productos, planes_vigentes_de, productos_sin_acceso
from ..catalogo.images import url_imagen
from ..usuarios.permissions import IsAdministrador
from .instrucciones_pago import instrucciones_transferencia
from .models import OrdenCompra, PlanSuscripcion, Suscripcion
from .pasarelas import PASARELAS, pasarela, urls_pasarela
from .repositorio_suscripciones import (
    dias_aviso_tienda, hoy_local, suscripciones_activas_en_tienda, suscripciones_del_panel,
)
from .servicio_suscripciones import acciones_suscripcion, suscribirse

CAMPOS_PLAN = ('nombre', 'descripcion', 'precio', 'frecuencia_semanas', 'unidades', 'beneficios', 'categorias',
               'productos', 'envio_gratis', 'envio_gratis_compras', 'descuento', 'activo')
# Lo que ve el público de un plan (sin los productos elegibles: esos se piden aparte, con sus variantes)
CAMPOS_PLAN_PUBLICO = ('id', 'nombre', 'descripcion', 'precio', 'frecuencia_semanas', 'unidades', 'beneficios',
                       'envio_gratis', 'envio_gratis_compras', 'descuento')
LIMITE_OPCIONES = 100
CAMPOS_DIRECCION = ('calle', 'numero', 'dpto_casa', 'comuna', 'ciudad', 'region', 'codigo_sucursal', 'referencia')


def _error(mensaje, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': str(mensaje)}, status=codigo)


def exigir_modulo_activo():
    """Con el módulo apagado, la página y lo que se ofrece al público no existen (404)."""
    if not suscripciones_activas_en_tienda():
        raise NotFound('Esta página no está disponible.')


def plan_json(plan: PlanSuscripcion, publico=True) -> dict:
    campos = CAMPOS_PLAN_PUBLICO if publico else ('id', *CAMPOS_PLAN, 'orden')
    datos = {campo: getattr(plan, campo) for campo in campos}
    datos['frecuencia_texto'] = frecuencia_legible(plan.frecuencia_semanas)
    if not publico:
        datos['suscripciones'] = getattr(plan, 'total_suscripciones', None)
    return datos


def _texto_entrega(fila: Suscripcion) -> str:
    direccion = fila.direccion_envio or {}
    if fila.proveedor_logistico == 'RETIRO_LOCAL':
        return 'Retiro en el local'
    texto = ' '.join(str(direccion.get(c) or '') for c in ('calle', 'numero')).strip()
    if direccion.get('comuna'):
        texto = f"{texto}, {direccion['comuna']}" if texto else direccion['comuna']
    if fila.proveedor_logistico == 'ENTREGA_COORDINADA':
        return f'Entrega coordinada: {texto}' if texto else 'Entrega coordinada'
    return f'{fila.proveedor_logistico.capitalize()}: {texto}' if texto else fila.proveedor_logistico.capitalize()


def _pedido_pendiente(fila: Suscripcion):
    orden = fila.pedidos.filter(estado=EstadoPedido.PENDIENTE.value).order_by('ciclo_fecha', 'id').first()
    if orden is None:
        return None
    return {'orden_id': orden.id, 'total': int(round(orden.total_final)), 'ciclo_fecha': orden.ciclo_fecha,
            'metodo_pago': orden.metodo_pago}


def suscripcion_json(fila: Suscripcion, panel=False) -> dict:
    estado = EstadoSuscripcion(fila.estado)
    datos = {
        'id': fila.id,
        'plan': plan_json(fila.plan),
        'estado': estado.value,
        'estado_texto': ETIQUETAS_ESTADO_SUSCRIPCION[estado],
        'producto_mongo_id': fila.producto_mongo_id,
        'variante_sku': fila.variante_sku,
        'producto': fila.nombre_producto,
        'entrega': {
            'proveedor_logistico': fila.proveedor_logistico,
            'direccion_envio_snapshot': fila.direccion_envio or {},
            'nombre_destinatario': fila.nombre_destinatario,
            'telefono_destinatario': fila.telefono_destinatario,
            'texto': _texto_entrega(fila),
        },
        'metodo_pago': fila.metodo_pago,
        'proxima_entrega': fila.proxima_entrega,
        'fecha_creacion': fila.fecha_creacion,
        'pedido_pendiente': _pedido_pendiente(fila),
        # Qué botones mostrar en Mi cuenta (el servidor igual valida cada acción)
        'acciones': [accion.value for accion in AccionSuscripcion if estado in ESTADOS_DE_ACCION[accion]],
    }
    if panel:
        usuario = fila.usuario
        datos['cliente'] = {'nombre': f'{usuario.nombre} {usuario.apellido_paterno}'.strip(), 'email': usuario.email}
        datos['motivo_cancelacion'] = fila.motivo_cancelacion
    return datos


def iniciar_pago(orden: OrdenCompra, request) -> dict:
    """Lo que necesita el navegador para pagar un pedido pendiente: la URL de la pasarela, o los datos para transferir.
    Lanza ErrorPasarelaPago si la pasarela no responde."""
    from .views import token_verificacion_pago
    respuesta = {'orden_id': orden.id, 'total': int(round(orden.total_final)),
                 'token_verificacion': token_verificacion_pago(orden.id)}
    if orden.metodo_pago in PASARELAS:
        url_retorno, url_aviso = urls_pasarela(orden.metodo_pago, request)
        pago = pasarela(orden.metodo_pago).iniciar(str(orden.id), orden.total_final, url_retorno, url_aviso)
        OrdenCompra.objects.filter(pk=orden.id).update(id_transaccion_pasarela=pago.referencia)
        respuesta['url_pago'] = pago.url_pago
    instrucciones = instrucciones_transferencia(orden)
    if instrucciones:
        respuesta['instrucciones_pago'] = instrucciones
    return respuesta


def _entrega(datos) -> Entrega:
    """La entrega que envía el formulario, con el nombre y el teléfono normalizados (RF-02.3)."""
    if not isinstance(datos, dict):
        raise ErrorSuscripcion('Indica cómo quieres recibir tus entregas.')
    direccion = datos.get('direccion_envio_snapshot') or {}
    if not isinstance(direccion, dict):
        raise ErrorSuscripcion('La dirección no es válida.')
    # Solo los campos de una dirección: nada más se guarda
    direccion = {campo: str(direccion.get(campo) or '').strip()[:255] for campo in CAMPOS_DIRECCION
                 if direccion.get(campo)}
    destinatario, telefono = str(datos.get('nombre_destinatario') or '').strip(), ''
    try:
        if destinatario:
            destinatario = normalizar_nombre_persona(destinatario)
        if datos.get('telefono_destinatario'):
            telefono = normalizar_telefono_chile(datos.get('telefono_destinatario'))
    except (NombreInvalido, TelefonoInvalido) as error:
        raise ErrorSuscripcion(str(error)) from error
    return Entrega(str(datos.get('proveedor_logistico') or '').strip().upper(), direccion, destinatario, telefono)


# ---------- Público ----------

class PlanesPublicosView(APIView):
    """GET /api/ventas/suscripciones/planes/: los planes activos, en el orden del admin."""
    permission_classes = [AllowAny]

    def get(self, request):
        exigir_modulo_activo()
        planes = PlanSuscripcion.objects.filter(activo=True).order_by('orden', 'id')
        return Response({'planes': [plan_json(plan) for plan in planes], 'dias_aviso': dias_aviso_tienda()})


class OpcionesPlanView(APIView):
    """GET /api/ventas/suscripciones/planes/<id>/opciones/: los productos elegibles con sus variantes y si alcanzan
    para una entrega (stock por variante, RN-03)."""
    permission_classes = [AllowAny]

    def get(self, request, pk):
        exigir_modulo_activo()
        plan = PlanSuscripcion.objects.filter(pk=pk, activo=True).first()
        if plan is None:
            raise NotFound('Ese plan no está disponible.')
        propia = None
        if 'suscripcion_id' in request.query_params:
            if not request.user.is_authenticated:
                raise NotAuthenticated()
            identificador = request.query_params['suscripcion_id']
            if not identificador.isdigit():
                raise NotFound()
            propia = _propia(request, int(identificador))
            if propia.plan_id != plan.id:
                raise NotFound()
        ids = []
        for valor in plan.productos or []:
            try:
                ids.append(ObjectId(valor))
            except (InvalidId, TypeError):
                continue
        categorias = [c for c in (plan.categorias or []) if c]
        filtro = {'$or': []}
        if ids:
            filtro['$or'].append({'_id': {'$in': ids}})
        for categoria in categorias:
            filtro['$or'].append({'categoria': {'$regex': f'^{_escapar(categoria)}$', '$options': 'i'}})
        if not filtro['$or']:
            return Response({'productos': []})
        productos = (Producto.objects(activo=True, publicado=True, coleccion_privada__ne=True)
                     .filter(__raw__=filtro).order_by('nombre')[:LIMITE_OPCIONES])
        productos = list(productos)
        restringidos = productos_sin_acceso(productos, request.user, plan.id,
                                           contratando=propia is None, suscripcion=propia)
        return Response({'productos': [{
            'id': str(producto.id),
            'nombre': producto.nombre,
            'categoria': producto.categoria,
            'descripcion': producto.descripcion or '',
            'imagen': url_imagen(producto.imagenes[0], request) if producto.imagenes else None,
            'solo_suscriptores': producto.solo_suscriptores,
            'requiere_suscripcion': str(producto.id) in restringidos,
            'aviso_exclusivo': AVISO_EXCLUSIVO if str(producto.id) in restringidos else '',
            'variantes': [{
                'sku': variante.sku,
                'atributos': variante.atributos_variables or {},
                'disponible': int(variante.stock) >= plan.unidades and str(producto.id) not in restringidos,
            } for variante in producto.variantes],
        } for producto in productos]})


def _escapar(texto: str) -> str:
    import re
    return re.escape(texto)


# ---------- Cliente con sesión ----------

class SuscribirseView(APIView):
    """POST /api/ventas/suscripciones/: crea la suscripción Pendiente con el pedido del primer ciclo e inicia su pago.

    Del navegador solo se toman el plan, la variante, la entrega, el medio de pago y la aceptación de los términos:
    el estado, las fechas y el precio los fija el servidor.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        exigir_modulo_activo()
        datos = request.data
        try:
            solicitud = SolicitudSuscripcion(
                plan_id=datos.get('plan_id'), producto_id=str(datos.get('producto_mongo_id') or ''),
                sku=str(datos.get('variante_sku') or ''), entrega=_entrega(datos),
                metodo_pago=str(datos.get('metodo_pago') or '').strip().upper(),
                acepta_terminos=datos.get('acepta_terminos') is True)
            exigir_acceso_productos([datos], request.user,
                                   int(datos['plan_id']) if str(datos.get('plan_id', '')).isdigit() else None,
                                   contratando=True)
            with transaction.atomic():
                iniciada = suscribirse().ejecutar(request.user.id, solicitud, hoy_local(), dias_aviso_tienda())
                orden = OrdenCompra.objects.get(pk=iniciada.orden_id)
                respuesta = iniciar_pago(orden, request)
        except ErrorSuscripcion as error:
            return _error(error)
        except ErrorPasarelaPago as error:
            # El rollback deshace la suscripción y su pedido: puede intentarlo de nuevo
            return _error(f'No se pudo iniciar el pago: {error}', status.HTTP_502_BAD_GATEWAY)
        return Response({'suscripcion_id': iniciada.suscripcion_id, **respuesta}, status=status.HTTP_201_CREATED)


class MisSuscripcionesView(APIView):
    """GET /api/ventas/suscripciones/mias/: las suscripciones del cliente (también con el módulo apagado, para que
    pueda cancelarlas)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        filas = Suscripcion.objects.select_related('plan').filter(usuario=request.user).order_by('-fecha_creacion')
        return Response({'suscripciones': [suscripcion_json(fila) for fila in filas],
                         'activas_en_tienda': suscripciones_activas_en_tienda()})


def _propia(request, pk) -> Suscripcion:
    fila = Suscripcion.objects.select_related('plan').filter(pk=pk, usuario=request.user).first()
    if fila is None:
        raise NotFound('No encontramos esa suscripción.')
    return fila


class SuscripcionView(APIView):
    """GET y PATCH /api/ventas/suscripciones/<id>/: una suscripción propia y cambiar lo que recibe, la entrega o el
    medio de pago (rige desde el próximo pedido)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        return Response(suscripcion_json(_propia(request, pk)))

    def patch(self, request, pk):
        propia = _propia(request, pk)
        datos = request.data
        if 'producto_mongo_id' in datos or 'variante_sku' in datos:
            exigir_acceso_productos([{'producto_mongo_id': datos.get('producto_mongo_id', propia.producto_mongo_id)}],
                                   request.user, propia.plan_id, suscripcion=propia)
        try:
            cambios = CambiosSuscripcion(
                producto_id=str(datos['producto_mongo_id']) if 'producto_mongo_id' in datos else None,
                sku=str(datos['variante_sku']) if 'variante_sku' in datos else None,
                entrega=_entrega(datos['entrega']) if 'entrega' in datos else None,
                metodo_pago=str(datos['metodo_pago']).strip().upper() if 'metodo_pago' in datos else None)
            with transaction.atomic():
                acciones_suscripcion().cambiar(request.user.id, pk, cambios)
        except SuscripcionNoEncontrada as error:
            return _error(error, status.HTTP_404_NOT_FOUND)
        except (ErrorSuscripcion, AccionNoPermitida) as error:
            return _error(error)
        return Response(suscripcion_json(_propia(request, pk)))


class AccionSuscripcionView(APIView):
    """POST /api/ventas/suscripciones/<id>/<accion>/: pausar, reanudar, saltar, adelantar o cancelar."""
    permission_classes = [IsAuthenticated]
    ACCIONES = {'pausar', 'reanudar', 'saltar', 'adelantar', 'cancelar'}

    def post(self, request, pk, accion):
        if accion not in self.ACCIONES:
            raise NotFound()
        _propia(request, pk)
        caso = acciones_suscripcion()
        usuario, hoy = request.user.id, hoy_local()
        try:
            with transaction.atomic():
                if accion == 'pausar':
                    caso.pausar(usuario, pk)
                elif accion == 'reanudar':
                    caso.reanudar(usuario, pk, hoy, dias_aviso_tienda())
                elif accion == 'saltar':
                    caso.saltar(usuario, pk)
                elif accion == 'adelantar':
                    caso.adelantar(usuario, pk, hoy)
                else:
                    caso.cancelar(usuario, pk)
        except SuscripcionNoEncontrada as error:
            return _error(error, status.HTTP_404_NOT_FOUND)
        except (ErrorSuscripcion, AccionNoPermitida) as error:
            return _error(error)
        return Response(suscripcion_json(_propia(request, pk)))


class BeneficiosView(APIView):
    """GET /api/ventas/suscripciones/beneficios/: el descuento y el envío gratis que tiene el comprador en sus compras
    mientras su suscripción esté activa (el checkout los muestra; el servidor los vuelve a calcular al comprar)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .serializers import beneficios_del_comprador
        beneficios = beneficios_del_comprador(request)
        return Response({'descuento': beneficios.descuento, 'envio_gratis': beneficios.envio_gratis})


class AccesoExclusivosView(APIView):
    """Planes vigentes de la propia cuenta para mostrar el acceso, sin cambiar el contrato de beneficios."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'planes_vigentes': sorted(planes_vigentes_de(request.user))
                         if suscripciones_activas_en_tienda() else []})


class PagarPedidoView(APIView):
    """POST /api/ventas/mis-pedidos/<id>/pagar/: inicia el pago de un pedido propio que sigue Pendiente (el enlace
    "Pagar esta entrega" del aviso de cobro). Con transferencia devuelve los datos para transferir."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        orden = OrdenCompra.objects.filter(pk=pk, usuario=request.user).first()
        if orden is None:
            raise NotFound('No encontramos ese pedido.')
        if orden.estado != EstadoPedido.PENDIENTE.value:
            return _error('Este pedido ya no está pendiente de pago.', status.HTTP_409_CONFLICT)
        try:
            return Response(iniciar_pago(orden, request))
        except ErrorPasarelaPago as error:
            return _error(f'No se pudo iniciar el pago: {error}', status.HTTP_502_BAD_GATEWAY)


# ---------- Panel ----------

def _datos_plan(request) -> DatosPlan:
    return DatosPlan.desde({campo: request.data.get(campo) for campo in CAMPOS_PLAN if campo in request.data})


def _guardar_plan(plan: PlanSuscripcion, datos: DatosPlan) -> PlanSuscripcion:
    for campo in CAMPOS_PLAN:
        valor = getattr(datos, campo)
        setattr(plan, campo, list(valor) if isinstance(valor, tuple) else valor)
    plan.save()
    return plan


class AdminPlanesView(APIView):
    """GET y POST /api/ventas/admin/suscripciones/planes/: todos los planes (activos o no) y crear uno."""
    permission_classes = [IsAdministrador]

    def get(self, request):
        from django.db.models import Count
        planes = PlanSuscripcion.objects.annotate(total_suscripciones=Count('suscripciones')).order_by('orden', 'id')
        return Response({'planes': [plan_json(plan, publico=False) for plan in planes]})

    def post(self, request):
        try:
            datos = _datos_plan(request)
        except PlanInvalido as error:
            return Response({'errores': error.errores}, status=status.HTTP_400_BAD_REQUEST)
        ultimo = PlanSuscripcion.objects.order_by('-orden').values_list('orden', flat=True).first()
        plan = _guardar_plan(PlanSuscripcion(orden=(ultimo or 0) + 1), datos)
        return Response(plan_json(plan, publico=False), status=status.HTTP_201_CREATED)


class AdminPlanView(APIView):
    """PUT y DELETE /api/ventas/admin/suscripciones/planes/<id>/. Un plan con suscripciones no se borra: se desactiva."""
    permission_classes = [IsAdministrador]

    def _plan(self, pk):
        plan = PlanSuscripcion.objects.filter(pk=pk).first()
        if plan is None:
            raise NotFound('Ese plan no existe.')
        return plan

    def put(self, request, pk):
        plan = self._plan(pk)
        try:
            datos = _datos_plan(request)
        except PlanInvalido as error:
            return Response({'errores': error.errores}, status=status.HTTP_400_BAD_REQUEST)
        return Response(plan_json(_guardar_plan(plan, datos), publico=False))

    def delete(self, request, pk):
        plan = self._plan(pk)
        if plan.suscripciones.exists():
            return _error('Este plan tiene suscripciones: desactívalo en vez de borrarlo, así nadie más se suscribe y '
                          'las actuales siguen igual.', status.HTTP_409_CONFLICT)
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminOrdenPlanesView(APIView):
    """PUT /api/ventas/admin/suscripciones/planes/orden/ {ids: [...]}: el orden en que la página muestra los planes."""
    permission_classes = [IsAdministrador]

    def put(self, request):
        ids = request.data.get('ids')
        existentes = set(PlanSuscripcion.objects.values_list('id', flat=True))
        if (not isinstance(ids, list) or not all(isinstance(i, int) for i in ids) or len(set(ids)) != len(ids)
                or set(ids) != existentes):
            return _error('Envía todos los planes, cada uno una vez.')
        with transaction.atomic():
            for posicion, plan_id in enumerate(ids, start=1):
                PlanSuscripcion.objects.filter(pk=plan_id).update(orden=posicion)
        return Response({'ids': ids})


class PaginacionSuscriptores(PageNumberPagination):
    page_size = 20
    page_query_param = 'pagina'


class AdminSuscripcionesView(APIView):
    """GET /api/ventas/admin/suscripciones/?estado=&plan=&pago_pendiente=1&buscar=&pagina=N: los suscriptores."""
    permission_classes = [IsAdministrador]

    def get(self, request):
        estado = request.query_params.get('estado', '')
        if estado and estado not in {e.value for e in EstadoSuscripcion}:
            return _error('Ese estado no existe.')
        filas = suscripciones_del_panel(estado, request.query_params.get('plan', ''),
                                        request.query_params.get('pago_pendiente') in ('1', 'true'))
        buscar = request.query_params.get('buscar', '').strip()
        if buscar:
            filas = filas.filter(Q(usuario__email__icontains=buscar) | Q(usuario__nombre__icontains=buscar)
                                 | Q(nombre_producto__icontains=buscar))
        paginador = PaginacionSuscriptores()
        pagina = paginador.paginate_queryset(filas, request, view=self)
        return paginador.get_paginated_response([suscripcion_json(fila, panel=True) for fila in pagina])
