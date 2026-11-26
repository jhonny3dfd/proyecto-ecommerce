import { Buffer } from 'node:buffer';
import { test, expect } from '@playwright/test';
import { prepararTienda } from './soporte/tienda';

const imagen = `data:image/svg+xml,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="60"><rect width="100" height="60" fill="blue"/></svg>'
)}`;

const configuracion = {
  nombre_tienda: 'Tienda QA',
  texto_bienvenida: 'Bienvenidos',
  subtitulo_bienvenida: 'Nuestra tienda',
  texto_landing: 'Productos destacados',
  video_banner_activo: false,
  banners: [
    {
      id: 1,
      imagen,
      orden: 0,
      antetitulo: '',
      titulo: 'Portada principal',
      texto: '',
      destino: 'CATALOGO',
    },
  ],
};

test('permite activar, agregar y guardar un video en el carrusel', async ({ page }) => {
  // Preparar la tienda con una sesión de administrador simulada
  await prepararTienda(page, { sesion: true });

  // Simular la API para no modificar la base de datos real
  await page.route('**/api/configuracion/**', async (route) => {
    await route.fulfill({ json: configuracion });
  });

  await page.goto('/');

  await page.getByRole('button', {
    name: 'Editar página',
    exact: true,
  }).click();

  const checkbox = page.getByRole('checkbox', {
    name: 'Activar video en el banner',
  });

  await expect(checkbox).not.toBeChecked();

  await expect(
    page.getByLabel('Video MP4 del banner')
  ).toHaveCount(0);

  await expect(
    page.getByLabel('Imagen de portada del video')
  ).toHaveCount(0);

  await checkbox.check();

  await expect(checkbox).toBeChecked();

  await expect(
    page.getByLabel('Video MP4 del banner')
  ).toBeAttached();

  await expect(
    page.getByLabel('Imagen de portada del video')
  ).toBeAttached();

  // Seleccionar un archivo MP4 simulado
  await page.getByLabel('Video MP4 del banner').setInputFiles({
    name: 'banner.mp4',
    mimeType: 'video/mp4',
    buffer: Buffer.from('video de prueba'),
  });

  // Seleccionar una imagen PNG de portada
  await page.getByLabel('Imagen de portada del video').setInputFiles({
    name: 'portada.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLttAAAAABJRU5ErkJggg==',
      'base64'
    ),
  });

  // Agregar el video al carrusel
  const agregar = page.getByRole('button', {
    name: 'Agregar video al carrusel',
  });

  await expect(agregar).toBeEnabled();
  await agregar.click();

  await expect(
    page.locator('.portada-editor-posicion')
  ).toContainText('de 2');

  await expect(
    page.getByLabel('Video MP4 del banner')
  ).toHaveCount(0);

  await expect(
    page.getByRole('button', {
      name: 'Agregar video al carrusel',
    })
  ).toHaveCount(0);

  const solicitudGuardado = page.waitForRequest((request) =>
    request.url().includes('/api/configuracion/') &&
    request.method() === 'PATCH'
  );

  await page.getByRole('button', {
    name: 'Guardar cambios',
    exact: true,
  }).click();

  const solicitud = await solicitudGuardado;

  const datos = solicitud.postDataBuffer();

  expect(datos).not.toBeNull();

  const contenido = datos.toString('utf8');

  expect(contenido).toContain('banner_videos');
  expect(contenido).toContain('banner_fotos');
  expect(contenido).toContain('banner_orden');
  expect(contenido).toContain('video_banner_activo');
  expect(contenido).toContain('banner.mp4');
  expect(contenido).toContain('portada.png');

  await expect(
    page.getByText(/Cambios guardados/)
  ).toBeVisible();
});

test('muestra el video publicado y permite pausar el carrusel', async ({ page }) => {
  await prepararTienda(page);

  await page.route('**/api/configuracion/**', async (route) => {
    await route.fulfill({
      json: {
        ...configuracion,
        video_banner_activo: true,
        banners: [
          {
            ...configuracion.banners[0],
            video: '/media/banner.mp4',
            imagen: '/media/portada.png',
          },
        ],
      },
    });
  });

  await page.goto('/');

  const video = page.locator('.portada-carrusel video');

  await expect(video).toHaveCount(1);
  await expect(video).toHaveAttribute('src', '/media/banner.mp4');
  await expect(video).toHaveAttribute('poster', '/media/portada.png');
  await expect(video).toHaveJSProperty('muted', true);
  await expect(video).toHaveAttribute('loop', '');
  await expect(video).toHaveAttribute('playsinline', '');

  await page.getByRole('button', {
    name: 'Pausar carrusel',
  }).click();

  await expect(
    page.getByRole('button', { name: 'Reanudar carrusel' })
  ).toBeVisible();

  await expect.poll(() => video.evaluate((elemento) => elemento.paused))
    .toBe(true);
});
