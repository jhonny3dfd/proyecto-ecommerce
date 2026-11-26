import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda } from './soporte/tienda';

// SCRUM-194: cada foto del carrusel con sus textos y un botón hacia una página del header
const foto = (color) => `data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2210%22 height=%2210%22%3E%3Crect width=%2210%22 height=%2210%22 fill=%22%23${color}%22/%3E%3C/svg%3E`;
const FOTOS = [
  { id: 1, imagen: foto('2a2622'), orden: 0, antetitulo: 'Hecho a mano', titulo: 'Murales', texto: 'Para tu casa',
    destino: 'CATALOGO' },
  { id: 2, imagen: foto('1e293b'), orden: 1, antetitulo: '', titulo: 'Encargos', texto: '', destino: 'COTIZAR' },
];

async function prepararCarrusel(page, banners = FOTOS) {
  await prepararTienda(page, { sesion: true });
  const guardados = [];
  const config = {
    nombre_tienda: 'Tienda QA', texto_bienvenida: 'Murales', subtitulo_bienvenida: 'Hecho a mano',
    texto_landing: 'Para tu casa', cotizaciones_activas: true, banners,
  };
  await page.route('**/api/configuracion/**', async route => {
    if (route.request().method() === 'PATCH') guardados.push(route.request().postDataJSON());
    await route.fulfill({ json: config });
  });
  return guardados;
}

for (const ancho of [390, 1280]) {
  test(`la portada muestra los textos y el botón de cada foto, y se detiene al usarlos (${ancho}px)`, async ({ page }) => {
    await page.clock.install();
    await prepararCarrusel(page);
    await page.setViewportSize({ width: ancho, height: 900 });
    await page.goto('/');
    const titulo = page.getByRole('heading', { level: 1 });
    await expect(titulo).toHaveText('Murales');
    await expect(page.getByRole('link', { name: 'Ver catálogo', exact: true })).toHaveAttribute('href', '/catalogo');

    // Las flechas van junto a la pausa y no tapan el botón de la foto
    const controles = page.getByRole('group', { name: 'Controles del carrusel', exact: true });
    const [cajaControles, cajaBoton] = await Promise.all([controles.boundingBox(), page.locator('.portada-boton').boundingBox()]);
    const seCruzan = cajaControles.x < cajaBoton.x + cajaBoton.width && cajaBoton.x < cajaControles.x + cajaControles.width
      && cajaControles.y < cajaBoton.y + cajaBoton.height && cajaBoton.y < cajaControles.y + cajaControles.height;
    expect(seCruzan).toBe(false);
    await controles.getByRole('button', { name: 'Foto siguiente', exact: true }).click();
    await expect(titulo).toHaveText('Encargos');
    await controles.getByRole('button', { name: 'Foto anterior', exact: true }).click();
    await expect(titulo).toHaveText('Murales');
    await expect(controles.getByRole('status')).toHaveText('Foto 1 de 2.');
    // Con el foco en la flecha el carrusel se detiene: se saca el foco para que siga solo
    await page.evaluate(() => document.activeElement.blur());

    await page.clock.runFor(5000);
    await expect(titulo).toHaveText('Encargos');
    const cotizar = page.locator('.portada-boton');
    await expect(cotizar).toHaveAttribute('href', '/cotizar');

    // Con el foco en el botón, la foto no cambia
    await cotizar.focus();
    await page.clock.runFor(15000);
    await expect(titulo).toHaveText('Encargos');
    await expect(cotizar).toBeFocused();
    expect((await new AxeBuilder({ page }).include('.portada').analyze()).violations).toEqual([]);
  });

  test(`edita los textos y el botón de cada foto desde la landing (${ancho}px)`, async ({ page }) => {
    const guardados = await prepararCarrusel(page);
    await page.setViewportSize({ width: ancho, height: 900 });
    await page.goto('/');
    await page.getByRole('button', { name: 'Editar página', exact: true }).click();

    const titulo = page.getByLabel('Título', { exact: true });
    await expect(titulo).toHaveValue('Murales');
    await page.getByRole('button', { name: 'Foto siguiente →', exact: true }).click();
    await expect(titulo).toHaveValue('Encargos');
    await expect(page.getByRole('button', { name: '← Foto anterior', exact: true })).toBeFocused();
    await expect(page.locator('.portada-editor-posicion')).toHaveText('Foto 2 de 2');

    await titulo.fill('Cyber');
    await page.getByLabel('El botón lleva a', { exact: true }).selectOption('INICIO');
    await expect(page.locator('.portada-boton')).toHaveText('Ver inicio');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).include('.portada').analyze()).violations).toEqual([]);

    await page.getByRole('button', { name: 'Guardar cambios', exact: true }).click();
    await expect(page.getByText(/Cambios guardados/)).toBeVisible();
    expect(JSON.parse(guardados.at(-1).banner_orden)).toEqual([
      { ref: 'id:1', antetitulo: 'Hecho a mano', titulo: 'Murales', texto: 'Para tu casa', destino: 'CATALOGO' },
      { ref: 'id:2', antetitulo: '', titulo: 'Cyber', texto: '', destino: 'INICIO' },
    ]);
  });
}

test('con las 10 fotos, el panel del carrusel cabe en un celular y las miniaturas se recorren por dentro (390px)', async ({ page }) => {
  const diez = Array.from({ length: 10 }, (_, i) => ({
    id: i + 1, imagen: foto('2a2622'), orden: i, antetitulo: '', titulo: `Foto ${i + 1}`, texto: '', destino: 'CATALOGO',
  }));
  await prepararCarrusel(page, diez);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.getByRole('button', { name: 'Editar página', exact: true }).click();

  const panel = page.locator('.portada-editor-fotos');
  const caja = await panel.boundingBox();
  expect(caja.x).toBeGreaterThanOrEqual(0);
  expect(caja.x + caja.width).toBeLessThanOrEqual(390);
  // Ni el panel ni los textos ocultos de cada foto estiran la página hacia el costado
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  // La última foto se alcanza con el teclado: la lista se desplaza hasta ella
  const quitarUltima = page.getByRole('button', { name: 'Quitar foto 10 del banner', exact: true });
  await quitarUltima.focus();
  await expect(quitarUltima).toBeInViewport();
  expect((await new AxeBuilder({ page }).include('.portada-editor-fotos').analyze()).violations).toEqual([]);
});
