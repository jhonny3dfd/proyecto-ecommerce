import { test, expect } from '@playwright/test';
import { prepararTienda } from './soporte/tienda';

const BLANCO = 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2210%22 height=%2210%22%3E%3Crect width=%2210%22 height=%2210%22 fill=%22white%22/%3E%3C/svg%3E';
const TEXTO = 'Texto de prueba para comprobar el contraste en toda el área de lectura de la portada. '.repeat(3);

// Contraste del párrafo de la portada en su borde derecho, el punto donde el velo es más claro, suponiendo que
// debajo hay un cuadro completamente blanco. Devuelve también la opacidad del velo en el borde derecho de la portada
async function medirContraste(page) {
  return page.locator('.portada-texto').evaluate(parrafo => {
    const portada = parrafo.closest('.portada').getBoundingClientRect();
    const rango = document.createRange();
    rango.selectNodeContents(parrafo);
    const proporcion = (rango.getBoundingClientRect().right - portada.left) / portada.width;
    const estilo = getComputedStyle(document.querySelector('.portada-velo'));
    const gradiente = estilo.backgroundImage;
    const alfaSolido = Number(estilo.backgroundColor.match(/[\d.]+/g).at(-1));
    const alfas = gradiente === 'none' ? [alfaSolido, alfaSolido, alfaSolido] : [...gradiente.matchAll(/(?:rgba|color|oklab)\([^)]+\)/g)].map(coincidencia => Number(coincidencia[0].match(/[\d.]+/g).at(-1)));
    const alfa = proporcion <= 0.55 ? alfas[0] + (alfas[1] - alfas[0]) * proporcion / 0.55 : alfas[1] + (alfas[2] - alfas[1]) * (proporcion - 0.55) / 0.45;
    const fondo = 1 - alfa;
    const canales = getComputedStyle(parrafo).color.match(/[\d.]+/g).map(Number);
    const opacidad = canales[3] ?? 1;
    const texto = canales.slice(0, 3).map(canal => canal / 255 * opacidad + fondo * (1 - opacidad));
    const luminancia = valor => valor <= 0.04045 ? valor / 12.92 : ((valor + 0.055) / 1.055) ** 2.4;
    const luzTexto = texto.reduce((total, canal, indice) => total + luminancia(canal) * [0.2126, 0.7152, 0.0722][indice], 0);
    return { razon: (luzTexto + 0.05) / (luminancia(fondo) + 0.05), gradiente, alfaBorde: alfas[2] };
  });
}

for (const ancho of [1440, 320]) {
test(`el texto de portada conserva contraste sobre una imagen blanca a ${ancho} píxeles`, async ({ page }) => {
  await prepararTienda(page);
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    tema_seleccionado: 1, nombre_tienda: 'Tienda QA', texto_bienvenida: 'Portada QA',
    texto_landing: TEXTO, banner_url: BLANCO,
  } }));
  await page.setViewportSize({ width: ancho, height: 844 });
  await page.goto('/');
  const contraste = await medirContraste(page);
  expect(contraste.razon, contraste.gradiente).toBeGreaterThanOrEqual(4.5);
});
}

// Con el video en pantalla el velo se aclara hacia la derecha (desde 1024 px), pero no en la zona del texto
for (const [ancho, aclarado] of [[1440, true], [1024, true], [1023, false], [320, false]]) {
test(`con el video en pantalla, el texto conserva contraste a ${ancho} píxeles`, async ({ page }) => {
  await prepararTienda(page);
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    tema_seleccionado: 1, nombre_tienda: 'Tienda QA', texto_bienvenida: 'Portada QA', video_banner_activo: true,
    banners: [{ id: 1, imagen: BLANCO, video: '/media/banners/qa.mp4', orden: 0, antetitulo: '',
      titulo: 'Portada con video', texto: TEXTO, destino: 'CATALOGO' }],
  } }));
  // El video queda cargando (sin responder): así no falla y la portada lo sigue mostrando
  await page.route('**/qa.mp4', () => {});
  await page.setViewportSize({ width: ancho, height: 844 });
  await page.goto('/');
  await expect(page.locator('section.portada')).toHaveClass(/portada--con-video/);
  // El velo cambia con una transición de 1 s
  await page.waitForTimeout(1200);
  const contraste = await medirContraste(page);
  expect(contraste.razon, contraste.gradiente).toBeGreaterThanOrEqual(4.5);
  if (aclarado) expect(contraste.alfaBorde).toBeCloseTo(0.3, 2);
  else expect(contraste.alfaBorde).toBeGreaterThanOrEqual(0.6);
  // El video va un 20 % más claro bajo el velo; el cálculo de arriba ya supone el peor caso, un cuadro blanco
  expect(await page.locator('.portada-diapositiva video').evaluate(v => getComputedStyle(v).filter))
    .toBe('brightness(1.2)');
});
}
