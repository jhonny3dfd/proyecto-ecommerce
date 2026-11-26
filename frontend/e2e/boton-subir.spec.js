import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto } from './soporte/tienda';

// Una página llena del catálogo (24 productos) de un total de 3 páginas, para poder bajar y ver la paginación
const productos = Array.from({ length: 24 }, (_, i) => ({
  ...producto, id: `0000000000000000000001${String(i).padStart(2, '0')}`, nombre: `Producto ${i + 1}`,
  variantes: [{ ...producto.variantes[0], sku: `QA-${i + 1}` }],
}));

async function catalogoLargo(page, ancho) {
  await prepararTienda(page);
  await page.route(/\/api\/catalogo\/productos\/(\?.*)?$/, route => route.fulfill({ json: {
    count: 72, total_pages: 3, current_page: 1, results: productos } }));
  await page.setViewportSize({ width: ancho, height: 800 });
  await page.goto('/catalogo');
  await expect(page.getByRole('heading', { name: 'Producto 24' })).toBeAttached();
}

for (const ancho of [1280, 390]) {
test(`el botón para subir aparece solo al bajar en el catálogo y lleva al inicio (${ancho}px)`, async ({ page }) => {
  await catalogoLargo(page, ancho);
  const boton = page.getByRole('button', { name: 'Volver al inicio de la página' });
  await expect(page.getByRole('navigation', { name: 'Paginación del catálogo' })).toBeAttached();

  // Arriba no está
  await expect(boton).toHaveCount(0);

  // Al bajar aparece, abajo a la derecha y dentro de la pantalla
  await page.mouse.wheel(0, 1500);
  await expect(boton).toBeVisible();
  const caja = await boton.boundingBox();
  expect(caja.x + caja.width).toBeGreaterThan(ancho - 40);
  expect(caja.y + caja.height).toBeGreaterThan(800 - 40);
  expect(caja.width).toBeGreaterThanOrEqual(44);
  expect((await new AxeBuilder({ page }).include('.boton-subir').analyze()).violations).toEqual([]);

  // Lleva al inicio, el foco queda al comienzo del contenido y el botón desaparece
  await boton.click();
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await expect(page.locator('main#contenido')).toBeFocused();
  await expect(boton).toHaveCount(0);
});
}

test('el botón para subir también funciona con el teclado', async ({ page }) => {
  await catalogoLargo(page, 1280);
  await page.evaluate(() => window.scrollTo(0, 2000));
  const boton = page.getByRole('button', { name: 'Volver al inicio de la página' });
  await expect(boton).toBeVisible();
  await boton.focus();
  await page.keyboard.press('Enter');
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
  await expect(boton).toHaveCount(0);
});
