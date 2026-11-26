from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from ecommerce.application.cuentas import (
    CambiarContrasena, ContrasenaActualIncorrecta, ContrasenaInvalida, EnlaceInvalido, RestablecerContrasena,
    SolicitarRestablecimiento,
)
from .cuentas import CorreoNotificadorCuentas, CuentasDjango, EnlacesDjango, ValidadorDjango
from .serializers import (
    CambiarContrasenaSerializer, GoogleAuthSerializer, OlvidoContrasenaSerializer, RegistroUsuarioSerializer,
    RestablecerContrasenaSerializer,
)
from .services import GoogleAuthService

User = get_user_model()

class RegistroView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegistroUsuarioSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            return Response({
                "message": "Usuario registrado exitosamente.",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "nombre": user.nombre,
                    "rol": user.rol
                },
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['id_token']
        payload = GoogleAuthService.verificar_token(token)

        email = payload.get('email')
        google_id = payload.get('sub')
        nombre = payload.get('given_name', 'Usuario')
        apellido = payload.get('family_name', 'Google')

        if not email:
            return Response(
                {"detail": "La cuenta de Google no tiene un email público asociado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # La misma cuenta aunque se haya registrado con otras mayúsculas
        user = User.objects.por_correo(email)

        if not user:
            user = User.objects.create_user(
                email=email,
                nombre=nombre,
                apellido_paterno=apellido,
                apellido_materno="",
                rol='COMPRADOR',
                google_sso_id=google_id,
                password=None
            )
            user.set_unusable_password()
            user.save()
        else:
            if not user.google_sso_id:
                user.google_sso_id = google_id
                user.save(update_fields=['google_sso_id'])

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Autenticación Google exitosa.",
            "user": {
                "id": user.id,
                "email": user.email,
                "nombre": user.nombre,
                "rol": user.rol,
                "google_sso_id": user.google_sso_id
            },
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)

class UsuarioActualAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'email': request.user.email,
            'rol': request.user.rol,
            'nombre': request.user.nombre,
            # El checkout los usa para precargar quién recibe el pedido (RF-02.3)
            'apellido_paterno': request.user.apellido_paterno,
            'telefono': request.user.telefono or '',
            # False en una cuenta creada con Google: al cambiarla no se pide la contraseña actual
            'tiene_contrasena': request.user.has_usable_password(),
        })


class CumpleanosAPIView(APIView):
    """La fecha de cumpleaños solo se consulta y modifica usando la cuenta autenticada."""
    permission_classes = [IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        from ..ventas.views_suscripciones import exigir_modulo_activo
        exigir_modulo_activo()

    def get(self, request):
        return Response({'dia': request.user.cumpleanos_dia, 'mes': request.user.cumpleanos_mes})

    def patch(self, request):
        from .serializers import CumpleanosSerializer
        serializer = CumpleanosSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        request.user.cumpleanos_dia = datos['dia']
        request.user.cumpleanos_mes = datos['mes']
        request.user.save(update_fields=['cumpleanos_dia', 'cumpleanos_mes'])
        return Response(datos)


class OlvidoContrasenaThrottle(SimpleRateThrottle):
    """Pocos pedidos de enlace por hora desde la misma IP (DEFAULT_THROTTLE_RATES['contrasena_olvido'])."""
    scope = 'contrasena_olvido'

    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class ContrasenaThrottle(SimpleRateThrottle):
    """Intentos de elegir o cambiar la contraseña: por cuenta con la sesión iniciada, si no por IP."""
    scope = 'contrasenas'

    def get_cache_key(self, request, view):
        ident = f'u{request.user.pk}' if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


MENSAJE_ENLACE_ENVIADO = ('Si el correo tiene una cuenta en la tienda, te enviamos un enlace para elegir una nueva '
                          'contraseña. Revisa también la carpeta de spam.')


class OlvidoContrasenaView(APIView):
    """POST /api/usuarios/contrasena/olvido/: siempre la misma respuesta, para no revelar qué correos tienen cuenta."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OlvidoContrasenaThrottle]

    def post(self, request):
        serializer = OlvidoContrasenaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        SolicitarRestablecimiento(CuentasDjango(), EnlacesDjango(), CorreoNotificadorCuentas()).ejecutar(
            serializer.validated_data['email'])
        return Response({'detail': MENSAJE_ENLACE_ENVIADO})


class RestablecerContrasenaView(APIView):
    """POST /api/usuarios/contrasena/restablecer/: la nueva contraseña con el uid y el token del enlace."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ContrasenaThrottle]

    def post(self, request):
        serializer = RestablecerContrasenaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        try:
            RestablecerContrasena(CuentasDjango(), EnlacesDjango(), ValidadorDjango(), CorreoNotificadorCuentas()
                                  ).ejecutar(datos['uid'], datos['token'], datos['password'], datos['password2'])
        except EnlaceInvalido as error:
            return Response({'enlace': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        except ContrasenaInvalida as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Tu contraseña se cambió. Ya puedes iniciar sesión.'})


class CambiarContrasenaView(APIView):
    """POST /api/usuarios/contrasena/cambiar/: con la sesión iniciada."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [ContrasenaThrottle]

    def post(self, request):
        serializer = CambiarContrasenaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        try:
            CambiarContrasena(CuentasDjango(), ValidadorDjango(), CorreoNotificadorCuentas()).ejecutar(
                request.user.id, datos['actual'], datos['password'], datos['password2'])
        except ContrasenaActualIncorrecta as error:
            return Response({'actual': [str(error)]}, status=status.HTTP_400_BAD_REQUEST)
        except ContrasenaInvalida as error:
            return Response(error.errores, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Tu contraseña se cambió.'})
