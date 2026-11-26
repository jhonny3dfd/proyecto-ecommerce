"""Security probes: mounted only by override_settings, never in production."""

from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.infrastructure.usuarios.permissions import IsAdministrador

from rest_framework.authentication import TokenAuthentication, SessionAuthentication

class AuthenticatedProbe(APIView):
    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]
    # Inherit the production authentication and permission defaults.
    def get(self, request):
        return Response({'id': request.user.pk})


class AdministratorProbe(APIView):
    permission_classes = [IsAdministrador]

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    def get(self, request):
        return Response({'id': request.user.pk})

    def post(self, request):
        return Response({'id': request.user.pk}, status=201)

    put = get
    patch = get
    delete = get


urlpatterns = [
    path('private/', AuthenticatedProbe.as_view(), name='security-private'),
    path('administrator/', AdministratorProbe.as_view(),
         name='security-admin'),
]
