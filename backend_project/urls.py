"""
URL configuration for backend_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from ecommerce.infrastructure.usuarios.urls import usuarios_urlpatterns
from ecommerce.infrastructure.ventas.urls import (
    configuracion_urlpatterns,
    ventas_urlpatterns,
)
from ecommerce.infrastructure.catalogo.urls import catalogo_urlpatterns
from ecommerce.infrastructure.salud import salud
from django.http import JsonResponse

def bienvenida_api(request):
    return JsonResponse({
        "mensaje": "mensaje de prueba, la api esta corriendo correctamente",
        "estado": "Online",
        "version": "1.0"
    })

urlpatterns = [
    path('', bienvenida_api, name='bienvenida_api'),
    # Healthcheck de Docker y del monitor externo: 200 si PostgreSQL y MongoDB responden, 503 si no
    path('api/salud/', salud, name='salud'),
    path('api/configuracion/', include(configuracion_urlpatterns)),
    path('admin/', admin.site.urls),
    path('api/usuarios/', include(usuarios_urlpatterns)),
    path('api/ventas/', include(ventas_urlpatterns)),
    path('api/catalogo/', include(catalogo_urlpatterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
