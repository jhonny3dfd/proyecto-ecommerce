import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, comprobarVista, producto } from './soporte/tienda';

// Video de YouTube opcional en la ficha del producto (pedido de Alan). La API está simulada y YouTube también:
// la prueba no sale a internet y registra si la página intenta conectarse a YouTube antes del clic.
const foto = (color) => `data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2240%22 height=%2250%22%3E%3Crect width=%2240%22 height=%2250%22 fill=%22%23${color}%22/%3E%3C/svg%3E`;
const obra = { ...producto, nombre: 'Mural en movimiento', imagenes: [foto('2a2622'), foto('9c4f2e')],
  youtube_id: 'dQw4w9WgXcQ' };

async function prepararFicha(page) {
  const comprobacion = await prepararTienda(page);
  await page.route(`**/api/catalogo/productos/${obra.id}/`, (route) => route.fulfill({ json: obra }));
  const youtube = [];
  await page.route(/youtube-nocookie\.com|youtube\.com|ytimg\.com/, (route) => {
    youtube.push(route.request().url());
    return route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Reproductor simulado</title>' });
  });
  return { ...comprobacion, youtube };
}

for (const ancho of [390, 1280]) {
  test(`la ficha muestra el video al final de la galería y lo carga solo al reproducirlo (${ancho}px)`, async ({ page }) => {
    await page.setViewportSize({ width: ancho, height: 900 });
    const { inesperadas, youtube } = await prepararFicha(page);
    await page.goto(`/catalogo/producto/${obra.id}`);
    await expect(page.getByRole('heading', { name: 'Mural en movimiento' })).toBeVisible();

    // Fotos y video en círculo: desde la primera foto, "anterior" lleva al video
    await page.getByRole('button', { name: 'Imagen anterior' }).click();
    await expect(page.getByRole('button', { name: 'Ver video' })).toHaveAttribute('aria-pressed', 'true');
    const reproducir = page.getByRole('button', { name: 'Reproducir video: Mural en movimiento' });
    await expect(reproducir).toBeVisible();
    expect(youtube).toEqual([]);

    const { violations } = await new AxeBuilder({ page }).include('.detalle-galeria')
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(violations.map(({ id, nodes }) => `${id}: ${nodes.map((nodo) => nodo.target).join(', ')}`)).toEqual([]);
    await comprobarVista(page);

    // Solo con teclado: el botón de reproducir tiene foco visible y monta el reproductor sin cookies
    await reproducir.focus();
    await page.keyboard.press('Enter');
    const reproductor = page.getByTitle('Reproductor de video: Mural en movimiento');
    await expect(reproductor).toHaveAttribute('src', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1');
    await expect.poll(() => youtube.length).toBeGreaterThan(0);
    expect(youtube.every((url) => url.startsWith('https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'))).toBe(true);

    // El video llena el marco de la foto, sin salirse de él
    const [marco, video] = await Promise.all([page.locator('.detalle-imagen-principal').boundingBox(),
      reproductor.boundingBox()]);
    expect(Math.abs(marco.width - video.width)).toBeLessThan(2);
    expect(Math.abs(marco.height - video.height)).toBeLessThan(2);

    // Al pasar a una foto, el reproductor se quita
    await page.getByRole('button', { name: 'Imagen siguiente' }).click();
    await expect(reproductor).toHaveCount(0);
    await expect(page.getByRole('img', { name: 'Mural en movimiento, imagen 1 de 2' })).toBeVisible();
    expect(inesperadas).toEqual([]);
  });
}
