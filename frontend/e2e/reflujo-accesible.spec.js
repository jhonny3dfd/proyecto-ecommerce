import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto } from './soporte/tienda';
import { medirVista, ampliarTexto, espaciarTexto } from './soporte/mediciones';

const rutas = ['/', '/catalogo', `/catalogo/producto/${producto.id}`, '/variantes', '/login', '/checkout', '/seguimiento', '/mis-direcciones', '/mis-pedidos', '/legal/terminos', '/pago-exitoso', '/pedido-recibido', '/pago-cancelado', '/pago-rechazado'];

for (const ancho of [1440, 390, 768, 320]) {
  test(`las rutas conservan estructura y reflujo a ${ancho} píxeles`, async ({ page }) => {
    const { inesperadas } = await prepararTienda(page);
    await page.route('**/api/ventas/mis-pedidos/', route => route.fulfill({ json: [] }));
    await page.setViewportSize({ width: ancho, height: ancho === 768 ? 1024 : ancho === 1440 ? 900 : 844 });
    for (const ruta of rutas) {
      await page.goto(ruta);
      await medirVista(page);
      if (ruta === '/login') {
        await page.getByRole('button', { name: 'Regístrate aquí' }).click();
        await expect(page.getByRole('heading', { name: 'Crear cuenta', exact: true })).toBeVisible();
        await medirVista(page);
      }
    }
    expect(inesperadas).toEqual([]);
  });
}

// El reflujo depende de la tipografía (el ancho del texto), no de la paleta: los colores no cambian las medidas, y
// el contraste de cada paleta lo revisan paletas.test.js y accesibilidad.spec.js
for (const tipografia of [1, 2, 3, 4, 5]) {
  test(`tipografía ${tipografia}: 320 píxeles`, async ({ page }) => {
    const { inesperadas } = await prepararTienda(page, { tipografia, sesion: true });
    await page.setViewportSize({ width: 320, height: 844 });
    for (const ruta of ['/', '/catalogo', '/login', '/checkout', '/admin']) {
      await page.goto(ruta);
      await medirVista(page);
    }
    await page.getByRole('button', { name: 'Inventario', exact: true }).click();
    await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
    await medirVista(page);
    await expect(page.getByRole('button', { name: 'Crear Producto', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Configuración', exact: true }).click();
    await medirVista(page);
    expect(inesperadas).toEqual([]);
  });
}

for (const ajuste of ['texto al 200 %', 'espaciado personalizado']) {
  for (const tipografia of [1, 2, 3, 4, 5]) {
    test(`${ajuste}, tipografía ${tipografia}, sin cambiar el viewport`, async ({ page }) => {
      const { inesperadas } = await prepararTienda(page, { sesion: true, tipografia });
      await page.setViewportSize({ width: 390, height: 844 });
      for (const ruta of ['/', '/catalogo', '/login', '/checkout', '/legal/terminos', '/admin']) {
        await page.goto(ruta);
        await medirVista(page);
        if (ajuste === 'texto al 200 %') await ampliarTexto(page);
        else await espaciarTexto(page);
        await medirVista(page);
      }
      await page.goto('/admin');
      await page.getByRole('button', { name: 'Inventario', exact: true }).click();
      await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
      if (ajuste === 'texto al 200 %') await ampliarTexto(page);
      else await espaciarTexto(page);
      await medirVista(page);
      expect(inesperadas).toEqual([]);
    });
  }
}

test('el formulario de producto y el editor no tienen errores automáticos en sus estados dinámicos', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.setViewportSize({ width: 320, height: 844 });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
  await page.getByRole('button', { name: /Agregar atributo global/i }).click();
  const contrastes = await page.locator('.formulario-producto input:not([type="checkbox"]):not([type="file"]), .formulario-producto textarea, .formulario-producto select').evaluateAll(campos => {
    const luminancia = color => color.match(/[\d.]+/g).slice(0, 3).map(Number)
      .map(valor => valor / 255).map(valor => valor <= .04045 ? valor / 12.92 : ((valor + .055) / 1.055) ** 2.4)
      .reduce((total, valor, indice) => total + valor * [.2126, .7152, .0722][indice], 0);
    return campos.filter(campo => !campo.disabled && campo.getClientRects().length).map(campo => {
      // En un campo de react-select (ej. Colecciones) el borde lo dibuja su contenedor, no el input donde se escribe
      const estilo = getComputedStyle(campo.closest('[class*="__control"]') ?? campo);
      const borde = luminancia(estilo.borderColor);
      const fondo = luminancia(estilo.backgroundColor);
      return { etiqueta: campo.labels?.[0]?.textContent.trim(), razon: (Math.max(borde, fondo) + .05) / (Math.min(borde, fondo) + .05) };
    });
  });
  expect(contrastes.length).toBeGreaterThan(5);
  expect(contrastes.filter(campo => campo.razon < 3)).toEqual([]);
  const analisis = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(analisis.violations).toEqual([]);
  await medirVista(page);
  expect(inesperadas).toEqual([]);
});
