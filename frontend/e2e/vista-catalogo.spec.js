import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda } from './soporte/tienda';

// RF-01.4: el admin elige la vista del catálogo en Configuración > Apariencia y el catálogo público la aplica
for (const ancho of [390, 1280]) {
  test(`el admin elige la vista del catálogo y la tienda la muestra (${ancho}px)`, async ({ page }) => {
    await prepararTienda(page, { sesion: true });
    await page.setViewportSize({ width: ancho, height: 900 });
    let config = { nombre_tienda: 'Tienda QA', texto_bienvenida: 'Productos de prueba', layout_catalogo: 'GRID_3' };
    const guardados = [];
    await page.route('**/api/configuracion/**', async route => {
      if (route.request().method() === 'PATCH') {
        guardados.push(route.request().postDataJSON());
        config = { ...config, ...guardados.at(-1) };
      }
      await route.fulfill({ json: config });
    });

    await page.goto('/admin');
    await page.getByRole('button', { name: 'Configuración', exact: true }).click();
    const indice = page.getByRole('navigation', { name: 'Secciones de configuración' });
    await indice.getByRole('button', { name: 'Vista del catálogo', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Vista del catálogo', level: 4 })).toBeFocused();

    const vistas = page.getByRole('group', { name: 'Vistas del catálogo', exact: true });
    await expect(vistas.getByRole('button', { name: /Cuadrícula de 3/, pressed: true })).toBeVisible();
    await vistas.getByRole('button', { name: /Lista con descripción/ }).click();
    expect((await new AxeBuilder({ page }).include('.selector-vistas-catalogo').analyze()).violations).toEqual([]);
    await page.getByRole('button', { name: 'Guardar vista del catálogo', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Vista guardada' })).toBeVisible();
    expect(guardados.at(-1)).toEqual({ layout_catalogo: 'LISTA' });

    await page.goto('/catalogo');
    await expect(page.locator('ul.catalogo-lista')).toBeVisible();
  });
}
