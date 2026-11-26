import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda } from './soporte/tienda';

for (const ancho of [320, 390, 1280]) {
  test(`edita el menú desde la landing a ${ancho}px`, async ({ page }, testInfo) => {
    await prepararTienda(page, { sesion: true });
    await page.setViewportSize({ width: ancho, height: 900 });
    let guardados = 0;
    let config = {
      nombre_tienda: 'Tienda QA', texto_bienvenida: 'Productos de prueba',
      texto_boton_ingreso: 'Texto antiguo', nosotros_texto: 'Nuestra tienda.',
      blog_activo: true, blog_nombre: 'Portafolio', sobre_mi_activo: true,
      sobre_mi_nombre: 'Historia', cotizaciones_activas: true,
      menu_principal: { nombres: { nosotros: 'Blog antiguo', sobre_mi: 'Historia antigua' }, ocultos: ['nosotros', 'sobre_mi', 'cotizar'] },
    };
    await page.route('**/api/configuracion/**', async route => {
      if (route.request().method() === 'PATCH') {
        guardados++;
        config = { ...config, ...route.request().postDataJSON() };
      }
      await route.fulfill({ json: config });
    });
    await page.route('**/api/ventas/admin/blog/', route => route.fulfill({ json: [] }));
    await page.route('**/api/ventas/admin/sobre-mi/proyectos/', route => route.fulfill({ json: [] }));
    await page.goto('/');
    await expect(page.getByRole('link', { name: /Ver catálogo/ })).toHaveAttribute('href', '/catalogo');
    await expect(page.locator('header .campo-editable-ayuda')).toHaveCount(0);
    await page.getByRole('button', { name: 'Editar página', exact: true }).click();
    const header = page.locator('header');
    const footer = page.getByRole('navigation', { name: 'Tienda', exact: true });
    const nombre = page.getByLabel('Nombre de Catálogo', { exact: true });
    await expect(header.getByRole('textbox')).toHaveCount(1);
    await expect(nombre).toHaveAttribute('maxlength', '20');
    const contador = header.locator('.campo-editable-ayuda');
    await expect(contador).toHaveCount(1);
    await expect(contador).toHaveText('8/20');
    expect(await contador.getAttribute('id')).toBe(await nombre.getAttribute('aria-describedby'));
    await nombre.fill('');
    await nombre.pressSequentially('abcdefghijklmnopqrstuv');
    await expect(nombre).toHaveValue('abcdefghijklmnopqrst');
    await expect(contador).toHaveText('20/20');
    await expect(page.getByLabel('Texto del botón', { exact: true })).toHaveCount(0);
    await expect(header.getByRole('checkbox')).toHaveCount(0);
    await expect(footer.getByRole('link', { name: 'Historia', exact: true })).toHaveAttribute('href', '/sobre-mi');
    await expect(footer.getByRole('link', { name: 'Portafolio', exact: true })).toHaveAttribute('href', '/blog');
    await expect(footer.getByRole('link', { name: 'Cotizar', exact: true })).toHaveAttribute('href', '/cotizar');
    await nombre.click();
    await nombre.fill('Productos');
    await expect(contador).toHaveText('9/20');
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('.portada-boton')).toHaveText('Ver productos');
    await expect(footer.getByRole('link', { name: 'Productos', exact: true })).toBeVisible();
    expect(guardados).toBe(0);
    await page.getByRole('button', { name: 'Descartar', exact: true }).click();
    await expect(nombre).toHaveValue('Catálogo');
    await expect(page.locator('.portada-boton')).toHaveText('Ver catálogo');
    expect(guardados).toBe(0);
    await nombre.fill('Productos');
    await page.getByRole('button', { name: 'Mover Productos a la izquierda', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: 'Mover Productos a la derecha', exact: true })).toBeFocused();
    await expect(page.getByRole('button', { name: 'Mover Productos a la izquierda', exact: true })).toBeDisabled();
    const desbordes = await page.evaluate(() => [...document.querySelectorAll('body *')].filter(elemento => {
      const caja = elemento.getBoundingClientRect();
      return caja.width > 0 && caja.right > innerWidth + 1;
    }).slice(0, 12).map(elemento => ({ clase: elemento.className, ancho: elemento.getBoundingClientRect().width })));
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), JSON.stringify(desbordes)).toBe(true);
    expect((await new AxeBuilder({ page }).include('header').analyze()).violations).toEqual([]);
    await page.screenshot({ path: testInfo.outputPath('menu-editando.png') });
    expect(guardados).toBe(0);
    await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
    await expect(page.getByText(/Cambios guardados/)).toBeVisible();
    expect(guardados).toBe(1);
    expect(config.menu_principal.nombres.catalogo).toBe('Productos');
    expect(config.menu_principal.nombres.sobre_mi).toBe('Historia antigua');
    expect(config.menu_principal.orden[0]).toBe('catalogo');
    expect(config.menu_principal.ocultos).toEqual(['nosotros', 'sobre_mi', 'cotizar']);
    expect(config.sobre_mi_activo).toBe(true);
    await page.reload();
    await expect(header.locator('.campo-editable-ayuda')).toHaveCount(0);
    await expect(header.locator('.header-links a').first()).toHaveText('Productos');
    await expect(header.getByRole('link', { name: 'Historia', exact: true })).toHaveAttribute('href', '/sobre-mi');
    await expect(header.getByRole('link', { name: 'Portafolio', exact: true })).toHaveAttribute('href', '/blog');
    await expect(footer.getByRole('link', { name: 'Productos', exact: true })).toHaveAttribute('href', '/catalogo');
    await page.getByRole('link', { name: /Ver productos/ }).click();
    await expect(page).toHaveURL(/\/catalogo$/);
    config = { ...config, blog_activo: false, sobre_mi_activo: false, cotizaciones_activas: false, nosotros_texto: '' };
    await page.goto('/');
    await expect(header.getByRole('link', { name: 'Historia', exact: true })).toHaveCount(0);
    await expect(header.getByRole('link', { name: 'Portafolio', exact: true })).toHaveCount(0);
    await expect(footer.getByRole('link', { name: 'Cotizar', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: 'Editar página', exact: true }).click();
    await expect(header.locator('.menu-edicion-item')).toHaveCount(2);
    await expect(header.getByRole('checkbox')).toHaveCount(0);
    await page.getByRole('button', { name: 'Salir', exact: true }).click();
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Configuración', exact: true }).click();
    const indice = page.getByRole('navigation', { name: 'Secciones de configuración' });
    await expect(indice.getByRole('button', { name: 'Menú principal', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Guardar menú', exact: true })).toHaveCount(0);
    await expect(indice.getByRole('button', { name: 'Orden del catálogo y categorías', exact: true })).toBeVisible();
  });
}

test('conserva un nombre antiguo largo al reordenar y permite reemplazarlo', async ({ page }) => {
  await prepararTienda(page, { sesion: true });
  const anterior = 'Nuestra colección especial';
  let config = { nombre_tienda: 'Tienda QA', texto_bienvenida: 'Portada QA', menu_principal: { nombres: { catalogo: anterior } } };
  await page.route('**/api/configuracion/**', async route => {
    if (route.request().method() === 'PATCH') config = { ...config, ...route.request().postDataJSON() };
    await route.fulfill({ json: config });
  });
  await page.goto('/');
  const header = page.locator('header');
  await expect(header.getByRole('link', { name: anterior, exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Editar página', exact: true }).click();
  const campo = page.getByLabel('Nombre de Catálogo', { exact: true });
  await expect(campo).toHaveValue(anterior);
  await expect(campo).toHaveAttribute('maxlength', '20');
  await expect(header.locator('.campo-editable-ayuda')).toHaveText(anterior.length + '/20');
  await page.getByRole('button', { name: 'Mover ' + anterior + ' a la izquierda', exact: true }).click();
  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
  await expect(page.getByText(/Cambios guardados/)).toBeVisible();
  expect(config.menu_principal.nombres.catalogo).toBe(anterior);
  await expect(campo).toHaveValue(anterior);
  await campo.fill('Artículos');
  await expect(header.locator('.campo-editable-ayuda')).toHaveText('9/20');
  await page.getByRole('button', { name: 'Descartar', exact: true }).click();
  await expect(campo).toHaveValue(anterior);
  await campo.fill('Productos');
  await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
  await expect(page.getByText(/Cambios guardados/)).toBeVisible();
  await page.reload();
  await expect(header.getByRole('link', { name: 'Productos', exact: true })).toHaveAttribute('href', '/catalogo');
  await expect(header.locator('.campo-editable-ayuda')).toHaveCount(0);
});
