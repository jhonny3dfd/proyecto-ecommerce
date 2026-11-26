import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { metricasDashboard, prepararTienda } from './soporte/tienda';

test('el editor legal tiene nombre y formato operable con teclado', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  let guardado;
  await page.route('**/api/ventas/admin/paginas-legales/terminos/', async route => {
    guardado = route.request().postDataJSON();
    await route.fulfill({ json: { ...guardado, tipo_pagina: 'TERMINOS' } });
  });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Páginas legales', exact: true }).click();
  const editor = page.getByRole('textbox', { name: 'Contenido:' });
  await expect(editor).toHaveAttribute('aria-multiline', 'true');
  await editor.fill('Contenido accesible de prueba.');
  const selector = page.getByRole('button', { name: 'Nivel de encabezado', exact: true });
  await selector.focus();
  await page.keyboard.press('Enter');
  await expect(selector).toHaveAttribute('aria-expanded', 'true');
  await page.getByRole('button', { name: 'Encabezado de nivel 2' }).press('Enter');
  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).press('Enter');
  await expect(page.getByRole('status')).toContainText('guardada y publicada');
  expect(guardado.contenido).toContain('Contenido accesible de prueba.');
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
  expect(inesperadas).toEqual([]);
});

test('las cifras del gráfico también se pueden consultar como tabla', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.route('**/api/ventas/dashboard/metricas/**', route => route.fulfill({ json: {
    ...metricasDashboard,
    tarjetas: { ...metricasDashboard.tarjetas, ventas: 1480, pedidos: 1, ticket_promedio: 1480 },
    serie: [{ fecha: '2026-11-02', total: 1480, pedidos: 1 }],
  } }));
  await page.goto('/admin');
  const resumen = page.getByText('Ver los datos del gráfico', { exact: true });
  await resumen.focus();
  await page.keyboard.press('Enter');
  const region = page.getByRole('region', { name: 'Datos de las ventas del periodo' });
  await expect(region).toContainText('02/11');
  await expect(region).toContainText('$1.480');
  await region.focus();
  await expect(region).toBeFocused();
  expect(inesperadas).toEqual([]);
});
