import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { comprobarVista, prepararTienda } from './soporte/tienda';

// Destacados de la landing (RF-01.1, pedido de un cliente): la sección pública y el editor del modo edición, en
// los 4 temas, en el computador y a 375 px. La API está simulada (prepararTienda): no se usa backend.
const foto = (color) => `data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2230%22 height=%2220%22%3E%3Crect width=%2230%22 height=%2220%22 fill=%22%23${color}%22/%3E%3C/svg%3E`;

const destacados = [
  { tipo: 'PUBLICACION', id: '7', nombre: 'Mural en Cerro Alegre', imagen: foto('9c4f2e'), enlace: '/blog/mural-cerro-alegre' },
  { tipo: 'PRODUCTO', id: 'p1', nombre: 'Retrato al óleo', imagen: foto('2a2622'), enlace: '/catalogo/producto/p1',
    variantes: [{ sku: 'p1-1', precio: 90000, precio_oferta: 75000, stock: 1 }] },
  { tipo: 'PRODUCTO', id: 'p3', nombre: 'Print A3', imagen: null, enlace: '/catalogo/producto/p3',
    variantes: [{ sku: 'p3-1', precio: 15000, stock: 0 }] },
];

async function prepararDestacados(page, { tema = 1, sesion = false } = {}) {
  const tienda = await prepararTienda(page, { tema, sesion });
  const configuracion = {
    nombre_tienda: 'Tienda QA', tema_seleccionado: tema, tipografia_seleccionada: 1,
    texto_bienvenida: 'Productos de prueba', texto_boton_ingreso: 'Ver catálogo', blog_activo: true,
    blog_nombre: 'Portafolio', vitrina_modo: 'DESTACADOS', destacados_titulo: 'Obras elegidas',
    destacados: destacados.map(({ tipo, id }) => ({ tipo, id })),
  };
  // Las rutas registradas después mandan sobre las de prepararTienda
  await page.route('**/api/configuracion/', (route) => route.fulfill({ json: configuracion }));
  await page.route('**/api/catalogo/vitrina/', (route) => route.fulfill({ json: {
    mas_vendidos: [], recientes: [], destacados, destacados_titulo: 'Obras elegidas' } }));
  // Lo que el editor ofrece para agregar
  await page.route((url) => url.pathname === '/api/catalogo/productos/' && url.searchParams.get('todos') === 'true',
    (route) => route.fulfill({ json: [
      { id: 'p1', nombre: 'Retrato al óleo', publicado: true, imagenes: [foto('2a2622')], variantes: destacados[1].variantes },
      { id: 'p3', nombre: 'Print A3', publicado: true, imagenes: [], variantes: destacados[2].variantes },
      { id: 'p4', nombre: 'Acuarela', publicado: true, imagenes: [], variantes: [{ sku: 'p4-1', precio: 20000, stock: 2 }] },
    ] }));
  await page.route('**/api/ventas/admin/blog/', (route) => route.fulfill({ json: [
    { id: 7, titulo: 'Mural en Cerro Alegre', slug: 'mural-cerro-alegre', estado: 'PUBLICADA', portada: foto('9c4f2e') },
  ] }));
  return tienda;
}

// Cuántas tarjetas hay en la primera fila, y cuánto espacio queda a cada lado de esa fila dentro de la grilla
const primeraFila = (grilla) => grilla.evaluate((elemento) => {
  const cajas = [...elemento.children].map((hijo) => hijo.getBoundingClientRect());
  const fila = cajas.filter((caja) => Math.abs(caja.top - cajas[0].top) < 1);
  const contenedor = elemento.getBoundingClientRect();
  return { cantidad: fila.length, izquierda: fila[0].left - contenedor.left,
    derecha: contenedor.right - fila[fila.length - 1].right };
});

async function sinViolaciones(page, selectores) {
  let analisis = new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']);
  for (const selector of selectores) analisis = analisis.include(selector);
  const { violations } = await analisis.analyze();
  expect(violations.map(({ id, nodes }) => `${id}: ${nodes.map((nodo) => nodo.target).join(', ')}`)).toEqual([]);
}

for (const tema of [1, 2, 3, 4]) {
  // En el computador, los 3 en una fila y centrados; en el celular, dos por fila como el catálogo
  for (const [ancho, porFila] of [[1280, 3], [375, 2]]) {
    test(`destacados en la landing con el tema ${tema} a ${ancho} px: ${porFila} por fila y sin violaciones`, async ({ page }) => {
      const { inesperadas } = await prepararDestacados(page, { tema });
      await page.setViewportSize({ width: ancho, height: 900 });
      await page.goto('/');

      const seccion = page.getByRole('region', { name: 'Obras elegidas' });
      await expect(seccion.getByRole('listitem')).toHaveCount(3);
      await expect(page.getByRole('region', { name: 'Más vendidos' })).toHaveCount(0);
      const fila = await primeraFila(seccion.locator('.grilla-destacados'));
      expect(fila.cantidad).toBe(porFila);
      expect(Math.abs(fila.izquierda - fila.derecha)).toBeLessThan(2);
      // Foto vertical (4:5), como en el catálogo (pedido de Alan)
      const marco = await seccion.locator('.tarjeta-destacado-imagen').first().boundingBox();
      expect(marco.height / marco.width).toBeCloseTo(1.25, 1);
      await expect(seccion.getByRole('link', { name: /Mural en Cerro Alegre/ })).toHaveAttribute('href', '/blog/mural-cerro-alegre');
      await comprobarVista(page);
      await sinViolaciones(page, ['#destacados']);
      expect(inesperadas).toEqual([]);
    });
  }
}

for (const tema of [1, 2, 3, 4]) {
  for (const ancho of [1280, 375]) {
    test(`el editor de la vitrina con el tema ${tema} a ${ancho} px funciona con teclado y sin violaciones`, async ({ page }) => {
      const { inesperadas } = await prepararDestacados(page, { tema, sesion: true });
      await page.setViewportSize({ width: ancho, height: 900 });
      await page.goto('/');
      await page.getByRole('button', { name: 'Editar página' }).click();

      await expect(page.getByRole('radio', { name: /Destacados/ })).toBeChecked();
      await expect(page.getByText('Tus destacados (3 de 8)')).toBeVisible();

      // Solo con teclado: "Bajar" mueve y el foco se queda en el mismo botón
      const bajar = page.getByRole('button', { name: 'Bajar Mural en Cerro Alegre' });
      await bajar.focus();
      await page.keyboard.press('Enter');
      await expect(page.getByRole('button', { name: 'Bajar Mural en Cerro Alegre' })).toBeFocused();
      await expect(page.getByText('Mural en Cerro Alegre: posición 2 de 3.')).toBeAttached();

      // Agregar el cuarto desde la lista desplegable
      await page.getByLabel('Agregar un producto o una publicación').selectOption({ label: 'Acuarela' });
      await page.getByRole('button', { name: 'Agregar', exact: true }).click();
      await expect(page.getByText('Tus destacados (4 de 8)')).toBeVisible();
      // Quedan cupos: se puede seguir agregando (el límite lleno lo prueba LandingPage.test.jsx)
      await expect(page.getByLabel('Agregar un producto o una publicación')).toBeEnabled();

      await comprobarVista(page);
      await sinViolaciones(page, ['.editor-vitrina', '#destacados']);
      expect(inesperadas).toEqual([]);
    });
  }
}
