"""Listado mensual y registro idempotente del regalo anual, solo para el panel."""
from django.contrib.auth import get_user_model
from django.db.models import Exists, F, OuterRef, Prefetch
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.domain.suscripciones import EstadoSuscripcion
from ecommerce.infrastructure.usuarios.permissions import IsAdministrador
from .models import RegaloCumpleanos, Suscripcion
from .repositorio_suscripciones import hoy_local
from .views_suscripciones import PaginacionSuscriptores, _texto_entrega, exigir_modulo_activo


class AdminCumpleanosView(APIView):
    permission_classes = [IsAdministrador]

    def get(self, request):
        exigir_modulo_activo()
        hoy = hoy_local()
        try:
            mes = int(request.query_params.get('mes', hoy.month))
            if not 1 <= mes <= 12:
                raise ValueError
        except (ValueError, TypeError):
            raise ValidationError({'mes': 'Elige un mes entre enero y diciembre.'}) from None
        entregas = Suscripcion.objects.filter(estado=EstadoSuscripcion.ACTIVA.value).select_related('plan').order_by(
            F('proxima_entrega').asc(nulls_last=True), 'id')
        usuarios = get_user_model().objects.filter(
            cumpleanos_mes=mes, is_active=True, suscripciones__estado=EstadoSuscripcion.ACTIVA.value,
        ).distinct().annotate(regalo_enviado=Exists(RegaloCumpleanos.objects.filter(
            usuario_id=OuterRef('pk'), anio=hoy.year))).prefetch_related(
                Prefetch('suscripciones', queryset=entregas, to_attr='entregas_cumpleanos')
        ).order_by('cumpleanos_dia', 'nombre', 'pk')
        paginador = PaginacionSuscriptores()
        pagina = paginador.paginate_queryset(usuarios, request, view=self)
        filas = []
        for usuario in pagina:
            proxima = usuario.entregas_cumpleanos[0]
            filas.append({
                'usuario_id': usuario.id, 'nombre': f'{usuario.nombre} {usuario.apellido_paterno}'.strip(),
                'dia': usuario.cumpleanos_dia, 'mes': usuario.cumpleanos_mes,
                'direccion': _texto_entrega(proxima), 'direccion_envio': proxima.direccion_envio,
                'destinatario': proxima.nombre_destinatario, 'plan': proxima.plan.nombre,
                'proxima_entrega': proxima.proxima_entrega, 'regalo_enviado': usuario.regalo_enviado,
            })
        respuesta = paginador.get_paginated_response(filas)
        respuesta.data.update(mes=mes, anio=hoy.year)
        return respuesta


class AdminRegaloCumpleanosView(APIView):
    permission_classes = [IsAdministrador]

    def post(self, request, usuario_id):
        exigir_modulo_activo()
        usuario = get_user_model().objects.filter(
            pk=usuario_id, is_active=True, cumpleanos_dia__isnull=False, cumpleanos_mes__isnull=False,
            suscripciones__estado=EstadoSuscripcion.ACTIVA.value,
        ).first()
        if usuario is None:
            raise NotFound('No encontramos un suscriptor vigente con cumpleaños registrado.')
        anio = hoy_local().year
        regalo, creado = RegaloCumpleanos.objects.get_or_create(
            usuario=usuario, anio=anio, defaults={'enviado_por': request.user})
        return Response({'usuario_id': usuario.id, 'anio': anio, 'regalo_enviado': True,
                         'fecha_envio': regalo.fecha_envio},
                        status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK)
