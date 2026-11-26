from django.urls import path
from . import views
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import RegistroView, GoogleLoginView
usuarios_urlpatterns = [
    #Endpoint para el registro de usuarios
    path('registro/', RegistroView.as_view(), name='registro'),
    #acceso a los tokens JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    #Endpoint para el login con Google
    path('google/', GoogleLoginView.as_view(), name='google_login'),
    path('me/', views.UsuarioActualAPIView.as_view(), name='usuario_actual'),
    path('cumpleanos/', views.CumpleanosAPIView.as_view(), name='mi-cumpleanos'),
    # Recuperar la contraseña por correo y cambiarla con la sesión iniciada
    path('contrasena/olvido/', views.OlvidoContrasenaView.as_view(), name='contrasena_olvido'),
    path('contrasena/restablecer/', views.RestablecerContrasenaView.as_view(), name='contrasena_restablecer'),
    path('contrasena/cambiar/', views.CambiarContrasenaView.as_view(), name='contrasena_cambiar'),

]
