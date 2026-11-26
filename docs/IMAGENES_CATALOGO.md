# SCRUM-125: galerías de imágenes de productos

## Requisitos revisados en Jira

Se consultaron por MCP de Atlassian las descripciones, campos y criterios de:

- [SCRUM-125](https://emiliosanmartinpez.atlassian.net/browse/SCRUM-125): subida,
  almacenamiento seguro y URLs de galerías vinculadas a documentos MongoDB.
- [SCRUM-75](https://emiliosanmartinpez.atlassian.net/browse/SCRUM-75): administración
  CRUD con galería y conexión al motor de variantes/SKUs y stock.
- [SCRUM-126](https://emiliosanmartinpez.atlassian.net/browse/SCRUM-126): formularios
  React para crear/editar productos, atributos dinámicos, SKUs y Drag & Drop.

Jira no establece formatos ni límites. Los valores siguientes son decisiones
de implementación configurables. El formulario Drag & Drop corresponde a
SCRUM-126; este cambio entrega el backend y su contrato de integración.

## Rutas y autorización

Todas las rutas usan el prefijo real `/api/catalogo/`.

| Método | Ruta | Resultado |
| --- | --- | --- |
| GET | `productos/{producto_id}/imagenes/` | 200, galería completa e IDs de archivos gestionados |
| POST | `productos/{producto_id}/imagenes/` | 201, agrega uno o varios archivos al final de la galería |
| DELETE | `productos/{producto_id}/imagenes/{imagen_id}/` | 204, desasocia la imagen, limpia referencias de variante y borra el archivo |
| PATCH | `productos/{producto_id}/` | 200, permite reordenar o reducir `imagenes` enviando la lista completa de URLs |
| DELETE | `productos/{producto_id}/` | 204, elimina el documento y programa/ejecuta la limpieza de sus archivos |

La gestión de galerías y todas las escrituras del CRUD requieren una cuenta
activa con `rol == "ADMIN"`, usando el permiso `IsAdministrador` existente.
Se admite `Authorization: Bearer <access_token>` con JWT real. También siguen
disponibles los mecanismos de autenticación DRF configurados; las sesiones
requieren CSRF para escribir. El rol se consulta en la cuenta actual, no se
confía en un rol enviado por el cliente ni en flags de staff/superuser.

GET de productos/listado sigue siendo público y retorna `imagenes: string[]`
con URLs accesibles; las imágenes de variante también retornan URLs.

## Subida multipart

Enviar exclusivamente el campo **`imagenes`**, repetido por cada archivo.
Un archivo usa el mismo campo. Se requiere `multipart/form-data`; el navegador
debe generar su boundary. No enviar JSON, Base64 ni URLs al endpoint de subida.

```javascript
const form = new FormData();
archivosSeleccionados.forEach((archivo) => form.append('imagenes', archivo));

const { data } = await clienteAxios.post(
  `catalogo/productos/${productoId}/imagenes/`,
  form,
  // axiosConfig.js tiene application/json como valor predeterminado.
  // Este override permite que el navegador genere Content-Type y boundary.
  { headers: { 'Content-Type': undefined } },
);

setImagenes(data.imagenes); // Galería completa, incluidas imágenes anteriores.
setArchivosGestionados(data.archivos); // IDs para borrar y URLs para preview.
```

Ejemplo de respuesta POST:

```json
{
  "producto_id": "507f1f77bcf86cd799439011",
  "imagenes": [
    "http://localhost:8000/media/catalogo/productos/507f1f77bcf86cd799439011/11111111111111111111111111111111.png"
  ],
  "archivos": [
    {
      "id": "11111111111111111111111111111111",
      "url": "http://localhost:8000/media/catalogo/productos/507f1f77bcf86cd799439011/11111111111111111111111111111111.png"
    }
  ],
  "subidas": [
    {
      "id": "11111111111111111111111111111111",
      "url": "http://localhost:8000/media/catalogo/productos/507f1f77bcf86cd799439011/11111111111111111111111111111111.png"
    }
  ]
}
```

GET retorna los mismos campos salvo `subidas`. `archivos` contiene únicamente
los archivos gestionados por estos endpoints; `imagenes` también incluye URLs
externas heredadas. No se accede ni se intenta borrar contenido externo.

## Flujo del formulario SCRUM-126

1. Para un producto nuevo, crear primero un borrador mediante
   `POST /api/catalogo/productos/`, con atributos y variantes. `fecha_creacion`
   la asigna el servidor; `publicado` puede permanecer en `false`.
2. Utilizar el `id` retornado para subir los archivos seleccionados por Drag & Drop.
   No existen subidas temporales sin producto, evitando asociaciones sin dueño.
3. Conservar **todas** las URLs de `data.imagenes` en el estado del formulario.
   La primera es la portada. El formulario anterior solo conservaba la primera;
   SCRUM-126 debe administrar la lista completa al editar.
4. Para asignar una foto a un SKU, enviar su URL en
   `variantes[i].imagen_especifica` mediante PUT/PATCH del producto, junto con
   los campos habituales de la variante. El backend normaliza esa URL a su clave
   interna y verifica que siga incluida en la galería del mismo producto.
5. Para reordenar, enviar `PATCH {"imagenes": [url2, url1, ...]}`. Para borrar
   un archivo, usar su `archivos[i].id` en DELETE y recargar la galería. Para
   retirar una URL externa, enviar la lista `imagenes` sin esa URL.
6. Si falla la subida, conservar el ID del borrador y permitir reintentar.
   Ante 409, recargar el producto antes de reintentar. Ante 503 después de un
   timeout, consultar GET primero: la asociación podría haberse confirmado.

Omitir `imagenes` en PUT/PATCH conserva la galería. Enviar `[]` la vacía y
programa la limpieza de los archivos retirados. Si se envían variantes e imágenes
en la misma petición, una variante no puede referenciar un archivo retirado.

## Validación y almacenamiento

| Configuración / variable de entorno | Valor inicial |
| --- | --- |
| `MEDIA_ROOT` | `<repositorio>/media` |
| `MEDIA_URL` | `/media/` |
| `CATALOGO_IMAGEN_MAX_BYTES` | 5242880 (5 MiB por archivo, original y procesado) |
| `CATALOGO_IMAGEN_MAX_ARCHIVOS` | 10 por petición |
| `CATALOGO_IMAGEN_MAX_GALERIA` | 20 por producto, contando URLs externas |
| `CATALOGO_IMAGEN_MAX_PIXELES` | 20000000 por imagen |

Se admiten imágenes estáticas JPEG (`image/jpeg`, `.jpg`/`.jpeg`), PNG
(`image/png`, `.png`) y WebP (`image/webp`, `.webp`). MIME declarado, extensión
y formato detectado deben coincidir. Se rechazan archivos vacíos, corruptos,
SVG, GIF, animaciones, dimensiones excesivas y bombas de descompresión.

El handler de subida limita bytes y cantidad durante la recepción multipart.
Antes de guardar se valida el lote completo. Pillow decodifica y regenera los
píxeles, corrige la orientación EXIF y elimina metadatos/contenido añadido.
El nombre original no se utiliza: las claves tienen la forma
`catalogo/productos/{producto_id}/{uuid}.{extension_canonica}`.

`Producto.imagenes` conserva su tipo MongoDB `List[String]`: para archivos propios
persiste claves de storage; las URLs HTTP(S) externas se conservan. Los serializers
resuelven las claves con `default_storage.url()` y la request para retornar URLs
absolutas. No se persiste el host local ni una firma temporal del storage.
Solo se aceptan claves/URLs gestionadas ya asociadas al producto actual; no es
posible inyectar rutas locales ni asociar archivos de otro producto mediante JSON.

La lógica se separa en puertos/tipos de dominio, el servicio de aplicación
`ServicioGaleria`, y adaptadores Django Storage/MongoEngine. Las modificaciones
de galería usan operaciones atómicas con la galería leída como precondición;
un cambio concurrente produce 409. El borrado modifica únicamente referencias
de imagen de los SKUs, preservando sus precios, atributos y stock actual.
No requiere migraciones SQL ni una conversión de documentos existentes.

En desarrollo, Django sirve media cuando `DEBUG=True`. En producción se debe
servir `MEDIA_ROOT` bajo `MEDIA_URL` mediante un servidor de media, o configurar
el storage predeterminado en `STORAGES` con URLs accesibles. Los endpoints siguen
usando `save`, `url` y `delete`; no dependen de `storage.path()`. El backend de
storage debe conservar el prefijo generado y los nombres/extension canónicos.
Si `MEDIA_URL` es una URL de CDN, sus URLs se devuelven directamente.

## Fallos y limpieza

| Código | Significado |
| --- | --- |
| 400 | Imagen o referencias inválidas, lote vacío, campo ausente/extra o galería llena |
| 401 | Credenciales ausentes/invalidas o cuenta inactiva |
| 403 | Cuenta autenticada sin rol ADMIN; también puede ocurrir por CSRF |
| 404 | Producto/ID inexistente o imagen ajena al producto |
| 409 | La galería cambió durante la operación; recargar y reintentar |
| 413 | Bytes por archivo o cantidad de archivos excedidos durante la recepción |
| 415 | Content-Type distinto de multipart en la subida |
| 503 | Fallo de persistencia/storage, sin detalles internos en la respuesta |

Un error de subida detectado ejecuta compensación de los archivos del lote;
se verifica primero que MongoDB no haya confirmado su asociación. MongoDB y
storage son recursos independientes, sin una transacción distribuida. Una caída
de proceso entre escribir un archivo y asociarlo puede requerir conciliación de
archivos huérfanos; un error de MongoDB que impide incluso registrar la limpieza
se conserva en logs para revisión operativa.

Antes de retirar referencias se registra una intención idempotente en la colección
`imagenes_catalogo_pendientes_borrado`. DELETE retorna 204 una vez desasociada la
imagen; si el borrado físico falla, su intención persiste para reintentar. Repetir
DELETE reintenta una intención pendiente; un ID desconocido o ya completamente
borrado retorna 404. El comando también cubre limpieza tras eliminar un producto:

```powershell
.\venv\Scripts\python.exe manage.py limpiar_imagenes_catalogo --limite 100
```

El comando nunca elimina una clave todavía referenciada por un producto/SKU.
Puede programarse operacionalmente para procesar pendientes. No recorre ni
elimina archivos arbitrarios de `MEDIA_ROOT`.

## Pruebas

```powershell
.\venv\Scripts\python.exe manage.py test ecommerce.infrastructure.catalogo --noinput
.\venv\Scripts\python.exe manage.py test --noinput
```

Se usa PostgreSQL de pruebas, MongoDB real y un directorio de media aislado.
Cada ejecución crea una base MongoDB `test_ecode_catalogo_<uuid>` y la elimina
al finalizar. `MONGO_TEST_URI` permite un servidor distinto; si se omite se usa
el servidor configurado por `MONGO_URI`, siempre con una base de nombre nuevo.
No se alteran las colecciones productivas. El workflow de backend incluye
servicios PostgreSQL 15 y MongoDB 6.

La suite verifica JWT/permisos, contenido/MIME/extensión, lotes, límites, nombres,
URLs, referencias entre productos, stock concurrente, documentos antiguos,
reordenación, borrado, compensación y reintentos de limpieza.

Referencias técnicas: [Django Storage](https://docs.djangoproject.com/en/6.1/ref/files/storage/),
[DRF multipart](https://www.django-rest-framework.org/api-guide/parsers/),
[Pillow y límites de descompresión](https://pillow.readthedocs.io/en/stable/reference/Image.html),
[MongoEngine: actualizaciones atómicas](https://docs.mongoengine.org/guide/querying.html#atomic-updates).
