# GUÍA DE PRUEBAS Y VERIFICACIÓN: MERCADO PAGO (CHECKOUT PRO)


## 1. OBJETIVO DE ESTA GUÍA

Esta guía permite a cualquier integrante del equipo reproducir, verificar y validar paso a paso el correcto funcionamiento y la seguridad de la pasarela **Mercado Pago Checkout Pro**, tanto a través de la interfaz web (Frontend React) como a través de la suite automatizada de pruebas (Backend Django).

1. **Backend Django (Terminal 1):**
   ```bash
   python manage.py runserver
   ```
   *(Disponible en `http://localhost:8000`).*

2. **Frontend React (Terminal 2):**
   ```bash
   cd frontend
   npm run dev
   ```
   *(Disponible en `http://localhost:5173`).*


## 2. CONFIGURACIÓN DE CREDENCIALES DE PRUEBA (SANDBOX)

Mercado Pago requiere credenciales de prueba para operar en modo Sandbox. Para configurarlas en la tienda:

1. Inicia sesión como administrador en `http://localhost:5173/login` (o en Django Admin `http://localhost:8000/admin`).
2. Ve a la sección **Configuración > Medios de Pago** en el panel de administración.
3. Habilita **Mercado Pago** e ingresa las credenciales de prueba de tu cuenta desarrollador de Mercado Pago:
   * **Access Token:** el de la cuenta de prueba del equipo (`MP_PRUEBA_ACCESS_TOKEN`; ver la nota de abajo)
   * **Webhook Secret:** `secreto_prueba_123`
4. Guarda los cambios. *(Las credenciales se guardan automáticamente cifradas con AES en PostgreSQL).*

> **Nota técnica:** El backend entrega la URL oficial unificada `init_point` de Mercado Pago. Al utilizar credenciales y cuentas de prueba TEST, Mercado Pago reconoce automáticamente el entorno de pruebas en su pasarela vigente, permitiendo pagar directamente desde el botón del checkout con las tarjetas ficticias oficiales sin caídas de servidor ni sustituciones manuales de URL.

---

## 4. DATOS Y TARJETAS DE PRUEBA OFICIALES (CHILE - CLP)

Mercado Pago Sandbox dispone de tarjetas de prueba diseñadas para simular respuestas predefinidas:
Para pagar, inicia sesión en Mercado Pago con el comprador de prueba del equipo (`MP_PRUEBA_COMPRADOR_USUARIO` y
`MP_PRUEBA_COMPRADOR_CLAVE`). Si al pagar pide un número de verificación, es `MP_PRUEBA_COMPRADOR_CODIGO`.

> **Credenciales de prueba:** no van escritas en el repositorio. Pídeselas al equipo y guárdalas en tu `.env` local
> (que git ignora) con esos cuatro nombres, solo como referencia: la tienda no las lee del `.env`; el Access Token se
> carga desde el panel (sección 2).

### 4.1 Tarjeta para Pago APROBADO (Flujo Exitoso)
| Campo | Valor de Prueba |
| :--- | :--- |
| **Número de Tarjeta** | `5416 7526 0258 2580` (Visa) o `4168 8188 4444 7115` (Mastercard) |
| **Nombre del Titular** | `APRO` (Obligatorio para forzar aprobación en Sandbox) |
| **Fecha de Vencimiento** | Cualquier fecha futura (ej. `11/30`) |
| **Código de Seguridad (CVV)**| `123` |
| **RUT del Titula o Otros** | Cualquier numero en otros (ej. `123456789`) recomiendo ocupar la opcion "Otros"

### 4.2 Tarjeta para Pago RECHAZADO (Fondos Insuficientes)
| Campo | Valor de Prueba |
| :--- | :--- |
| **Número de Tarjeta** | `4023 0000 0000 0000` |
| **Nombre del Titular** | `CONT` (Simula fondos insuficientes) |
| **Fecha de Vencimiento / CVV**| `11/30` / `123` |

### 4.3 Tarjeta para Rechazo por Error General
| Campo | Valor de Prueba |
| :--- | :--- |
| **Número de Tarjeta** | `4023 0000 0000 0000` |
| **Nombre del Titular** | `OTHE` (Simula rechazo por política o error de emisor) |
| **Fecha de Vencimiento / CVV**| `11/28` / `123` |

---

## 5. ESCENARIOS DE PRUEBA PASO A PASO (FRONTEND)

### Escenario 1: Compra Exitosa (Pago Aprobado)
1. Abre el catálogo en `http://localhost:5173/catalogo`.
2. Selecciona un producto con stock disponible (ej. talla o variante) y presiona **"Agregar al carrito"**.
3. Dirígete al **Checkout** (`http://localhost:5173/checkout`).
4. Completa los datos obligatorios del destinatario y la dirección de despacho.
5. En la sección **"¿Cómo deseas pagar?"**, selecciona la opción **Mercado Pago**.
6. Acepta los Términos y Condiciones y haz clic en **"Pagar con Mercado Pago"**.
7. **Resultado esperado:**
   * El sistema registra la orden en estado `PENDIENTE`.
   * El navegador es redirigido a la pantalla oficial de Checkout Pro de Mercado Pago.
8. En Mercado Pago, elige **"Nueva tarjeta"** e ingresa la **Tarjeta para Pago APROBADO** (Titular: `APRO`).
9. Completa el flujo hasta la confirmación de Mercado Pago.
10. **Resultado esperado al volver:**
    * Mercado Pago redirige al comprador a `http://localhost:5173/pago-exitoso?orden=<ID>`.
    * La pantalla muestra el número de orden y la confirmación de pago.
    * El carrito local (`carrito_local`) se vacía automáticamente.
    * En la base de datos, la orden pasa a estado `PAGADO` y el stock de la variante se descuenta atómicamente.

---

### Escenario 2: Pago Rechazado
1. Agrega cualquier producto al carrito e inicia el Checkout seleccionando **Mercado Pago**.
2. Al llegar a la pasarela de Mercado Pago, ingresa la tarjeta con titular `CONT` o `OTHE`.
3. Procesa el intento de pago. Mercado Pago informará que el pago fue rechazado.
4. **Resultado esperado:**
   * Al regresar a la tienda, serás dirigido a `http://localhost:5173/pago-rechazado?orden=<ID>`.
   * La pantalla indica con ícono de rechazo que la transacción no fue procesada y que no se ha realizado ningún cobro.
   * **El carrito de compras permanece intacto**, permitiendo al usuario volver a intentar pagar de inmediato sin perder sus productos seleccionados.
   * En la base de datos, la orden queda marcada como `CANCELADO` con motivo `"Pago rechazado"`. El stock no se descuenta.

---

### Escenario 3: Anulación o Cancelación por el Comprador
1. En el checkout, haz clic en **"Pagar con Mercado Pago"**.
2. Una vez en la ventana de Mercado Pago, haz clic en el enlace inferior **"Volver al sitio"** (o cancela la operación).
3. **Resultado esperado:**
   * Regresas a `http://localhost:5173/pago-cancelado?orden=<ID>`.
   * El mensaje confirma que el pago fue cancelado y tus productos siguen en el carrito.
   * La orden se cancela con motivo `"Pago anulado en pasarela"`.

---

### Escenario 4: Pago Pendiente / En Proceso (Efectivo o Revisión)
1. Al pagar mediante un método que requiere acreditación asíncrona (como efectivo o revisión manual).
2. **Resultado esperado:**
   * El comprador es dirigido a `http://localhost:5173/pedido-recibido?orden=<ID>`.
   * Se informa claramente que el pedido está **pendiente de pago** y que se preparará una vez confirmado.
   * La orden permanece en estado `PENDIENTE` sin descontar stock anticipadamente.

---

## 6. VALIDACIÓN AUTOMATIZADA MEDIANTE SUITE DE TESTS (BACKEND)

Para evaluar todas las reglas de negocio, seguridad criptográfica y manejo de errores sin necesidad de conectarse a servicios externos:

### 6.1 Ejecutar Suite Exclusiva de Mercado Pago (14 Tests)
Abre la terminal en la raíz del proyecto y ejecuta:
```bash
python manage.py test ecommerce.infrastructure.ventas.test_mercadopago
```

**Qué valida esta suite:**
1. `test_pago_aprobado_pasa_a_pagado_descuenta_stock_y_envia_correo`: Transición a `PAGADO`, descuento atómico y emisión de evento.
2. `test_pago_rechazado_cancela_orden_y_envia_correo`: Cancelación limpia y auditoría de motivo.
3. `test_pago_pendiente_deja_orden_en_pendiente_sin_descontar_stock`: Retención de orden sin afectar inventario.
4. `test_aviso_repetido_es_idempotente_no_descuenta_dos_veces_ni_reenvia_correo`: Idempotencia y control de duplicados.
5. `test_firma_invalida_lanza_error_y_no_cambia_la_orden`: Bloqueo ante firmas HMAC manipuladas.
6. `test_monto_distinto_marca_orden_para_revision_del_admin`: Detección de adulteración de precios (*tampering*).
7. `test_vista_webhook_responde_401_con_firma_invalida`: Respuesta HTTP 401 para peticiones no autenticadas.
8. `test_webhook_refunded_marca_orden_para_revision_si_estaba_pagada`: Manejo seguro de reembolsos y contracargos.
9. `test_webhook_topic_no_relevante_es_ignorado`: Filtrado de eventos no vinculados a pagos.
10. `test_vista_retorno_si_orden_ya_estaba_pagada_redirige_a_exitoso`: Sincronización cuando el webhook llega antes que el navegador.
11. `test_vista_retorno_seguridad_no_aprueba_si_consulta_falla`: *Zero-Trust* ante caída o simulación de retorno.
12. `test_vista_retorno_discrepancia_orden_id_redirige_a_cancelado`: Prevención de cross-account/cross-order hijacking.
13. `test_vista_retorno_aprueba_orden_con_pago_valido`: Aprobación verificada server-to-server.
14. `test_vista_retorno_pago_pendiente_redirige_a_pedido_recibido`: Redirección semántica para pagos diferidos.

**Resultado esperado:**
```text
Ran 14 tests in 0.026s
OK
```

---

### 6.2 Ejecutar Suite Completa de Regresión del Sistema (210 Tests)
Para asegurar que las tareas de promociones (SCRUM-136), logística y catálogo no sufrieron ninguna regresión:
```bash
python manage.py test ecommerce.infrastructure.ventas ecommerce.infrastructure.catalogo
```

**Resultado esperado:**
```text
Ran 210 tests in ~15s
OK
```

---

## 7. VALIDACIÓN DE COMPILACIÓN DEL FRONTEND

Para corroborar que no existen errores de sintaxis, imports rotos o fallos en el bundle de producción:

```bash
cd frontend
npm run build
```

**Resultado esperado:**
```text
✓ 1410 modules transformed.
✓ built in ~6s (Exit code: 0)
```

---

## 8. MATRIZ DE SEGURIDAD VERIFICADA

| Vector de Riesgo | Medida Defensiva en Código | Comprobación |
| :--- | :--- | :--- |
| **Alteración del precio** | El backend ignora cualquier precio enviado por el frontend. Calcula el total sumando los items validados en MongoDB y la tarifa del courier. | En [serializers.py:354](file:///c:/Users/jhona/Ecode/ecommerce/infrastructure/ventas/serializers.py#L354). |
| **Spoofing de Webhook** | El endpoint exige firma HMAC-SHA256 (`x-signature`). No confía en los datos recibidos y consulta directamente a la API oficial de Mercado Pago. | En `aviso_autentico` de [adapters/mercadopago.py](ecommerce/infrastructure/ventas/adapters/mercadopago.py) y el caso de uso `ProcesarAvisoPago` de [application/pagos.py](ecommerce/application/pagos.py). |
| **Timing Attacks** | Se utiliza `hmac.compare_digest` para comparar firmas en tiempo constante. | En `aviso_autentico` de [adapters/mercadopago.py](ecommerce/infrastructure/ventas/adapters/mercadopago.py). |
| **Manipulación de URLs de Retorno** | El cliente no puede forzar la aprobación alterando la URL (`?status=approved`); el backend valida el pago con la API antes de cambiar el estado de la orden. | En [views.py:365-385](file:///c:/Users/jhona/Ecode/ecommerce/infrastructure/ventas/views.py#L365-L385). |
| **Cifrado de Credenciales** | `access_token` y `webhook_secret` se guardan cifrados con AES en base de datos (`CLAVE_CIFRADO_CREDENCIALES`). | En [models.py](file:///c:/Users/jhona/Ecode/ecommerce/infrastructure/ventas/models.py). |

---

## 9. CONTACTO Y SOPORTE
Si tienes dudas durante la revisión o necesitas que generemos credenciales de prueba Sandbox adicionales, contacta a **Jhonatan de la Cruz Tigre (Equipo 1)** o revisa el reporte formal en [Reporte_revision_cruzada_SCRUM-161_MercadoPago.md](file:///c:/Users/jhona/Ecode/Reporte_revision_cruzada_SCRUM-161_MercadoPago.md).
