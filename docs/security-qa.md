# SCRUM-94 / SCRUM-98: seguridad y contratos de acceso

## Estado y alcance

La suite verifica la política reutilizable de seguridad con vistas de prueba,
el checkout real y el dashboard productivo contra la base SQL de pruebas. El
dashboard `GET /ventas/api/dashboard/` aplica `IsEmprendedor` y se prueba con
tokens de acceso firmados por SimpleJWT, sin `force_authenticate` ni mocks.

## Política implementada

- Las vistas DRF requieren `IsAuthenticated` por defecto. Las rutas públicas
  nuevas deben declarar su permiso explícitamente.
- `TokenAuthentication` precede a `SessionAuthentication`: las peticiones sin
  credenciales a rutas protegidas devuelven `401` con `WWW-Authenticate: Token`.
- Las rutas heredadas de QA y checkout admiten `Authorization: Token <clave>`
  de DRF. Las rutas JWT admiten `Authorization: Bearer <access>` mediante
  SimpleJWT; el acceso dura 60 minutos y el refresh un día.
- Las sesiones Django existentes siguen siendo válidas; una petición con sesión
  válida está autenticada aunque no incluya Authorization. Escrituras por sesión
  necesitan CSRF. Un token reconocido pero inválido no recurre a la sesión.
- `IsAdministrador` requiere cuenta activa y `rol == 'ADMIN'`; ni `is_staff`
  ni `is_superuser` reemplazan ese rol. Aplicar
  `permission_classes = [IsAdministrador]` a futuras vistas de administración.
  La misma condición se comprueba en permisos de objeto.
- `IsEmprendedor` exige un Bearer JWT válido cuyo payload contenga exactamente
  `rol: "Emprendedor"`. El test genera el refresh con `RefreshToken.for_user`,
  añade el claim firmado y deriva desde él el access. Los emisores actuales de
  registro, login tradicional y Google todavía no añaden ese claim por defecto;
  si el dashboard se consume con esos tokens, el permiso devuelve `403`.
- Checkout permite invitados en `INVITADO`, `MIXTO` y sin configuración. En
  `REGISTRO_OBLIGATORIO`, rechaza anónimos con `401` antes de validar el cuerpo
  (antes devolvía `400` desde el serializer). Ambos roles pueden comprar.
- `/admin/` pertenece al sitio HTML de Django y conserva sus reglas de sesión,
  staff y redirecciones; la política HTTP de DRF no se aplica a ese sitio.

Con sesiones, CSRF inválido puede producir `403` aun para ADMIN. Un método no
admitido puede producir `405`; no se promete `200` para cualquier petición de
un administrador independientemente de su validez.

## Matriz automatizada

| Superficie | Casos | Resultado |
| --- | --- | --- |
| Permiso unitario de vista/objeto | Anónimo, rol vacío/desconocido, COMPRADOR, staff/superuser, ADMIN inactivo | Denegado |
| Permiso unitario de vista/objeto | ADMIN activo sin flags de Django | Permitido |
| Rutas de prueba privadas | Header ausente/vacío, token desconocido, malformado o esquema no admitido | 401 + challenge |
| Ruta de prueba ADMIN | COMPRADOR en GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS | 403 |
| Ruta de prueba ADMIN | ADMIN activo, mismos métodos | 200; POST 201 |
| Dashboard real | Sin `Authorization: Bearer` | 401 |
| Dashboard real | JWT válido con rol COMPRADOR | 403 |
| Dashboard real | JWT válido con `rol: "Emprendedor"` | 200 |
| Autenticación real | Cuenta inactiva/eliminada, token revocado | 401 |
| Autorización real | ADMIN degradado con token existente | 403 inmediato |
| Sesiones | Roles, CSRF ausente y presente; token inválido con sesión válida | 200/201, 403 o 401 según política |
| Checkout real | Invitados, ambos roles y todos los modos de tienda | 201 o 401 según modo |
| Checkout real | Token inválido/inactivo; identidad inyectada en payload | Sin orden o asignación al usuario autenticado |
| Checkout real | Email invitado ausente; intento de listar órdenes | 400; 405 |

`usuarios/tests/urls.py` solo se monta mediante `override_settings`; sus vistas
no simulan operaciones de negocio ni se publican. No se usa `force_authenticate`
ni se reemplaza la validación de tokens por mocks. Las factories crean usuarios
y contraseñas con el manager real; cada test revierte sus datos. No se necesita
MongoDB ni Google porque no se ejercitan adaptadores de catálogo ni SSO.

## Ejecución

Requisitos: dependencias de `requirements.txt`, PostgreSQL accesible según las
variables `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` y
`POSTGRES_PORT`, y usuario SQL con permiso para crear bases de prueba.
Django crea y elimina `test_<POSTGRES_DB>` y aplica las migraciones, incluidas las
de tokens. No desactivar migraciones ni apuntar a una base de producción.

Con el entorno virtual activado, desde la raíz:

```powershell
python manage.py test
```

Solo esta suite:

```powershell
python manage.py test ecommerce.infrastructure.usuarios ecommerce.infrastructure.ventas --verbosity 2
```

Sin activar el entorno virtual de Windows:

```powershell
.\venv\Scripts\python.exe manage.py test --noinput
```

`.github/workflows/backend-security.yml` ejecuta la suite con PostgreSQL 15
aislado. Usa las versiones ya fijadas por el proyecto y no requiere secretos ni
servicios Google. La suite completa también ejecuta las pruebas de catálogo
SCRUM-125 con un servicio MongoDB 6 y bases aisladas por ejecución; las suites
de usuarios/ventas mencionadas arriba siguen sin necesitar MongoDB. No se
cambian los settings productivos por SQLite.

Validación local realizada: 22 tests aprobados sobre PostgreSQL, comprobación
de migraciones sin cambios pendientes y `git diff --check` sin errores.
El workflow queda versionado; su ejecución remota no se ha verificado.

## Contrato OpenAPI

[openapi.json](openapi.json) es OpenAPI 3.0.3, importable en Swagger Editor o
Postman, y documenta las rutas que están montadas actualmente bajo `/usuarios/`:

- `POST /usuarios/registro/`: alta y respuesta `201` con `user` y el par JWT
  dentro de `tokens`.
- `POST /usuarios/token/`: login tradicional y respuesta `200` con `access` y
  `refresh` en el nivel superior, según `TokenObtainPairView`.
- `POST /usuarios/google/`: canje de `id_token`; crea o reutiliza la cuenta y
  responde `200` con `user` y `tokens`.
- `POST /usuarios/token/refresh/`: renueva el access a partir del refresh.

El contrato refleja los campos que aceptan los serializers actuales, ejemplos
de éxito y respuestas `400`/`401`. Estas rutas públicas no requieren CSRF. El ID
token de Google solo se usa para verificar identidad; después el backend emite
sus propios JWT SimpleJWT.

Referencias oficiales de las decisiones:

- [DRF: autenticación y códigos 401/403](https://www.django-rest-framework.org/api-guide/authentication/)
- [DRF: permisos](https://www.django-rest-framework.org/api-guide/permissions/)
- [Google: verificación de ID tokens](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
