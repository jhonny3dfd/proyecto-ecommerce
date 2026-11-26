import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto } from './soporte/tienda';

// Reseñas con estrellas: el comprador deja la suya desde el enlace del correo, el admin la aprueba y la tienda
// la muestra. La API está simulada: no se usa el backend ni la base

const TOKEN = 'token-firmado:abc';
const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const formulario = {
  orden_id: 12, nombre_sugerido: 'Ana P.', productos: [{ producto_id: producto.id, nombre: producto.nombre }],
};
const aprobada = { nombre_publico: 'Ana P.', estrellas: 5, comentario: 'Llegó impecable', fecha: '2026-10-20T12:00:00Z' };
const pendiente = {
  id: 7, orden_id: 12, estado: 'PENDIENTE', estado_display: 'Pendiente', fecha_creacion: '2026-10-25T12:00:00Z',
  estrellas: 5, comentario: 'Llegó impecable', nombre_publico: 'Ana P.',
  productos: [{ producto_mongo_id: producto.id, producto_nombre: producto.nombre, estrellas: 4, comentario: '' }],
};

async function simularResenas(page, { tema = 1, sesion = false } = {}) {
  const tienda = await prepararTienda(page, { tema, sesion });
  const enviadas = [];
  const moderadas = [];
  const pendientes = [pendiente];
  // Registradas después: tienen prioridad sobre las de prepararTienda
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', tema_seleccionado: tema, resenas_activas: true, texto_bienvenida: 'Productos de prueba',
  } }));
  await page.route('**/api/ventas/resenas/**', async route => {
    const peticion = route.request();
    const { pathname, searchParams } = new URL(peticion.url());
    if (pathname.endsWith('/resenas/formulario/')) {
      return searchParams.get('t') === TOKEN ? route.fulfill({ json: formulario })
        : route.fulfill({ status: 404, json: { detail: 'El enlace para dejar la reseña no es válido o ya venció.' } });
    }
    if (pathname.endsWith('/resenas/') && peticion.method() === 'POST') {
      enviadas.push(peticion.postDataJSON());
      return route.fulfill({ status: 201, json: { mensaje: '¡Gracias por tu reseña! La tienda la revisará antes de publicarla.' } });
    }
    if (pathname.endsWith('/resenas/tienda/')) return route.fulfill({ json: { promedio: 4.5, total: 2, resenas: [aprobada] } });
    if (pathname.endsWith(`/resenas/producto/${producto.id}/`)) {
      return route.fulfill({ json: { promedio: 4, total: 1, resenas: [{ ...aprobada, estrellas: 4, comentario: 'Muy bueno' }] } });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.route('**/api/ventas/admin/resenas/**', async route => {
    const peticion = route.request();
    if (peticion.method() === 'PATCH') {
      moderadas.push(peticion.postDataJSON());
      pendientes.pop();
      return route.fulfill({ json: { ...pendiente, ...peticion.postDataJSON() } });
    }
    const estado = new URL(peticion.url()).searchParams.get('estado');
    const resultados = estado === 'PENDIENTE' ? pendientes : [];
    return route.fulfill({ json: { count: resultados.length, results: resultados } });
  });
  return { ...tienda, enviadas, moderadas };
}

test('el comprador deja su reseña solo con el teclado', async ({ page }) => {
  const { enviadas, inesperadas } = await simularResenas(page);
  await page.goto(`/resena?t=${encodeURIComponent(TOKEN)}`);
  await expect(page.getByText('Pedido #12')).toBeVisible();
  // El token del correo sale de la URL al abrirla: la analítica no lo ve
  expect(await page.evaluate(() => location.pathname + location.search)).toBe('/resena');

  // Tienda: se entra al grupo y las flechas eligen
  const tienda = page.getByRole('group', { name: '¿Cómo calificarías a Tienda QA?' });
  await tienda.getByRole('radio', { name: '1 estrella: Muy mala' }).focus();
  await page.keyboard.press('Space');
  for (let i = 0; i < 3; i++) await page.keyboard.press('ArrowRight');
  await expect(tienda.getByRole('radio', { name: '4 estrellas: Buena' })).toBeChecked();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Comentario (opcional)')).toBeFocused();
  await page.keyboard.type('Muy buena atención');

  // Producto: opcional
  const productoGrupo = page.getByRole('group', { name: producto.nombre });
  await productoGrupo.getByRole('radio', { name: '1 estrella: Muy mala' }).focus();
  await page.keyboard.press('Space');
  for (let i = 0; i < 4; i++) await page.keyboard.press('ArrowRight');
  await expect(productoGrupo.getByRole('radio', { name: '5 estrellas: Excelente' })).toBeChecked();

  const acepta = page.getByRole('checkbox', { name: /Acepto que mi reseña/ });
  await acepta.focus();
  await page.keyboard.press('Space');
  await page.getByRole('button', { name: 'Enviar reseña' }).press('Enter');

  const gracias = page.getByRole('status');
  await expect(gracias).toContainText('¡Gracias por tu reseña!');
  await expect(gracias).toBeFocused();
  expect(enviadas).toEqual([{
    token: TOKEN, estrellas: 4, comentario: 'Muy buena atención', nombre_publico: 'Ana P.', acepta_publicacion: true,
    productos: [{ producto_id: producto.id, estrellas: 5, comentario: '' }],
  }]);
  expect(inesperadas).toEqual([]);
});

test('un enlace alterado no muestra el formulario', async ({ page }) => {
  await simularResenas(page);
  await page.goto('/resena?t=otro-token');

  await expect(page.getByText('no es válido o ya venció')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Enviar reseña' })).toHaveCount(0);
});

for (const tema of [1, 2, 3, 4, 5, 6]) {
  test(`el formulario cumple WCAG AA en la paleta ${tema}, en escritorio y celular`, async ({ page }) => {
    await simularResenas(page, { tema });
    for (const ancho of [1280, 375]) {
      await page.setViewportSize({ width: ancho, height: 900 });
      await page.goto(`/resena?t=${encodeURIComponent(TOKEN)}`);
      await page.getByRole('radio', { name: '4 estrellas: Buena' }).first().check({ force: true });
      const axe = await new AxeBuilder({ page }).include('main').withTags(WCAG).analyze();
      expect(axe.violations).toEqual([]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    }
  });
}

test('el admin aprueba la reseña pendiente desde el panel', async ({ page }) => {
  const { moderadas } = await simularResenas(page, { sesion: true });
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Reseñas', exact: true }).click();

  const tarjeta = page.getByRole('article', { name: 'Ana P. · Pedido #12' });
  await expect(tarjeta.getByRole('img', { name: '5 de 5 estrellas' })).toBeVisible();
  await tarjeta.getByRole('button', { name: 'Aprobar la reseña de Ana P.' }).click();

  await expect(page.getByRole('status')).toContainText('Publicaste la reseña de Ana P.');
  await expect(page.getByText('No hay reseñas por revisar.')).toBeVisible();
  expect(moderadas).toEqual([{ estado: 'APROBADA' }]);
});

test('la landing y la ficha muestran las reseñas aprobadas', async ({ page }) => {
  await simularResenas(page);
  await page.goto('/');

  const seccion = page.getByRole('region', { name: 'Lo que dicen nuestros clientes' });
  await expect(seccion).toContainText('4,5 de 5 · 2 reseñas');
  await expect(seccion.getByText('Llegó impecable')).toBeVisible();
  const axe = await new AxeBuilder({ page }).include('#resenas').withTags(WCAG).analyze();
  expect(axe.violations).toEqual([]);

  await page.goto(`/catalogo/producto/${producto.id}`);
  await page.getByRole('link', { name: '4,0 de 5 · 1 reseña' }).click();
  await expect(page).toHaveURL(/#resenas$/);
  await expect(page.getByRole('region', { name: 'Reseñas' }).getByText('Muy bueno')).toBeInViewport();
});
