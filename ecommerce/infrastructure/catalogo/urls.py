from django.urls import path
from .views import (
    FiltrosCatalogoView,
    ProductoDetailView,
    ProductoEnlaceImagenView,
    ProductoImagenDetailView,
    ProductoImagenListCreateView,
    ProductoListCreateView,
    VitrinaView,
)
from .views_categorias import CategoriasView, RenombrarCategoriaView

catalogo_urlpatterns = [
    path('productos/', ProductoListCreateView.as_view(), name='lista_productos'),
    path('filtros/', FiltrosCatalogoView.as_view(), name='filtros_catalogo'),
    # GET /api/catalogo/vitrina/: más vendidos y últimos agregados para la landing (pública)
    path('vitrina/', VitrinaView.as_view(), name='vitrina'),
    # Panel: renombrar o unir categorías (RF-03.2)
    path('categorias/', CategoriasView.as_view(), name='categorias_catalogo'),
    path('categorias/renombrar/', RenombrarCategoriaView.as_view(), name='renombrar_categoria'),
    
    path('productos/<str:id>/', ProductoDetailView.as_view(), name='detalle_producto'),
    path('productos/<str:id>/imagenes/', ProductoImagenListCreateView.as_view(), name='imagenes_producto'),
    # Antes que <imagen_id>, que también aceptaría "enlace"
    path('productos/<str:id>/imagenes/enlace/', ProductoEnlaceImagenView.as_view(), name='enlace_imagen_producto'),
    path('productos/<str:id>/imagenes/<str:imagen_id>/', ProductoImagenDetailView.as_view(), name='detalle_imagen_producto'),
]
