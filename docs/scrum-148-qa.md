# SCRUM-148: accesibilidad y reflujo

Evaluación local del 23 de octubre de 2026. Tienda y panel React de SCRUM-83; WCAG 2.1 A/AA. No incluye el administrador interno de Django.

Base: `4eaec4b87fe8d99b11f853ca97620e9c23e20635` (125 pruebas frontend y build correctos). Código frontend final evaluado: árbol Git `4c1ded7abdf92a88ed2dfb2c070c036ce2b8db6c`, comprobable con `git rev-parse HEAD:frontend`. Windows, Node 24.19.0, Python 3.13.15, Vitest 5.0.4, Playwright 1.64.1, axe 4.14.0; Chromium y Edge. Se reutilizó el fixture `scrum149-v1` con PostgreSQL y MongoDB en Docker.

Se inspeccionaron las pruebas de Javier hasta `3258987345669a7fcca6f31c8fbbe3cbe7f1e0f1`: cubren lógica de seguimiento, carrito, variantes y checkout mediante simulaciones. Las pruebas nuevas se concentran en DOM, teclado, diálogo, consultas simultáneas, reflujo e integración real. No hubo dependencia funcional ni incorporación de sus commits. No se pudo recuperar el contenido del informe DOCX adjunto; no se atribuyen hallazgos a ese documento. No se repitió su auditoría de carga.

## Defectos comprobados y correcciones

La inspección inicial no detectó problemas automáticos en las vistas públicas habituales a 390 píxeles. La paleta de texto existente ya supera 4,5:1 en sus combinaciones previstas; se conservó. La línea base dinámica del panel se tomó antes de las correcciones de estructura, teclado y reflujo.

| Evidencia anterior | Resultado y archivos principales |
|---|---|
| Bordes de campos sobre blanco: 1,36–1,41:1; excepción rosada en Precio Oferta | Token `controlBorder` separado de bordes decorativos: mínimo 4,02:1 sobre superficie, fondo y fondo secundario de las cuatro paletas. CSS y estilos de formularios; `paletas.test.js`, `accesibilidad.spec.js`, formulario dinámico. |
| Texto de portada sobre imagen blanca: 3,64:1 en el caso evaluado | Velo de al menos 60 % negro, conservando imagen y composición. Contraste calculado con colores computados y transparencia, >=4,5:1 en escritorio y móvil (`portada-accesible.spec.js`). |
| `/variantes` sin `main`; sin salto compartido ni títulos por ruta; Escape no restituía el foco de los paneles del encabezado | Un `main` por vista, salto al contenido, títulos y foco de navegación. Menú y carrito cierran con Escape y al salir con Tab. Se conserva la caché de configuración. |
| Detalles de pedidos y aviso de pago con contención manual incompleta | `Dialogo.jsx` usa `dialog.showModal()`, fondo inerte, foco inicial, ciclo Tab/Shift+Tab, Escape y retorno al disparador. Cerrar el aviso deja la misma orden y su consulta periódica activas; no envía cancelación ni genera compras nuevas. Guardas contra consultas solapadas. |
| Expansión de variantes dependiente del clic de fila; iconos ambiguos | Botón nativo con estado expandido, nombres de producto y acciones contextuales; galería devuelve foco al selector tras retirar imagen. La validación asíncrona de stock conserva foco sin robárselo a quien lo haya movido. |
| axe: `aria-command-name` en Quill; regiones de ventas/promociones sin acceso de teclado; gráfico sin tabla equivalente | Editor y barra con nombres en español, foco visible, regiones desplazables nombradas y enfocables. Tabla desplegable con los mismos datos del gráfico, sin solicitudes adicionales. |
| Formulario de inventario a 320: documento de 369 píxeles; login al 200 %: 406/390; acción de checkout con tipografía Cercana: 403/390 | Cuadrículas adaptables, mínimos flexibles y ajuste de texto localizados. Documento <= viewport en los casos comprobados. Editor legal crece con su contenido y conserva acceso a publicar/guardar. |

Se conservaron los campos, opciones de personalización, contratos HTTP, filtros, ordenamiento, paginación, validación de stock, condiciones legales, logística y operaciones existentes. Las correcciones incluyen sus pruebas en seis commits sustantivos.

## Cobertura y método

Referencia normativa: [WCAG 2.1 del W3C](https://www.w3.org/TR/WCAG21/). Contraste de texto: 4,5:1, o 3:1 para texto grande según la definición normativa; componentes que necesitan distinguirse: 3:1. Los controles deshabilitados y bordes puramente decorativos tienen excepciones. AA no exige una fuente mínima de 16 píxeles ni los tamaños de objetivo de WCAG 2.2/AAA.

| Rutas o vistas / componentes | Estados y comprobaciones | Criterios relacionados |
|---|---|---|
| Todas: App, Header, Footer, CookieBanner, ProtectedRoute | Un `main` visible, jerarquía, títulos, idioma, imágenes y nombres; salto, orden, foco, menú/carrito, rechazo y reapertura de cookies. Sin activar telemetría antes del consentimiento. | 1.1.1, 1.3.1–2, 1.4.1/3/11/13, 2.1.1–2, 2.4.1–7, 2.5.3, 3.1.1, 3.2.1–4, 4.1.1–3 |
| `/`, `/catalogo`, `/catalogo/producto/:id`, `/variantes` | Contenido configurable, imagen clara, cuatro paletas/cinco tipografías; primera/última página, filtros y orden; variantes, stock, cantidad y aviso al agregar. Sin producto y sin variantes. | 1.1.1, 1.3.1–2, 1.4.3/4/10/11/12, 2.1.1, 2.4.4/6/7, 4.1.2–3 |
| `/login` (acceso y registro), `/mis-direcciones` | Etiquetas nativas, tipos/autocompletado, requerido, mensajes asociados, estados vacío y autenticado. Registro incluido en reflujo de las cuatro resoluciones; código de errores y asociaciones revisado sin crear cuentas reales. | 1.3.1/5, 1.4.4/10/12, 2.4.6, 2.5.3, 3.3.1–3, 4.1.2–3 |
| `/checkout`, `/pedido-recibido`, `/pago-exitoso`, `/pago-cancelado`, `/pago-rechazado` | Visitante y cuenta QA; domicilio/retiro, condiciones, total y pago. Diálogo abierto/cerrado/reabierto, pago pendiente/pagado/cancelado/error y respuesta lenta simulados. Transferencia y retiro reales solo en datos QA. | 1.3.1/5, 1.4.4/10/12, 2.1.1–2, 2.4.3/6/7, 3.3.1–4, 4.1.2–3 |
| `/seguimiento`, `/mis-pedidos`, `/legal/:tipo` | Consulta con resultado y foco, historial vacío/detalle pagado simulado, cierre y reapertura; contenido legal largo real y enlaces publicados. | 1.3.1–2, 1.4.4/10/12, 2.1.1–2, 2.4.2/3/6/7, 3.3.1–2, 4.1.2–3 |
| `/admin`: Dashboard, Inventario, FormularioProducto, GaleriaImagenes | Carga, vacío, datos del gráfico/tabla; filtro, expandir por Enter, desplazamiento interno por teclado, alta/edición, atributos/variantes e imágenes. Edición real de precio restaurada. | 1.1.1, 1.3.1, 1.4.3/4/10/11/12, 2.1.1, 2.4.3/6/7, 3.3.1–2, 4.1.2–3 |
| `/admin`: Ventas, Configuración, medios de pago, Chilexpress, promociones, páginas legales | Tablas, campos y ayuda, nombres y errores, secciones navegables y controles secretos existentes. Editor por teclado, guardado real y restauración. Sin activar pasarelas ni despachos externos. | 1.3.1, 1.4.3/4/10/11/12, 2.1.1, 2.4.3/6/7, 3.3.1–4, 4.1.2–3 |

Reflujo comprobado a **1440×900, 390×844, 768×1024 y 320×844 píxeles CSS**. Las 20 combinaciones de paleta/tipografía se recorren a 320 en vistas representativas de tienda, checkout, panel, formulario y configuración. Las tablas conservan desplazamiento interno utilizable sin desbordar el documento.

La ampliación al **200 %** es independiente del reflujo: `ampliarTexto` toma los tamaños computados y duplica las fuentes de los elementos ya renderizados; comprueba que se duplican y que el viewport no cambia. No usa `transform`, zoom CSS ni reducción de ventana. En una navegación nueva se prueba por separado el espaciado: interlínea 1,5, párrafos 2em, letras 0,12em y palabras 0,16em. Se verifican las cinco tipografías y se repite una selección con servicios reales. Véanse [Resize Text](https://www.w3.org/WAI/WCAG21/Understanding/resize-text.html), [Reflow](https://www.w3.org/WAI/WCAG21/Understanding/reflow.html) y [Text Spacing](https://www.w3.org/WAI/WCAG21/Understanding/text-spacing.html).

La revisión de código también comprobó orientación sin bloqueo, controles de clic simple, ausencia de acciones por foco o movimiento del dispositivo, mensajes sin dependencia exclusiva del color e identificadores/etiquetas. No hay audio, vídeo, destellos, CAPTCHA ni acciones por gestos complejos en las vistas evaluadas; sus criterios específicos no añaden pruebas en este cambio. Esto no constituye una evaluación formal exhaustiva de todos los criterios.

## Reproducción

Usar la configuración privada y el fixture existente según [la guía QA de SCRUM-149](scrum-149-qa.md#credenciales-locales). No imprimir `.env.local` ni la configuración resuelta de Compose. No volver a sembrar una base existente. Los mensajes de variables ausentes y la carga compatible con LF/CRLF se reutilizan sin conversiones nuevas.

Desde `frontend`, sin backend ni credenciales para las suites normales:

```powershell
npm ci
npm run test:run
npm run test:e2e -- --workers=2
$afectados = git diff --name-only 4eaec4b -- '*.js' '*.jsx' |
  Where-Object { $_ -like 'frontend/*' } | ForEach-Object { $_.Substring(9) }
npx eslint $afectados --max-warnings 0
npm run build
```

Para integración real, desde la raíz, reutilizar los servicios QA aislados:

```powershell
docker compose --env-file tools/qa/scrum149/.env.local -p ecode-qa149 -f tools/qa/scrum149/compose.yml config --quiet
docker compose --env-file tools/qa/scrum149/.env.local -p ecode-qa149 -f tools/qa/scrum149/compose.yml up -d --wait
.\venv\Scripts\python.exe tools/qa/scrum149/audit_fixture.py
.\venv\Scripts\python.exe tools/qa/scrum149/manage.py test --noinput
.\venv\Scripts\python.exe tools/qa/scrum149/manage.py check
.\venv\Scripts\python.exe tools/qa/scrum149/manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe tools/qa/scrum149/manage.py runserver 127.0.0.1:8000 --noreload
```

Con ese servidor activo, desde `frontend` y sin otro servidor en 5173:

```powershell
$apiQaAnterior = $env:VITE_API_URL
try {
  $env:VITE_API_URL = 'http://127.0.0.1:8000/api/'
  npm run build
  if ($LASTEXITCODE -ne 0) { throw 'Falló el build de QA' }
} finally { $env:VITE_API_URL = $apiQaAnterior }
npm run test:e2e:qa
# Solo los siete recorridos nuevos, cuando no se necesita repetir catálogo:
npm run test:e2e:a11y:qa
```

Este build local evita la resolución IPv6 intermitente de `localhost` en Edge cuando Django escucha solo en IPv4. No cambia la configuración de producción. Una repetición de ampliación detectó `ERR_CONNECTION_REFUSED` con el destino anterior; después del ajuste pasaron cinco repeticiones consecutivas y la suite conjunta. Las pruebas reales no interceptan respuestas de la API; las normales solo simulan la API y bloquean llamadas inesperadas. No ejecutar ambas suites a la vez sobre 5173.

## Resultados y límites

| Validación ejecutada | Resultado |
|---|---|
| Vitest | 131 pruebas correctas (125 en la base). |
| E2E normal Chromium | 53 correctas; tras el último ajuste de borde se repitieron las siete comprobaciones afectadas de rutas/registro, formulario dinámico y portada, todas correctas. |
| E2E real Edge con PostgreSQL/MongoDB | 11 correctas: siete nuevas y cuatro regresiones existentes. Incluye las cuatro resoluciones, ampliación/espaciado, editor, transferencia/retiro/seguimiento y cambios administrativos restaurados. |
| Backend real | 468 pruebas correctas; `check` sin incidencias y sin migraciones pendientes. Sin cambios funcionales backend. |
| Persistencia | Auditoría de los 1.200 productos correcta; orden QA148 retirada, transferencia deshabilitada y página de reembolsos restaurada. Sin stock descontado, cobros, correos ni despachos reales. |
| Build y ESLint afectado | Correctos, lint con cero errores y advertencias. Se conserva el aviso previo de bundle >500 kB. JS principal: 1.045,48 → 1.051,96 kB minificado (~0,62 %); axe es dependencia de desarrollo y no entra en el producto. |
| Rendimiento y contratos | Una solicitud inicial de configuración y ninguna de filtros separados en catálogo, paginación/filtros/orden y frescura tras editar comprobados por las regresiones QA149. Sin repetir la carga de Javier. |

Recorrido interactivo adicional: catálogo real, última página, categoría, detalle, variante, validación de stock y carrito con Escape. Se comprobó visualmente el foco conservado tras agregar y el formulario estrecho. Las pruebas de diálogo usan navegador real, teclado y reloj controlado; las respuestas de pasarela son simulaciones aisladas. Cerrar/reabrir no envía solicitudes de cancelación, mantiene una sola compra y no duplica consultas ni intervalos.

No se versionan capturas, trazas ni registros completos. Los diagnósticos y capturas locales de revisión quedan en `.tmp/scrum148/`, `.tmp/scrum149/` o `frontend/test-results/`, con exclusiones compartidas; la integración desactiva trazas por las credenciales. Desde la raíz:

```powershell
git check-ignore -v .tmp/scrum148/base.json .tmp/scrum149/browser.json frontend/test-results/.last-run.json
git diff --check
git status --short --untracked-files=all
```

Los resultados cubren los datos y estados descritos. Axe sin infracciones no demuestra conformidad completa. No se realizaron pruebas con lectores de pantalla, Safari/Firefox ni estudio con usuarios; tampoco pagos o despachos externos. El contenido futuro introducido por el negocio necesita su propia revisión. El defecto heredado de páginas vacías del catálogo con sesión administrativa permanece fuera del alcance; los recorridos públicos se hicieron como visitante.
