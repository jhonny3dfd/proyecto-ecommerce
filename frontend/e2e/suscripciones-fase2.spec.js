import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto, comprobarVista } from './soporte/tienda';

// API simulada: esta suite normal funciona sin backend, cuentas ni datos reales.
const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const exclusivo = { ...producto, id: '000000000000000000000202', nombre: 'Café exclusivo', solo_suscriptores: true,
  planes_suscripcion: [2], variantes: [{ sku: 'EXC-202', precio: 1000, stock: 5, atributos_variables: {} }] };
const plan = { id: 2, nombre: 'Mensual', activo: true };

test('sin suscripciones no hay enlace ni página de cumpleaños ni lectura de la fecha', async ({ page }) => {
  const tienda = await prepararTienda(page, { sesion: true });
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', suscripciones_activas: false,
  } }));
  let consultas = 0;
  await page.route('**/api/usuarios/cumpleanos/', route => { consultas++; return route.fulfill({ status: 404, json: {} }); });
  await page.goto('/catalogo');
  await page.getByRole('button', { name: /Menú de usuario/ }).click();
  await expect(page.getByRole('link', { name: 'Mi cumpleaños', exact: true })).toHaveCount(0);
  await page.goto('/mi-cumpleanos');
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('heading', { name: 'Mi cumpleaños', exact: true })).toHaveCount(0);
  expect(consultas).toBe(0);
  expect(tienda.inesperadas).toEqual([]);
});

async function preparar(page, { sesion = false, tema = 1 } = {}) {
  const tienda = await prepararTienda(page, { sesion, tema });
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', suscripciones_activas: true, tema_seleccionado: tema,
    retiro_en_local_activo: true, pasarelas_activas: ['TRANSFERENCIA'], couriers: [],
  } }));
  await page.route(`**/api/catalogo/productos/${exclusivo.id}/`, route => route.fulfill({ json: exclusivo }));
  await page.route('**/api/ventas/admin/suscripciones/planes/', route => route.fulfill({ json: { planes: [plan] } }));
  return tienda;
}

test('el comprador guarda y elimina su cumpleaños usando el teclado, sin año', async ({ page }) => {
  const tienda = await preparar(page, { sesion: true });
  let fecha = { dia: null, mes: null };
  await page.route('**/api/usuarios/cumpleanos/', async route => {
    if (route.request().method() === 'PATCH') fecha = route.request().postDataJSON();
    return route.fulfill({ json: fecha });
  });
  await page.goto('/mi-cumpleanos');
  await page.getByLabel('Día', { exact: true }).fill('29');
  await page.getByLabel('Mes', { exact: true }).selectOption('2');
  await page.getByRole('button', { name: 'Guardar cumpleaños' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toContainText('quedó guardado');
  expect(fecha).toEqual({ dia: 29, mes: 2 });
  await page.reload();
  await expect(page.getByLabel('Día', { exact: true })).toHaveValue('29');
  await page.getByRole('button', { name: 'Eliminar cumpleaños' }).click();
  await expect(page.getByRole('status')).toContainText('se eliminó');
  expect(fecha).toEqual({ dia: null, mes: null });
  expect(tienda.inesperadas).toEqual([]);
});

test('el panel muestra la dirección y la próxima entrega y registra un único regalo', async ({ page }) => {
  const tienda = await preparar(page, { sesion: true });
  let enviado = false;
  let marcas = 0;
  await page.route('**/api/ventas/admin/suscripciones/cumpleanos/**', async route => {
    if (route.request().method() === 'POST') {
      enviado = true; marcas += 1;
      return route.fulfill({ json: { anio: 2026, regalo_enviado: true } });
    }
    return route.fulfill({ json: { count: 1, anio: 2026, next: null, results: [{
      usuario_id: 7, nombre: 'Ana Prueba', dia: 29, mes: 2, proxima_entrega: '2026-12-01', plan: 'Mensual',
      direccion: 'Calle de prueba 202', direccion_envio: { calle: 'Calle de prueba', numero: '202', dpto_casa: 'Depto. 4' },
      regalo_enviado: enviado,
    }] } });
  });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Cumpleaños del mes', exact: true }).click();
  await page.getByLabel('Mes de cumpleaños').selectOption('2');
  await expect(page.getByText('1 de diciembre de 2026')).toBeVisible();
  await expect(page.getByText(/Calle de prueba, 202, Depto. 4/)).toBeVisible();
  const casilla = page.getByRole('checkbox', { name: 'Regalo enviado a Ana Prueba en 2026' });
  await casilla.focus(); await page.keyboard.press('Space');
  await expect(casilla).toBeChecked(); await expect(casilla).toBeDisabled();
  expect(marcas).toBe(1);
  await comprobarVista(page);
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  expect(tienda.inesperadas).toEqual([]);
});

test('un suscriptor compra y la validación del servidor impide agregar al perder el acceso', async ({ page }) => {
  await preparar(page, { sesion: true });
  let vigente = true;
  await page.route('**/api/ventas/suscripciones/acceso-exclusivos/', route => route.fulfill({ json: { planes_vigentes: [2] } }));
  await page.route('**/api/ventas/carrito/validar/', route => route.fulfill({ json: {
    valido: vigente, items: [{ producto_mongo_id: exclusivo.id, variante_sku: 'EXC-202', disponible: vigente ? 5 : 0,
      precio: '1000', problema: vigente ? null : 'SUSCRIPCION_REQUERIDA',
      mensaje: vigente ? null : 'Necesitas una suscripción vigente.' }],
  } }));
  await page.goto(`/catalogo/producto/${exclusivo.id}`);
  await page.getByRole('button', { name: /Agregar al carrito/i }).click();
  await expect(page.getByText(/Agregaste 1 unidad/)).toBeVisible();
  vigente = false;
  await page.getByRole('button', { name: /Agregar al carrito/i }).click();
  await expect(page.getByText(/Necesitas una suscripción vigente/)).toBeVisible();
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('carrito_local'))
    .find(item => item.sku === 'EXC-202').cantidad)).toBe(1);
});

for (const tema of [1, 2, 3, 4, 5, 6, 7, 8]) {
  test(`exclusivo y cumpleaños cumplen accesibilidad en paleta ${tema}, escritorio y celular`, async ({ page }) => {
    const tienda = await preparar(page, { tema });
    await page.route('**/api/usuarios/cumpleanos/', route => route.fulfill({ json: { dia: 29, mes: 2 } }));
    await page.goto('/catalogo');
    for (const ancho of [1440, 390, 320]) {
      await page.evaluate(() => localStorage.removeItem('access_token'));
      await page.setViewportSize({ width: ancho, height: 900 });
      await page.goto(`/catalogo/producto/${exclusivo.id}`);
      await expect(page.getByText('Exclusivo suscriptores')).toBeVisible();
      await expect(page.getByRole('link', { name: 'Ver planes de Suscripción' })).toHaveAttribute('href', '/suscripcion');
      await expect(page.getByRole('button', { name: /Agregar al carrito/ })).toHaveCount(0);
      await comprobarVista(page);
      expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
      await page.evaluate(() => localStorage.setItem('access_token', 'sesion-simulada'));
      await page.goto('/mi-cumpleanos');
      await expect(page.getByRole('heading', { name: 'Mi cumpleaños', exact: true })).toBeVisible();
      await expect(page).toHaveTitle(/Mi cumpleaños/);
      await comprobarVista(page);
      expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
    }
    await page.route('**/api/ventas/admin/suscripciones/cumpleanos/**', route => route.fulfill({ json: {
      count: 1, anio: 2026, next: null, results: [{ usuario_id: 7, nombre: 'Ana Prueba', dia: 11, mes: 11,
        direccion: 'Retiro en el local', proxima_entrega: '2026-12-01', plan: 'Mensual', regalo_enviado: false }],
    } }));
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Cumpleaños del mes', exact: true }).click();
    await expect(page.getByRole('checkbox', { name: /Regalo enviado a Ana/ })).toBeVisible();
    await comprobarVista(page);
    expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Inventario', exact: true }).click();
    await page.getByRole('button', { name: /Agregar producto/i }).click();
    await page.getByLabel('Solo para suscriptores', { exact: true }).check();
    await expect(page.getByRole('checkbox', { name: 'Mensual', exact: true })).toBeVisible();
    await comprobarVista(page);
    expect((await new AxeBuilder({ page }).include('.campo-exclusivo').withTags(WCAG).analyze()).violations).toEqual([]);
    expect(tienda.inesperadas).toEqual([]);
  });
}

test('el formulario muestra la restricción con el módulo y la oculta al apagarlo', async ({ page }) => {
  await preparar(page, { sesion: true });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  await page.getByRole('button', { name: /Agregar producto/i }).click();
  const casilla = page.getByLabel('Solo para suscriptores', { exact: true });
  await casilla.check();
  await page.getByRole('checkbox', { name: 'Mensual', exact: true }).check();
  await expect(page.getByRole('group', { name: 'Planes permitidos' })).toBeVisible();
  expect((await new AxeBuilder({ page }).include('.campo-exclusivo').withTags(WCAG).analyze()).violations).toEqual([]);
  await page.route('**/api/configuracion/', route => route.fulfill({ json: { nombre_tienda: 'QA', suscripciones_activas: false } }));
  await page.reload();
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  await page.getByRole('button', { name: /Agregar producto/i }).click();
  await expect(casilla).toHaveCount(0);
});

test('el catálogo conserva la etiqueta y el enlace en sus tres vistas', async ({ page }) => {
  const tienda = await preparar(page);
  await page.route('**/api/catalogo/productos/?*', route => route.fulfill({ json: {
    count: 1, total_pages: 1, current_page: 1, results: [exclusivo],
    filtros: { categorias: ['Prueba'], atributos: {} },
  } }));
  for (const layout of ['GRID_3', 'GRID_4', 'LISTA']) {
    await page.route('**/api/configuracion/', route => route.fulfill({ json: {
      nombre_tienda: 'Tienda QA', suscripciones_activas: true, layout_catalogo: layout,
    } }));
    await page.goto('/catalogo');
    await expect(page.getByText('Exclusivo suscriptores')).toBeVisible();
    await expect(page.getByRole('main').getByRole('link', { name: 'Suscripción', exact: true })).toBeVisible();
    expect(await page.locator('a a').count()).toBe(0);
    await comprobarVista(page);
  }
  expect(tienda.inesperadas).toEqual([]);
});
