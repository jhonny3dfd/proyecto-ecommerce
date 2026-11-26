import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda } from './soporte/tienda';

// El índice de Configuración es más alto que la pantalla: queda fijo al bajar, con su propio desplazamiento,
// y marca la sección que se está leyendo, que siempre se ve dentro del índice
test('el índice de Configuración se puede recorrer completo y sigue a la sección actual', async ({ page }) => {
  await prepararTienda(page, { sesion: true });
  await page.setViewportSize({ width: 1280, height: 700 });
  await page.route('**/api/configuracion/**', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', texto_bienvenida: 'Productos de prueba' } }));

  await page.goto('/admin');
  await page.getByRole('button', { name: 'Configuración', exact: true }).click();
  const indice = page.getByRole('navigation', { name: 'Secciones de configuración' });
  await expect(indice.getByRole('button', { name: 'Página de Inicio e Identidad' }))
    .toHaveAttribute('aria-current', 'location');

  // Tiene su propia barra: es más alto por dentro que por fuera y no pasa del alto de la pantalla
  const medidas = await indice.evaluate(nav => ({
    contenido: nav.scrollHeight, visible: nav.clientHeight, alto: nav.getBoundingClientRect().height }));
  expect(medidas.contenido).toBeGreaterThan(medidas.visible);
  expect(medidas.alto).toBeLessThanOrEqual(700);

  // Al bajar hasta el final, la última sección queda marcada y visible dentro del índice
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const ultima = indice.getByRole('button', { name: 'Analítica y marketing' });
  await expect(ultima).toHaveAttribute('aria-current', 'location');
  await expect(ultima).toBeInViewport();
  // El índice sigue fijo arriba
  expect(await indice.evaluate(nav => nav.getBoundingClientRect().top)).toBeLessThanOrEqual(40);

  // Desde el índice se llega a una sección del medio, que queda marcada
  await indice.getByRole('button', { name: 'Medios de Pago' }).click();
  await expect(page.getByRole('heading', { name: 'Medios de Pago', level: 4 })).toBeFocused();
  await expect(indice.getByRole('button', { name: 'Medios de Pago' })).toHaveAttribute('aria-current', 'location');

  expect((await new AxeBuilder({ page }).include('.config-indice').analyze()).violations).toEqual([]);
});

test('en el celular el índice va arriba, completo y sin barra propia', async ({ page }) => {
  await prepararTienda(page, { sesion: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/configuracion/**', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', texto_bienvenida: 'Productos de prueba' } }));

  await page.goto('/admin');
  await page.getByRole('button', { name: 'Configuración', exact: true }).click();
  const indice = page.getByRole('navigation', { name: 'Secciones de configuración' });
  await expect(indice.getByRole('button', { name: 'Analítica y marketing' })).toBeAttached();
  const medidas = await indice.evaluate(nav => ({ contenido: nav.scrollHeight, visible: nav.clientHeight,
    posicion: getComputedStyle(nav).position }));
  expect(medidas.contenido).toBeLessThanOrEqual(medidas.visible);
  expect(medidas.posicion).toBe('static');
});
