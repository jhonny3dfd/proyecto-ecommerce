import { test, expect } from '@playwright/test';
import { prepararTienda } from './soporte/tienda';

test('inventario permite expandir y abrir el formulario con teclado', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  const expandir = page.getByRole('button', { name: /^(Mostrar|Ocultar) variantes de Producto de prueba$/ });
  await expandir.focus();
  await page.keyboard.press('Space');
  await expect(expandir).toHaveAttribute('aria-expanded', 'true');
  await expect(page.getByText('QA-1', { exact: true })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(expandir).toHaveAttribute('aria-expanded', 'false');
  await page.getByRole('button', { name: 'Editar Producto de prueba', exact: true }).press('Enter');
  await expect(page.getByLabel('Nombre del Producto', { exact: true })).toHaveValue('Producto de prueba');
  await expect(page.getByRole('button', { name: 'Cerrar formulario de producto' })).toBeVisible();
  await page.getByRole('button', { name: 'Cerrar formulario de producto' }).press('Enter');
  await expect(page.getByRole('button', { name: 'Mostrar variantes de Producto de prueba' })).toBeVisible();
  expect(inesperadas).toEqual([]);
});

test('la galería del formulario de producto ocupa todo el ancho de los campos en el computador', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
  // Va dentro de la grilla de campos (.producto-campos): antes quedaba en una de sus 4 columnas, de unos 200 px
  const [galeria, grilla] = await page.locator('.galeria-zona').evaluate((zona) => [
    zona.parentElement.getBoundingClientRect().width, zona.closest('.producto-campos').getBoundingClientRect().width,
  ]);
  expect(galeria).toBeCloseTo(grilla, 0);
  // La categoría comparte su columna con "+ Nueva": con columnas de 160 px el selector quedaba en "Selecc…"
  const selector = await page.getByLabel('Categoría', { exact: true }).boundingBox();
  expect(selector.width).toBeGreaterThan(140);
  expect(inesperadas).toEqual([]);
});
