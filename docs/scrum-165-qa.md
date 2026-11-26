# SCRUM-165: encabezado en checkout, seguimiento y acceso

Fecha: 14 de octubre de 2026. Equipo 3: Huiscan y Vallejos. Rama: `eidan`.

Tarea: [SCRUM-165](https://emiliosanmartinpez.atlassian.net/browse/SCRUM-165).
RN-01 fundamenta conservar la identidad visible durante la compra. Se reutiliza el
encabezado actual; el logo comercial y el favicon pertenecen a SCRUM-167.

## Implementación y alcance

- `App.jsx` utiliza un contenedor global `div` con `flex: 1`.
- Checkout, seguimiento y `AuthPage` tienen un único `main`, con el `Header` como
  hermano. El encabezado también aparece durante carga, errores y elección de acceso.
- Login y registro conservan el encabezado completo porque forman parte del regreso
  al checkout. No se alteraron los handlers de autenticación ni el proveedor de Google.
- No se modificaron HistorialPedidos, MisDirecciones, ProtectedRoute ni las demás
  páginas secundarias para normalizar sus landmarks.
- `useCarrito` comparte el snapshot de `carrito_local`, escucha el evento local y los
  eventos `storage`, y convierte cantidades y precios a números. JSON inválido y
  contenido que no sea un arreglo se interpretan como carrito vacío.
- El mini carrito y el resumen consumen los mismos datos. El contador suma unidades;
  su total corresponde al subtotal, mientras checkout añade el envío.
- Las validaciones y cotizaciones anteriores no reemplazan la versión vigente.
  Los avisos de ajuste corresponden a la versión del carrito que se ajustó.
- El diseño permite varias filas en pantallas pequeñas y mantiene los desplegables
  dentro del viewport. Se añadieron foco visible, cierre con Escape y etiquetas
  asociadas a los campos de seguimiento.

## Entorno y datos de prueba

Se inició Vite en `http://localhost:5173` y Django en `http://localhost:8000`.
Con Django real se comprobó que las tres vistas cargan el logo y el menú, tienen
un único `main`, no contienen `main main` y no presentan desbordamiento horizontal.

El catálogo local respondió con un arreglo vacío. Para comprobar cantidades,
stock, precios, respuestas tardías, autenticación y pagos se utilizó una API HTTP
temporal con respuestas simuladas. Los controles de prueba operaron en otra pestaña
del mismo origen y utilizaron los helpers reales del frontend. No se crearon
productos, cuentas ni pedidos en las bases de datos, ni se realizaron pagos reales.

La API temporal se detuvo al finalizar y se restauró Django. La sesión y el carrito
de prueba se limpiaron mediante el menú de usuario. El override de viewport se
restauró. Los archivos de control temporales no forman parte de los commits.

## Verificación visual en Browser

El viewport se comprobó con `window.innerWidth` y `window.innerHeight`. Los JPEG
se conservaron tal como los entrega Browser; algunas imágenes tienen dimensiones
menores que el viewport medido cuando la página presenta barras de desplazamiento.

| Vista | Viewport medido | Logo y menú | `main` | `main main` | Desbordamiento horizontal |
| --- | --- | --- | --- | --- | --- |
| `/checkout` | 1440 × 900 | Visibles | 1 | 0 | No |
| `/checkout` | 390 × 844 | Visibles | 1 | 0 | No |
| `/seguimiento` | 1440 × 900 | Visibles | 1 | 0 | No |
| `/seguimiento` | 390 × 844 | Visibles | 1 | 0 | No |
| `/login` | 1440 × 900 | Visibles | 1 | 0 | No |
| `/login` | 390 × 844 | Visibles | 1 | 0 | No |

También se inspeccionó seguimiento a 768 × 1024: logo de 150 px, menú visible y
ancho de contenido igual al ancho desplazable (753 px, sin desbordamiento).
El registro a 390 × 844 conservó un encabezado, un `main` y ningún desbordamiento.

En móvil, el panel del carrito quedó entre x=38 y x=358, con 320 px de ancho.
El panel del usuario autenticado quedó dentro del viewport, con 280 px de ancho;
el saludo largo se truncó visualmente sin cortar las acciones.

### Capturas

| Vista | Escritorio | Móvil |
| --- | --- | --- |
| Checkout | [Captura](scrum-165-capturas/checkout-desktop.jpg) | [Captura](scrum-165-capturas/checkout-mobile.jpg) |
| Seguimiento | [Captura](scrum-165-capturas/seguimiento-desktop.jpg) | [Captura](scrum-165-capturas/seguimiento-mobile.jpg) |
| Login | [Captura](scrum-165-capturas/login-desktop.jpg) | [Captura](scrum-165-capturas/login-mobile.jpg) |

Desplegables: [carrito móvil](scrum-165-capturas/carrito-mobile.jpg) y
[usuario móvil](scrum-165-capturas/menu-usuario-mobile.jpg).

Las capturas de checkout contienen datos QA. Seguimiento utiliza la orden simulada
`QA-165` y el correo ficticio `qa@example.test`; no representan un pedido real.
El contorno azul de Catálogo en seguimiento demuestra el foco de teclado.

## Escenarios funcionales observados

| Escenario | Resultado |
| --- | --- |
| Carrito inicialmente vacío | Contador 0 y resumen vacío; pago deshabilitado. |
| Datos con cantidades y precios como strings | Dos unidades de $1.000 y una de $2.500: contador 3 y subtotal $4.500. |
| Actualización desde otra pestaña | Aumentar a cuatro unidades actualizó contador y resumen a $5.500 sin recargar checkout. |
| Stock y precio cambian juntos | La primera línea bajó a una unidad a $1.200: contador 2, subtotal $3.700 y avisos de ambos cambios. |
| Validación antigua | Una respuesta atrasada 1,5 s, con stock y precio anteriores, no sustituyó el carrito nuevo de 3 unidades y $4.500. |
| Cotización antigua | Cambiar de Providencia a Concón conservó la cotización nueva de $6.040 y total $11.540, sin aplicar la respuesta anterior. |
| Carrito cambia con destino seleccionado | La cotización cambió con el peso del carrito; los valores anteriores dejaron de estar disponibles para pagar. |
| JSON inválido y eliminación de la clave | Contador 0 y resumen vacío, sin romper la vista. |
| Sucursal y retiro en local | Las oficinas correspondieron a la comuna; retiro en local derivó un costo de envío 0. |
| Modo mixto y registro obligatorio | Encabezado presente en la elección de invitado y en el llamado a iniciar sesión. |
| Login y registro | Alternancia con encabezado persistente. El login simulado regresó al checkout de registro obligatorio. |
| Cancelación simulada | Se conservaron las 3 unidades al regresar al checkout. |
| Pedido recibido sin pasarela y pago exitoso simulado | El carrito se vació y el contador quedó en 0. |
| Seguimiento con `?orden=QA-165` | Número precargado, resultado y progreso En tránsito visibles. |
| Error de seguimiento | Se mostró el aviso y se conservó el encabezado. |
| Escape y teclado | Escape cerró los desplegables; los enlaces mostraron foco visible. |

Un harness temporal de Node verificó además los helpers originales y la suscripción:
snapshot estable, lectura segura, eventos locales y entre pestañas, limpieza de
listeners, escritura idéntica sin otra notificación, payload de validación,
sincronización autenticada, ajustes de stock/precio y vaciado. Las comprobaciones
terminaron correctamente; ese harness utilizó dependencias simuladas.

No se comprobó un login real de Google ni una transacción real con una pasarela.

## Compilación y ESLint

Desde `frontend`, en PowerShell:

```powershell
npm.cmd run build
npm.cmd exec -- eslint src/App.jsx src/components/Checkout.jsx src/pages/SeguimientoEnvio.jsx src/components/CarritoCompras.jsx src/components/carrito.js src/hooks/useCarrito.js src/components/header/header.jsx src/components/MenuUsuario.jsx --max-warnings=0
```

Resultados: build correcto; ESLint de los ocho archivos JS/JSX modificados terminó
con **0 errores y 0 advertencias**, sin desactivar reglas. Vite mantiene la advertencia
preexistente sobre el tamaño del bundle; no impide compilar.

El lint global (`npm.cmd run lint -- --format json`) todavía falla fuera del alcance.
En la comprobación final reportó **8 errores y 0 advertencias**:

| Archivo sin modificar | Errores | Regla / motivo |
| --- | --- | --- |
| `AdminTopbar.jsx` | 1 | `no-unused-vars`: React. |
| `Dashboard.jsx` | 3 | `no-unused-vars`: React, onVerTodos y anio. |
| `DashboardCard.jsx` | 1 | `no-unused-vars`: React. |
| `FormularioProducto.jsx` | 2 | React sin uso y `react-hooks/set-state-in-effect`. |
| `VariantSelector.jsx` | 1 | `react-hooks/set-state-in-effect`. |

Se confirmó con `git diff --exit-code ecd2082 -- <estos cinco archivos>` que su
contenido es idéntico al estado anterior a SCRUM-165. Se conserva el alcance
aprobado: no corregir archivos ajenos para limpiar el lint global.

## Commits de código verificados

1. `87917f5` — Landmarks de compra y acceso.
2. `48fd6b9` — Encabezado en checkout, seguimiento y acceso.
3. `65332ee` — Carrito compartido, validación y cotizaciones coherentes.
4. `c624ecc` — Diseño responsivo y mejoras de accesibilidad del encabezado.

El quinto commit incorpora este registro y las ocho capturas del navegador.
