import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto } from './soporte/tienda';

for (const ancho of [390, 1280]) {
  test(`configura catálogo y categorías con teclado a ${ancho}px`, async ({ page }) => {
    await prepararTienda(page, { sesion: true });
    await page.route('**/api/ventas/admin/blog/', route => route.fulfill({ json: [] }));
    await page.route('**/api/ventas/admin/sobre-mi/proyectos/', route => route.fulfill({ json: [] }));
    await page.setViewportSize({ width: ancho, height: 900 });
    let config = { nombre_tienda: 'Tienda QA', orden_catalogo: 'destacados', orden_categorias: [] };
    const publicados = [
      { ...producto, nombre: 'Producto Beta', categoria: 'Beta' },
      { ...producto, id: '000000000000000000000002', nombre: 'Producto Alfa', categoria: 'Alfa' }
    ];
    const borrador = { ...producto, id: '000000000000000000000003', nombre: 'Borrador', categoria: 'Zeta', publicado: false };
    await page.route('**/api/configuracion/**', async route => {
      if (route.request().method() === 'PATCH') config = { ...config, ...route.request().postDataJSON() };
      await route.fulfill({ json: config });
    });
    await page.route('**/api/catalogo/productos/**', route => {
      const params = new URL(route.request().url()).searchParams;
      if (params.get('todos') === 'true') return route.fulfill({ json: [...publicados, borrador] });
      const categorias = [...config.orden_categorias.filter(c => ['Alfa', 'Beta'].includes(c)), ...['Alfa', 'Beta'].filter(c => !config.orden_categorias.includes(c))];
      return route.fulfill({ json: { count: 2, total_pages: 1, current_page: 1, results: publicados, filtros: { categorias, atributos: {} } } });
    });
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Configuración', exact: true }).click();
    const selector = page.getByLabel('Orden inicial del catálogo');
    await selector.selectOption('precio-desc');
    await expect(page.getByRole('button', { name: 'Subir Zeta', exact: true })).toBeVisible();
    const subir = page.getByRole('button', { name: 'Subir Beta', exact: true });
    await subir.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: 'Bajar Beta', exact: true })).toBeFocused();
    await page.getByRole('button', { name: 'Guardar orden', exact: true }).click();
    await expect(page.getByText('Orden del catálogo y categorías guardado.')).toBeVisible();
    expect(config.orden_catalogo).toBe('precio-desc');
    expect(config.orden_categorias).toEqual(['Beta']);
    expect((await new AxeBuilder({ page }).include('.orden-catalogo-campos').analyze()).violations).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.goto('/catalogo');
    await expect(page.getByLabel('Ordenar por')).toHaveValue('precio-desc');
    await expect(page.getByLabel('Categoría').locator('option')).toHaveText(['Todas', 'Beta', 'Alfa']);
    const consulta = page.waitForRequest(request => request.url().includes('/api/catalogo/productos/') && new URL(request.url()).searchParams.get('orden') === 'nombre');
    await page.getByLabel('Ordenar por').selectOption('nombre');
    await consulta;
    await expect(page.getByLabel('Ordenar por')).toHaveValue('nombre');
    await expect(page.locator('.catalogo__contenido h3')).toHaveText(['Producto Beta', 'Producto Alfa']);
  });
}
