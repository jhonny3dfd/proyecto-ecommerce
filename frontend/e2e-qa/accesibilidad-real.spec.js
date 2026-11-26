import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import process from 'node:process';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { medirVista, ampliarTexto, espaciarTexto } from '../e2e/soporte/mediciones';

const API = 'http://127.0.0.1:8000/api/';
test.setTimeout(120_000);

test.beforeAll(async ({ request }) => {
  const faltantes = ['QA149_ADMIN_EMAIL', 'QA149_ADMIN_PASSWORD'].filter(nombre => !process.env[nombre]?.trim());
  if (faltantes.length) throw new Error(`Faltan variables de QA: ${faltantes.join(', ')}. Configure tools/qa/scrum149/.env.local o la sesión.`);
  const respuesta = await request.get(API + 'catalogo/productos/');
  expect(respuesta.ok(), 'El backend QA debe estar disponible').toBeTruthy();
  const catalogo = await respuesta.json();
  expect(catalogo.count, 'Se requiere el fixture QA149 aislado').toBe(1080);
  expect(catalogo.results[0].nombre).toMatch(/^Producto QA149 /);
});

async function iniciarSesion(page) {
  const respuesta = await page.request.post(API + 'usuarios/token/', {
    data: { email: process.env.QA149_ADMIN_EMAIL, password: process.env.QA149_ADMIN_PASSWORD },
  });
  if (!respuesta.ok()) throw new Error('No se pudo iniciar la sesión administrativa QA');
  const tokens = await respuesta.json();
  await page.evaluate(tokens => {
    localStorage.setItem('access_token', tokens.access);
    localStorage.setItem('refresh_token', tokens.refresh);
    localStorage.setItem('rol', 'ADMIN');
  }, tokens);
  return { Authorization: `Bearer ${tokens.access}` };
}

async function analizar(page) {
  const resultado = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  // Conservar solo el diagnóstico necesario; nunca respuestas HTTP, tokens o campos privados.
  expect(resultado.violations.map(({ id, nodes }) => ({ id, elementos: nodes.map(nodo => nodo.target) }))).toEqual([]);
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 320, height: 844 }]) {
  test(`tienda y panel reales: ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errores = [];
    page.on('pageerror', error => errores.push(error.message));
    await page.goto('/');
    await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
    for (const ruta of ['/', '/catalogo', '/catalogo/producto/000000000000000000000060', '/login', '/checkout', '/seguimiento', '/legal/terminos', '/variantes', '/pedido-recibido', '/pago-exitoso', '/pago-cancelado', '/pago-rechazado']) {
      await page.goto(ruta, { waitUntil: 'domcontentloaded' });
      await medirVista(page);
    }
    await analizar(page);
    await iniciarSesion(page);
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Inventario', exact: true }).click();
    const expandir = page.getByRole('button', { name: /^Mostrar variantes de/ }).first();
    await expandir.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: /^Ocultar variantes de/ }).first()).toHaveAttribute('aria-expanded', 'true');
    await medirVista(page);
    const tabla = page.getByRole('region', { name: 'Inventario de productos y variantes' });
    await tabla.focus();
    await expect(tabla).toBeFocused();
    await page.keyboard.press('ArrowRight');
    await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
    await medirVista(page);
    await analizar(page);
    await expect(page.getByRole('button', { name: 'Crear Producto', exact: true })).toBeVisible();
    if (viewport.width === 320) {
      await page.getByLabel('SKU', { exact: true }).scrollIntoViewIfNeeded();
      await page.screenshot({ path: testInfo.outputPath('revision-formulario-320.png') });
    }
    for (const vista of ['Ventas', 'Configuración', 'Páginas legales']) {
      await page.getByRole('button', { name: vista, exact: true }).click();
      if (vista === 'Páginas legales') await expect(page.getByRole('textbox', { name: 'Contenido:' })).toBeVisible();
      await medirVista(page);
      await analizar(page);
    }
    for (const ruta of ['/mis-direcciones', '/mis-pedidos']) {
      await page.goto(ruta);
      await medirVista(page);
      await analizar(page);
    }
    expect(errores).toEqual([]);
  });
}

test('texto al 200 % y espaciado se verifican por separado con servicios reales', async ({ page }) => {
  const fallosRed = [];
  page.on('requestfailed', peticion => fallosRed.push({ ruta: new URL(peticion.url()).pathname, motivo: peticion.failure()?.errorText }));
  page.on('response', respuesta => {
    if (respuesta.status() >= 400) fallosRed.push({ ruta: new URL(respuesta.url()).pathname, estado: respuesta.status() });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/login');
  await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
  await iniciarSesion(page);
  for (const ajuste of ['ampliacion', 'espaciado']) {
    for (const ruta of ['/login', '/checkout', '/legal/terminos', '/admin']) {
      await page.goto(ruta);
      await medirVista(page);
      if (ajuste === 'ampliacion') await ampliarTexto(page);
      else await espaciarTexto(page);
      await medirVista(page);
    }
    await page.goto('/admin');
    await expect(page, JSON.stringify(fallosRed)).toHaveURL(/\/admin$/, { timeout: 10_000 });
    await page.getByRole('button', { name: 'Inventario', exact: true }).click();
    await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
    if (ajuste === 'ampliacion') await ampliarTexto(page);
    else await espaciarTexto(page);
    await medirVista(page);
  }
});

test('el editor guarda contenido real y restaura la página QA', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
  const headers = await iniciarSesion(page);
  const paginas = await (await page.request.get(API + 'ventas/admin/paginas-legales/', { headers })).json();
  const original = paginas.find(pagina => pagina.tipo_pagina === 'REEMBOLSOS');
  const ruta = API + 'ventas/admin/paginas-legales/reembolsos/';
  try {
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Páginas legales', exact: true }).click();
    await page.getByLabel('Selecciona la página a editar:').selectOption('REEMBOLSOS');
    await page.getByRole('textbox', { name: 'Contenido:' }).fill('Contenido ficticio de accesibilidad SCRUM-148.');
    await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('guardada como borrador');
    const actual = await (await page.request.get(API + 'ventas/admin/paginas-legales/', { headers })).json();
    expect(actual.find(pagina => pagina.tipo_pagina === 'REEMBOLSOS').contenido).toContain('Contenido ficticio de accesibilidad SCRUM-148.');
  } finally {
    expect((await page.request.put(ruta, { headers, data: { titulo: original.titulo, contenido: original.contenido, publicada: original.publicada } })).ok()).toBeTruthy();
  }
});

test('checkout y seguimiento reales usan transferencia y retiro sin servicios externos', async ({ page }) => {
  await page.goto('/login');
  await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
  const headers = await iniciarSesion(page);
  const medios = await (await page.request.get(API + 'ventas/admin/medios-pago/', { headers })).json();
  const original = medios.find(medio => medio.codigo === 'TRANSFERENCIA');
  expect(original.habilitado, 'El fixture QA debe tener transferencia deshabilitada').toBe(false);
  expect(original.datos.verificar_con_linkify || 'No').toBe('No');
  const rutaMedio = API + 'ventas/admin/medios-pago/transferencia/';
  let ordenId;
  const compras = [];
  page.on('request', peticion => {
    if (new URL(peticion.url()).pathname === '/api/ventas/checkout/' && peticion.method() === 'POST') compras.push(true);
  });
  try {
    const habilitar = await page.request.put(rutaMedio, { headers, data: { habilitado: true, datos: {
      banco: 'Banco ficticio QA', tipo_cuenta: 'Cuenta vista', numero_cuenta: '000148',
      rut_titular: '11.111.111-1', nombre_titular: 'Titular ficticio QA', email: 'qa148@example.test', verificar_con_linkify: 'No',
    } } });
    expect(habilitar.ok()).toBeTruthy();
    const producto = await (await page.request.get(API + 'catalogo/productos/000000000000000000000060/')).json();
    const variante = producto.variantes[0];
    const precio = variante.precio_oferta && Number(variante.precio_oferta) < Number(variante.precio) ? Number(variante.precio_oferta) : Number(variante.precio);
    await page.evaluate(item => localStorage.setItem('carrito_local', JSON.stringify([item])), {
      id: producto.id, sku: variante.sku, nombre: producto.nombre, precio, cantidad: 1,
    });
    await page.goto('/checkout');
    await page.getByRole('radio', { name: /retiro en local/i }).focus();
    await page.keyboard.press('Space');
    await page.getByLabel(/Nombre de quien recibe/).fill('Comprador QA148');
    await page.getByLabel(/Teléfono de contacto/).fill('+56911111111');
    await page.getByRole('checkbox', { name: /acepto los/i }).check();
    const respuesta = page.waitForResponse(respuesta => new URL(respuesta.url()).pathname === '/api/ventas/checkout/' && respuesta.request().method() === 'POST');
    await page.getByRole('button', { name: 'Pagar con Transferencia bancaria', exact: true }).click();
    const compra = await respuesta;
    expect(compra.ok()).toBeTruthy();
    ordenId = Number((await compra.json()).orden_id);
    expect(Number.isSafeInteger(ordenId)).toBeTruthy();
    await expect(page).toHaveURL(/pedido-recibido\?orden=/);
    await expect(page.getByRole('heading', { name: 'Datos para transferir' })).toBeVisible();
    expect(compras).toHaveLength(1);
    const ordenes = await (await page.request.get(API + 'ventas/admin/ordenes/', { headers })).json();
    const orden = ordenes.find(orden => orden.id === ordenId);
    expect(orden.estado).toBe('PENDIENTE');
    expect(orden.proveedor_logistico).toBe('RETIRO_LOCAL');
    await page.goto(`/seguimiento?orden=${ordenId}`);
    await page.getByLabel('Correo electrónico', { exact: true }).fill(process.env.QA149_ADMIN_EMAIL);
    await page.getByRole('button', { name: 'Consultar seguimiento', exact: true }).click();
    await expect(page.getByRole('heading', { name: `Pedido #${ordenId}`, exact: true })).toBeFocused();
    await medirVista(page);
  } finally {
    try {
      if (Number.isSafeInteger(ordenId)) {
        const cancelar = await page.request.patch(API + `ventas/admin/ordenes/${ordenId}/estado/`, { headers, data: { estado: 'CANCELADO' } });
        expect(cancelar.ok()).toBeTruthy();
        // Reutilizar el administrador y los modelos existentes para retirar solo la orden ficticia
        // de esta ejecución. Las guardas impiden tocar otra base, una venta pagada o stock descontado.
        const raiz = fileURLToPath(new URL('../..', import.meta.url));
        const python = join(raiz, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
        execFileSync(python, ['tools/qa/scrum149/manage.py', 'shell', '-c',
          `from django.conf import settings; from ecommerce.infrastructure.ventas.models import OrdenCompra; assert settings.DATABASES['default']['NAME'] == 'ecode_qa_scrum149'; orden = OrdenCompra.objects.get(pk=${ordenId}); assert orden.nombre_destinatario == 'Comprador QA148' and orden.metodo_pago == 'TRANSFERENCIA' and orden.estado == 'CANCELADO' and not orden.stock_descontado; orden.delete()`], { cwd: raiz, stdio: 'pipe' });
      }
    } finally {
      expect((await page.request.put(rutaMedio, { headers, data: { habilitado: original.habilitado, datos: original.datos } })).ok()).toBeTruthy();
    }
  }
});
