import { test, expect } from '@playwright/test';
import { prepararTienda } from './soporte/tienda';
import AxeBuilder from '@axe-core/playwright';

for (const ancho of [320, 390, 1280]) {
  test(`menú personalizado accesible sin desbordamiento a ${ancho}px`, async ({ page }) => {
    await prepararTienda(page);
    await page.setViewportSize({ width: ancho, height: 900 });
    await page.route('**/api/configuracion/', route => route.fulfill({ json: {
      nombre_tienda: 'Tienda QA', blog_activo: true, sobre_mi_activo: true, cotizaciones_activas: true,
      blog_nombre: 'Nuestros proyectos y trabajos', sobre_mi_nombre: 'Historia de nuestro negocio',
      menu_principal: { orden: ['cotizar', 'sobre_mi', 'nosotros', 'catalogo', 'inicio'], nombres: {
        inicio: 'Inicio personalizado de tienda', catalogo: 'Catálogo personalizado extenso',
        nosotros: 'Nuestros proyectos y trabajos', sobre_mi: 'Historia de nuestro negocio', cotizar: 'Cotizaciones personalizadas'
      } }
    } }));
    await page.goto('/');
    const enlaces = page.locator('.header-links a');
    // Solo Catálogo usa su nombre personalizado; los antiguos de Inicio y Cotizar se ignoran
    await expect(enlaces).toHaveText(['Cotizar', 'Historia de nuestro negocio', 'Nuestros proyectos y trabajos', 'Catálogo personalizado extenso', 'Inicio']);
    expect(await enlaces.evaluateAll(nodos => nodos.map(nodo => nodo.getAttribute('href')))).toEqual(['/cotizar', '/sobre-mi', '/blog', '/catalogo', '/']);
    for (let indice = 0; indice < 5; indice++) {
      const caja = await enlaces.nth(indice).boundingBox();
      expect(caja.x).toBeGreaterThanOrEqual(0);
      expect(caja.x + caja.width).toBeLessThanOrEqual(ancho);
    }
    await enlaces.first().focus();
    await page.keyboard.press('Tab');
    await expect(enlaces.nth(1)).toBeFocused();
    expect((await new AxeBuilder({ page }).include('header').analyze()).violations).toEqual([]);
  });
}

test('el salto por teclado y los títulos acompañan la navegación sin repetir configuración', async ({ page }) => {
  const { inesperadas, llamadas } = await prepararTienda(page);
  await page.goto('/');
  await expect(page).toHaveTitle('Inicio · Tienda QA');
  expect(llamadas.filter(llamada => llamada.ruta === 'configuracion/')).toHaveLength(1);
  await page.getByRole('link', { name: 'Saltar al contenido' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('main')).toBeFocused();
  await page.locator('header').getByRole('link', { name: 'Catálogo', exact: true }).click();
  await expect(page).toHaveTitle('Catálogo · Tienda QA');
  await expect(page.locator('main')).toBeFocused();
  await expect(page.locator('main')).toHaveCount(1);
  expect(llamadas.filter(llamada => llamada.ruta === 'configuracion/')).toHaveLength(2);
  expect(inesperadas).toEqual([]);
});

test('Escape devuelve el foco del carrito y de la cuenta al botón que los abrió', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.goto('/login');
  for (const nombre of [/Carrito de compras/, /Menú de usuario/]) {
    const boton = page.getByRole('button', { name: nombre });
    await boton.focus();
    await page.keyboard.press('Enter');
    await expect(boton).toHaveAttribute('aria-expanded', 'true');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Escape');
    await expect(boton).toHaveAttribute('aria-expanded', 'false');
    await expect(boton).toBeFocused();
  }
  expect(inesperadas).toEqual([]);
});
