import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto } from './soporte/tienda';

// Detiene las respuestas que coinciden hasta llamar a soltar(); después siguen a las respuestas de prepararTienda
async function retener(page, patron, metodo) {
  let soltar;
  const suelta = new Promise(resolve => { soltar = resolve; });
  await page.route(patron, async route => {
    if (metodo && route.request().method() !== metodo) return route.fallback();
    await suelta;
    return route.fallback();
  });
  return soltar;
}

async function sinViolaciones(page) {
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
}

const animacion = (locator) => locator.first().evaluate(elemento => getComputedStyle(elemento).animationName);

test('el catálogo muestra tarjetas vacías mientras carga, nunca "0 productos"', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page);
  const soltar = await retener(page, '**/api/catalogo/productos/**');

  await page.goto('/catalogo');
  await expect(page.getByRole('status').filter({ hasText: 'Cargando productos...' })).toBeAttached();
  await expect(page.locator('.tarjeta-producto .esqueleto').first()).toBeVisible();
  await expect(page.getByText('0 productos')).toHaveCount(0);
  await expect(page.getByText('No hay productos para mostrar.')).toHaveCount(0);
  await sinViolaciones(page);

  soltar();
  await expect(page.getByRole('heading', { name: producto.nombre })).toBeVisible();
  await expect(page.getByText('1 producto', { exact: true })).toBeVisible();
  await expect(page.locator('.esqueleto')).toHaveCount(0);
  expect(inesperadas).toEqual([]);
});

test('el panel se ve entero mientras se verifica la sesión y el dashboard mientras llegan las cifras', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  const soltarSesion = await retener(page, '**/api/usuarios/me/');
  const soltarMetricas = await retener(page, '**/api/ventas/dashboard/**');

  await page.goto('/admin');
  await expect(page.getByRole('status').filter({ hasText: 'Verificando sesión...' })).toBeAttached();
  await expect(page.locator('.admin-barra .esqueleto').first()).toBeVisible();
  await expect(page.getByRole('main')).toHaveAttribute('id', 'contenido');
  await sinViolaciones(page);

  soltarSesion();
  await expect(page.getByRole('navigation', { name: 'Secciones del panel' })).toBeVisible();
  await expect(page.getByRole('status').filter({ hasText: 'Cargando información...' })).toBeAttached();
  await expect(page.locator('.admin-indicador .esqueleto').first()).toBeVisible();
  await sinViolaciones(page);

  soltarMetricas();
  await expect(page.getByRole('heading', { name: 'Ventas del periodo' })).toBeVisible();
  await expect(page.getByText(/Todo al día/)).toBeVisible();
  await expect(page.locator('.esqueleto')).toHaveCount(0);
  expect(inesperadas).toEqual([]);
});

test('un botón muestra el spinner mientras guarda y lo quita al terminar', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Configuración', exact: true }).click();
  const soltar = await retener(page, '**/api/configuracion/negocio/', 'PATCH');

  const guardar = page.getByRole('button', { name: 'Guardar dirección y opciones de retiro' });
  await guardar.scrollIntoViewIfNeeded();
  await guardar.click();
  const guardando = page.getByRole('button', { name: 'Guardando...' });
  await expect(guardando).toBeDisabled();
  await expect(guardando.locator('.spinner')).toBeVisible();
  expect(await animacion(guardando.locator('.spinner'))).toBe('spinner-giro');

  soltar();
  await expect(page.getByText(/actualizados con éxito/)).toBeVisible();
  await expect(guardar.locator('.spinner')).toHaveCount(0);
  expect(inesperadas).toEqual([]);
});

test('el brillo del esqueleto se mueve, y con "reducir movimiento" queda quieto', async ({ page }) => {
  await prepararTienda(page);
  await retener(page, '**/api/catalogo/productos/**');

  await page.goto('/catalogo');
  const bloques = page.locator('.esqueleto');
  await expect(bloques.first()).toBeVisible();
  expect(await animacion(bloques)).toBe('esqueleto-brillo');

  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect(await animacion(bloques)).toBe('none');
});
