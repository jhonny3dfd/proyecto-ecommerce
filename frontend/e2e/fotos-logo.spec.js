import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { comprobarVista, prepararTienda } from './soporte/tienda';

// Fotos y logo (pedido de un cliente): fotos sin recorte, ficha con la foto horizontal y logo más grande en el
// computador, la tablet y el celular. Apagadas, la tienda se ve como antes. La API está simulada (prepararTienda): no se usa backend.
const svg = (ancho, alto, color) => `data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="${ancho}" height="${alto}"><rect width="${ancho}" height="${alto}" fill="${color}"/></svg>`)}`;

const HORIZONTAL = svg(1500, 1000, '#9c4f2e');
const VERTICAL = svg(800, 1200, '#2a2622');
const LOGO = svg(300, 100, '#2a2622');

const obra = (id, nombre, imagen) => ({
  id, nombre, categoria: 'Pinturas', descripcion: 'Óleo sobre tela.', imagenes: [imagen], activo: true, publicado: true,
  variantes: [{ sku: `${id}-1`, precio: 90000, stock: 1, atributos_variables: {} }],
});
const MURAL = obra('000000000000000000000011', 'Mural en Cerro Alegre', HORIZONTAL);
const RETRATO = obra('000000000000000000000012', 'Retrato al óleo', VERTICAL);

async function prepararObras(page, opciones = {}, { tema = 1 } = {}) {
  const tienda = await prepararTienda(page, { tema });
  const configuracion = {
    nombre_tienda: 'Taller QA', tema_seleccionado: tema, tipografia_seleccionada: 1, logo: LOGO,
    texto_bienvenida: 'Obras de prueba', texto_boton_ingreso: 'Ver catálogo',
    fotos_completas: false, ficha_horizontal: false, logo_grande: false, ...opciones,
  };
  // Las rutas registradas después mandan sobre las de prepararTienda
  await page.route('**/api/configuracion/', (route) => route.fulfill({ json: configuracion }));
  await page.route('**/api/catalogo/vitrina/', (route) => route.fulfill({ json: { mas_vendidos: [MURAL, RETRATO], recientes: [] } }));
  await page.route((url) => url.pathname === '/api/catalogo/productos/', (route) => route.fulfill({ json: {
    count: 2, total_pages: 1, current_page: 1, results: [MURAL, RETRATO], filtros: { categorias: ['Pinturas'], atributos: {} } } }));
  await page.route(`**/api/catalogo/productos/${MURAL.id}/`, (route) => route.fulfill({ json: MURAL }));
  return tienda;
}

const estilo = (locator, propiedad) => locator.evaluate((elemento, nombre) => getComputedStyle(elemento)[nombre], propiedad);
const proporcion = (locator) => locator.evaluate((elemento) => {
  const { width, height } = elemento.getBoundingClientRect();
  return Math.round((width / height) * 100) / 100;
});

async function sinViolaciones(page) {
  const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(violations.map(({ id, nodes }) => `${id}: ${nodes.map((nodo) => nodo.target).join(', ')}`)).toEqual([]);
}

test('por defecto la tienda se ve como antes: fotos recortadas, ficha vertical y logo normal', async ({ page }) => {
  const { inesperadas } = await prepararObras(page);
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/catalogo');

  await expect(page.locator('html')).not.toHaveAttribute('data-fotos');
  expect(await estilo(page.locator('.tarjeta-producto-imagen img').first(), 'objectFit')).toBe('cover');
  expect(await estilo(page.locator('.header-logo-negocio'), 'height')).toBe('52px');

  await page.goto(`/catalogo/producto/${MURAL.id}`);
  const principal = page.locator('.detalle-imagen-principal');
  await expect(principal.locator('img')).toBeVisible();
  expect(await proporcion(principal)).toBe(0.8);
  expect(await estilo(principal.locator('img'), 'objectFit')).toBe('cover');
  expect(inesperadas).toEqual([]);
});

for (const tema of [1, 2, 3, 4]) {
  for (const ancho of [1280, 375]) {
    test(`con las tres opciones, tema ${tema} a ${ancho} px: obras enteras, ficha horizontal y sin violaciones`, async ({ page }) => {
      const { inesperadas } = await prepararObras(page, { fotos_completas: true, ficha_horizontal: true, logo_grande: true }, { tema });
      await page.setViewportSize({ width: ancho, height: 900 });

      // Catálogo: el mismo marco 4:5, con la obra entera dentro (horizontal y vertical)
      await page.goto('/catalogo');
      await expect(page.locator('html')).toHaveAttribute('data-fotos', 'completas');
      const tarjetas = page.locator('.tarjeta-producto-imagen');
      await expect(tarjetas).toHaveCount(2);
      for (const indice of [0, 1]) {
        expect(await estilo(tarjetas.nth(indice).locator('img'), 'objectFit')).toBe('contain');
        expect(await proporcion(tarjetas.nth(indice))).toBe(0.8);
      }
      // RN-01 y logo grande: 88 px en el computador y 64 en el celular (normal: 52 y 44)
      expect(await estilo(page.locator('.header-logo-negocio'), 'height')).toBe(ancho >= 1024 ? '88px' : '64px');
      await comprobarVista(page);
      await sinViolaciones(page);

      // Ficha: marco apaisado 3:2, obra entera; en el computador la foto ocupa cerca de dos tercios
      await page.goto(`/catalogo/producto/${MURAL.id}`);
      const principal = page.locator('.detalle-imagen-principal');
      await expect(principal.locator('img')).toBeVisible();
      expect(await proporcion(principal)).toBe(1.5);
      expect(await estilo(principal.locator('img'), 'objectFit')).toBe('contain');
      const galeria = await page.locator('.detalle-galeria').boundingBox();
      const contenido = await page.locator('.detalle-contenido').boundingBox();
      if (ancho >= 768) expect(galeria.width / contenido.width).toBeGreaterThan(0.58);
      else expect(galeria.width).toBe(contenido.width);
      await comprobarVista(page);
      await sinViolaciones(page);
      expect(inesperadas).toEqual([]);
    });
  }
}

test('cada opción funciona sola: solo el logo grande no cambia las fotos', async ({ page }) => {
  await prepararObras(page, { logo_grande: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/catalogo');

  expect(await estilo(page.locator('.header-logo-negocio'), 'height')).toBe('88px');
  expect(await estilo(page.locator('.header-logo-universidad'), 'height')).toBe('88px');
  expect(await estilo(page.locator('.tarjeta-producto-imagen img').first(), 'objectFit')).toBe('cover');

  // También más grande en la tablet y el celular (pedido de Alan, 2026-11-10), con los dos logos dentro de la pantalla
  for (const [ancho, alto] of [[820, '72px'], [390, '64px'], [360, '64px']]) {
    await page.setViewportSize({ width: ancho, height: 900 });
    expect(await estilo(page.locator('.header-logo-negocio'), 'height')).toBe(alto);
    expect(await estilo(page.locator('.header-logo-universidad'), 'height')).toBe(alto);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});
