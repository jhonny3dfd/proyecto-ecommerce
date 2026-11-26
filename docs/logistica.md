# Logística: couriers y entregas de la tienda (RF-02.3, RF-02.4)

## Couriers

Cada courier (hoy Chilexpress) es un adaptador del puerto `Courier` (`ecommerce/application/couriers.py`). El núcleo
no nombra a ninguno: los toma del registro `COURIERS` (`ecommerce/infrastructure/ventas/couriers/__init__.py`), que
entrega los **activos**, es decir, los que tienen sus llaves obligatorias cargadas en el panel.

El puerto pide:

| Operación | Para qué |
| --- | --- |
| `comunas()` | Las comunas que atiende (el checkout y Mis direcciones muestran la unión de los activos) |
| `cotizar(origen, destino, paquete)` | La tarifa en pesos; lanza `SinCobertura` (400) o `CourierNoDisponible` (503) |
| `sucursales(comuna)` | Sus oficinas, si `con_sucursales` |
| `generar_orden_transporte(envio)` | La OT al confirmarse el pago (`GenerarOrdenTransporte` + `TransportistaSegunProveedor`) |
| `etiqueta(numero_ot)` | La etiqueta de la OT en base64, que el admin descarga como PDF |
| `consultar_estado(codigo)` | El estado traducido a la línea estándar: En origen → En tránsito → En reparto → Entregado |

Cada courier declara además su `codigo`, `nombre`, los `CAMPOS` de sus llaves (`CampoCredencial`) y una `ayuda`
para el panel.

### Cómo sumar un courier (ej. Starken)

1. Crear `ecommerce/infrastructure/ventas/couriers/starken.py` con una clase que implemente `Courier`, reciba sus
   `CredencialesCourier` en el constructor y declare sus `CAMPOS`.
2. Agregarla a `COURIERS` en `couriers/__init__.py`.
3. Probarla con mocks de `requests` (como `ventas/test_chilexpress.py`) y a mano contra su ambiente de pruebas.

No hay que tocar el checkout, el panel, las vistas ni los modelos: el panel muestra un formulario por courier con
sus campos, y el checkout lo ofrece apenas sus llaves estén completas.

### Llaves

El admin las carga en Configuración > Envíos por courier (`GET /api/ventas/admin/couriers/` y
`PUT /api/ventas/admin/couriers/<codigo>/`). Se guardan cifradas con `CLAVE_CIFRADO_CREDENCIALES` en
`ProveedorEnvio`, una fila por código, y el panel solo ve sus últimos 4 caracteres. Una llave que vuelve
enmascarada se conserva y una vacía se borra (`CredencialesCourier.con_cambios`).

Chilexpress pide tres:

- Cotizador (obligatoria): tarifas (`rating/api/v1.0/rates/business`).
- Coberturas: regiones, comunas y sucursales (`georeference`). Si falta, se usa la del cotizador.
- Envíos: órdenes de transporte, etiquetas y seguimiento. Si falta, se usa la del cotizador.

Su catálogo de comunas (nombre → código de cobertura) se descarga una vez y se guarda en memoria.

### Configuración pública

`GET /api/configuracion/` trae `couriers`: los activos, como `[{"codigo", "nombre", "sucursales"}]`, nunca sus
llaves. Sin couriers, el checkout no ofrece despacho ni sucursales y la comuna se escribe a mano.

## Entregas de la tienda

La configuración de la tienda vive en campos de `ConfiguracionGlobal`: `comuna_origen`, `region_origen`,
`calle_origen`, `numero_origen`, `dpto_casa_origen` y `retiro_en_local_activo`. Son públicos (el checkout
muestra la dirección de retiro).

La **entrega coordinada** la hace la propia tienda, sin transportista: el comprador deja su dirección y la tienda
lo contacta para acordar el día y el lugar. El admin la activa en Configuración > Entrega Coordinada
(`entrega_coordinada_activa`, `costo_entrega_coordinada` en CLP y `instrucciones_entrega_coordinada`, que ve el
comprador en el checkout y en los correos). No necesita la dirección del local. La regla de qué entrega propia
está activa y cuánto cuesta vive en `domain/logistica.py` (`EntregasDeLaTienda`).

## API

### `POST /api/ventas/logistica/cotizar/`

Solicitud: `destino` es el nombre de la comuna e `items`, los productos del carrito (hasta 100 líneas). Sin
`proveedor` cotizan todos los couriers activos; con él, solo ese:

```json
{"destino": "SANTIAGO", "items": [{"producto_mongo_id": "6630...", "variante_sku": "POLERA-M", "cantidad": 2}], "proveedor": "CHILEXPRESS"}
```

El paquete lo arma el servidor con el peso y las medidas de cada variante del catálogo (`paquete_de_envio` en
`domain/logistica.py`): pesa la suma de los productos y es un cubo con su volumen total, de al menos el lado más
largo de un producto y 10 cm. El origen es la comuna de la tienda (Configuración). Peso, medidas u origen enviados
por el navegador se ignoran: así nadie puede declarar menos peso para pagar menos envío. Las comunas se comparan sin
tildes ni mayúsculas (`clave_comuna`: 'Ñuñoa' es NUNOA); si la comuna de origen no está en la cobertura del
courier, no se cotiza (`503`), en vez de cotizar desde otra comuna.

Respuesta exitosa (`200`), una opción por courier que pudo cotizar:

```json
{"opciones": [{"proveedor": "CHILEXPRESS", "nombre": "Chilexpress", "precio": 3500, "tiempo_estimado": "EXPRESS", "moneda": "CLP"}]}
```

Errores, siempre con el cuerpo `{"error": "..."}`:

- `400`: falta `destino`, faltan los `items` o alguno no está disponible, comuna sin cobertura en todos los
  couriers, o la tienda no tiene couriers activos.
- `503`: ningún courier respondió con una tarifa válida (caído, sin servicios, tarifa negativa o no numérica).
  Nunca se convierte en costo cero. Un courier caído no tapa a los demás.

### `GET /api/ventas/logistica/sucursales/?comuna=MAIPU&proveedor=CHILEXPRESS`

Las oficinas del courier (sin `proveedor`, del primero activo que tiene oficinas):
`{"sucursales": [{"codigo", "nombre", "direccion"}]}`.

### Checkout (`POST /api/ventas/checkout/`)

Recibe `proveedor_logistico` (el código de un courier activo, `RETIRO_LOCAL` o `ENTREGA_COORDINADA`) y, para
despacho, la `comuna` en `direccion_envio_snapshot` (solo `calle`, `numero`, `dpto_casa`, `comuna`, `ciudad`,
`region` y `codigo_sucursal`, como texto y con largo máximo). El backend arma el paquete con el catálogo, como en la
cotización, lo guarda para la orden de transporte, cotiza con ese courier y recalcula el total, ignorando
`paquete`, `costo_envio` y `total_final` enviados por el cliente. Un courier que no está activo se rechaza con `400`. `RETIRO_LOCAL` cuesta cero y se rechaza con `400` si
`retiro_en_local_activo` está desactivado. `ENTREGA_COORDINADA` cobra `costo_entrega_coordinada`, no se cotiza ni
lleva paquete, y se rechaza con `400` si está desactivada; el envío gratis sobre un monto también la cubre. Si el
courier falla, responde `503` y no se crea la orden.

## Pruebas

`application/test_couriers.py` prueba los casos de uso con couriers falsos (varios activos, uno caído, sin
cobertura). `ventas/test_logistica.py` y `ventas/test_chilexpress.py` simulan las respuestas HTTP de Chilexpress,
por lo que no salen a internet. La conexión real se valida manualmente contra su sandbox con las llaves cargadas en
el panel; `probar_ot.py <orden_id>` genera la OT de un pedido de prueba.

La documentación pública de [Chilexpress](https://developers.wschilexpress.com/) describe la clave de suscripción,
los códigos de cobertura y la cotización por medidas; su
[guía de integración](https://cxpgdastprod.blob.core.windows.net/mdn/documentos/Nuevas_API_Chilexpress.pdf)
muestra el endpoint empresarial.
