"""API del panel para renombrar o unir categorías (RF-03.2). Vistas delgadas: el caso de uso decide."""

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from ecommerce.application.categorias import RenombrarCategoria
from ecommerce.domain.categorias import CategoriaInvalida
from ecommerce.infrastructure.usuarios.permissions import IsAdministrador
from ecommerce.infrastructure.ventas.repositorio_categorias import DjangoReferenciasCategorias

from .repositorio_categorias import MongoCategoriasCatalogo
from .views import CatalogoAPIView


def _categorias_json():
    return [{'nombre': c.nombre, 'productos': c.productos, 'publicados': c.publicados}
            for c in MongoCategoriasCatalogo().listar()]


class CategoriasView(CatalogoAPIView):
    """GET /api/catalogo/categorias/: las categorías con cuántos productos tienen (también los borradores)."""
    permission_classes = [IsAdministrador]

    def get(self, request):
        return Response({'categorias': _categorias_json()})


class RenombrarCategoriaView(CatalogoAPIView):
    """POST /api/catalogo/categorias/renombrar/ {desde, hacia}: renombra una categoría en todos sus productos; si `hacia`
    es otra que ya existe (sin distinguir mayúsculas), las une."""
    permission_classes = [IsAdministrador]

    def post(self, request):
        desde = request.data.get('desde')
        if not isinstance(desde, str) or not desde:
            return Response({'detail': 'Elige la categoría que quieres renombrar.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            # Las referencias de PostgreSQL cambian juntas; los productos, después (ver el caso de uso)
            with transaction.atomic():
                resultado = RenombrarCategoria(MongoCategoriasCatalogo(), DjangoReferenciasCategorias()).ejecutar(
                    desde, request.data.get('hacia'))
        except CategoriaInvalida as error:
            return Response({'detail': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'desde': resultado.desde, 'hacia': resultado.hacia, 'une': resultado.une,
                         'productos': resultado.productos, 'categorias': _categorias_json()})
