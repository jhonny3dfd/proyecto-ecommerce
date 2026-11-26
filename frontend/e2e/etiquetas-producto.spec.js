import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, comprobarVista, producto } from './soporte/tienda';
// Todas las paletas de la tienda, de su única fuente: si se agrega una, esta prueba también la revisa
import { PALETTES } from '../src/constants/palettes.js';

const obra = { ...producto, nombre: 'Obra 198', etiqueta: 'Edición limitada', etiqueta_color: 'accent',
  variantes: [{ sku: '198', precio: 10000, precio_oferta: 8000, stock: 2 }] };

// Esta suite es funcional y simulada: toda API se intercepta y nunca escribe en un backend.
async function prepararEtiquetas(page, { productos = [obra], tema = 1, layout = 'GRID_3', sesion = false } = {}) {
  const comprobacion = await prepararTienda(page, { tema, sesion });
  const guardados = [];
  const altas = [];
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', tema_seleccionado: tema, layout_catalogo: layout,
    texto_bienvenida: 'Tienda de prueba', texto_boton_ingreso: 'Ver catálogo',
  } }));
  await page.route('**/api/catalogo/vitrina/', route => route.fulfill({ json: { recientes: productos, mas_vendidos: [] } }));
  await page.route('**/api/catalogo/productos/**', async route => {
    const url = new URL(route.request().url());
    const id = url.pathname.split('/').filter(Boolean)[3];
    if (route.request().method() === 'POST') {
      altas.push(route.request().postDataJSON());
      return route.fulfill({ status: 201, json: { ...obra, ...altas.at(-1) } });
    }
    if (route.request().method() === 'PUT') {
      guardados.push(route.request().postDataJSON());
      return route.fulfill({ json: { ...obra, ...guardados.at(-1) } });
    }
    return route.fulfill({ json: id ? productos.find(p => p.id === id) : url.searchParams.has('todos') ? productos : {
      count: productos.length, total_pages: 1, current_page: 1, results: productos,
      filtros: { categorias: ['Prueba'], atributos: {} },
    } });
  });
  return { ...comprobacion, guardados, altas };
}

for (const ancho of [390, 1280]) {
  test(`prioridades en landing, catálogo, lista y ficha (${ancho}px)`, async ({ page }) => {
    await page.setViewportSize({ width: ancho, height: 900 });
    const prods = [obra,
      { ...obra, id: '000000000000000000000002', nombre: 'Sin stock', variantes: [] },
      { ...obra, id: '000000000000000000000003', nombre: 'Privada', coleccion_privada: true, variantes: [], etiqueta: 'Original' },
    ];
    await prepararEtiquetas(page, { productos: prods });
    await page.goto('/');
    await expect(page.locator('.tarjeta-producto-etiqueta')).toHaveText(['Edición limitada', 'Agotado', 'Original']);
    await comprobarVista(page);
    await page.goto('/catalogo');
    await expect(page.locator('.tarjeta-producto-etiqueta')).toHaveText(['Edición limitada', 'Agotado', 'Original']);
    await comprobarVista(page);
    await page.goto(`/catalogo/producto/${obra.id}`);
    await expect(page.locator('.detalle-info .tarjeta-producto-etiqueta')).toHaveText('Edición limitada');
    await expect(page.getByRole('button', { name: 'Agregar al carrito', exact: true })).toBeEnabled();
    await comprobarVista(page);
    await page.goto('/catalogo/producto/000000000000000000000002');
    await expect(page.locator('.detalle-info .tarjeta-producto-etiqueta')).toHaveText('Agotado');
    await page.goto('/catalogo/producto/000000000000000000000003');
    await expect(page.locator('.detalle-info .tarjeta-producto-etiqueta')).toHaveText('Original');
    await prepararEtiquetas(page, { productos: prods, layout: 'LISTA' });
    await page.goto('/catalogo');
    await expect(page.locator('.fila-producto')).toHaveCount(3);
    await expect(page.locator('.fila-producto .tarjeta-producto-etiqueta')).toHaveText(['Edición limitada', 'Agotado', 'Original']);
    await comprobarVista(page);
  });
}

test('agrega una obra sin atributos al carrito y respeta su stock', async ({ page }) => {
  await prepararEtiquetas(page);
  await page.addInitScript(() => localStorage.removeItem('carrito_local'));
  const validaciones = [];
  await page.route('**/api/ventas/carrito/validar/', async route => {
    validaciones.push(route.request().postDataJSON());
    return route.fulfill({ json: { items: [{ producto_mongo_id: obra.id, variante_sku: '198',
      disponible: 2, precio: 8000, problema: null }] } });
  });
  await page.goto(`/catalogo/producto/${obra.id}`);
  const agregar = page.getByRole('button', { name: 'Agregar al carrito', exact: true });
  await expect(agregar).toBeEnabled();
  await agregar.click();
  await expect(page.getByRole('status').filter({ hasText: 'Agregaste' })).toBeVisible();
  expect(validaciones[0].items).toEqual([{ producto_mongo_id: obra.id, variante_sku: '198', cantidad: 1 }]);
  await expect(page.getByText('Stock disponible: 1 (1 en tu carrito)', { exact: true })).toBeVisible();
  await page.locator('.detalle-info').screenshot({ path: test.info().outputPath('compra-sin-atributos.png') });
  await agregar.click();
  await expect(page.getByRole('button', { name: 'Agotado (en tu carrito)', exact: true })).toBeDisabled();
  expect(validaciones).toHaveLength(2);
  expect(validaciones[1].items[0].cantidad).toBe(2);
  await expect(page.locator('.detalle-info .tarjeta-producto-etiqueta')).toHaveText('Edición limitada');
});

test('los cuatro colores mantienen contraste AA en todos los temas', async ({ page }) => {
  for (const { id: tema } of PALETTES) {
    const productos = ['primary', 'secondary', 'accent', 'text'].map((color, i) => ({
      ...obra, id: String(i + 1).padStart(24, '0'), etiqueta: color, etiqueta_color: color,
    }));
    await prepararEtiquetas(page, { tema, productos });
    await page.goto('/catalogo');
    await expect(page.locator('.tarjeta-producto-etiqueta')).toHaveCount(4);
    const colores = await page.locator('.tarjeta-producto-etiqueta').evaluateAll(nodos => nodos.map(nodo => {
      const estilo = getComputedStyle(nodo);
      return { texto: estilo.color, fondo: estilo.backgroundColor };
    }));
    for (const color of colores) {
      const luminancia = rgb => {
        const canales = rgb.match(/[\d.]+/g).slice(0, 3).map(Number).map(c => c / 255)
          .map(c => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
        return canales[0] * 0.2126 + canales[1] * 0.7152 + canales[2] * 0.0722;
      };
      const a = luminancia(color.texto);
      const b = luminancia(color.fondo);
      expect((Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05), `Tema ${tema}`).toBeGreaterThanOrEqual(4.5);
    }
    expect((await new AxeBuilder({ page }).include('.tarjeta-producto-etiqueta')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()).violations).toEqual([]);
  }
});

test('edita texto y color con teclado y envía los campos correctos', async ({ page }) => {
  const { guardados } = await prepararEtiquetas(page, { sesion: true });
  page.on('dialog', dialog => dialog.dismiss());
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  await page.getByRole('button', { name: 'Editar Obra 198', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Etiqueta', exact: true })).toHaveValue('Edición limitada');
  const radio = page.getByRole('radio', { name: 'Principal', exact: true });
  await radio.check();
  await radio.press('ArrowRight');
  await expect(page.getByRole('radio', { name: 'Secundario', exact: true })).toBeChecked();
  await page.getByRole('textbox', { name: 'Etiqueta', exact: true }).fill('x'.repeat(21));
  await expect(page.getByRole('textbox', { name: 'Etiqueta', exact: true })).toHaveValue('x'.repeat(20));
  await page.getByRole('textbox', { name: 'Etiqueta', exact: true }).fill('Único');
  await expect(page.getByRole('group', { name: 'Vista previa de la etiqueta', exact: true })).toHaveText('Único');
  expect((await new AxeBuilder({ page }).include('.campo-etiqueta-producto').analyze()).violations).toEqual([]);
  await page.locator('.campo-etiqueta-producto').screenshot({ path: test.info().outputPath('etiqueta-panel.png') });
  await page.getByRole('button', { name: 'Guardar cambios del producto', exact: true }).click();
  await expect.poll(() => guardados.length).toBe(1);
  expect(guardados[0]).toMatchObject({ etiqueta: 'Único', etiqueta_color: 'secondary' });
});

test('guardar después del alta actualiza la etiqueta sin duplicar el producto', async ({ page }) => {
  const { guardados, altas } = await prepararEtiquetas(page, { sesion: true });
  page.on('dialog', dialog => dialog.dismiss());
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Inventario', exact: true }).click();
  await page.getByRole('button', { name: '+ Agregar producto', exact: true }).click();
  await page.getByLabel('Nombre del Producto', { exact: true }).fill('Alta de prueba');
  await page.getByLabel('Categoría', { exact: true }).selectOption({ label: 'Prueba' });
  await page.getByLabel('SKU', { exact: true }).fill('ALTA-198');
  await page.getByLabel('Precio', { exact: true }).fill('10000');
  await page.getByLabel('Stock', { exact: true }).fill('2');
  await page.getByLabel('Etiqueta', { exact: true }).fill('Nuevo');
  await page.getByRole('button', { name: 'Crear Producto', exact: true }).click();
  await expect.poll(() => altas.length).toBe(1);
  await page.getByLabel('Etiqueta', { exact: true }).fill('Edición limitada');
  await page.getByRole('radio', { name: 'Oscuro', exact: true }).check();
  await page.getByRole('button', { name: 'Guardar cambios del producto', exact: true }).click();
  await expect.poll(() => guardados.length).toBe(1);
  expect(altas).toHaveLength(1);
  expect(guardados[0]).toMatchObject({ etiqueta: 'Edición limitada', etiqueta_color: 'text' });
});
