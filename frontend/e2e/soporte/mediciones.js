import { expect } from '@playwright/test';

export async function medirVista(page) {
  await page.locator('main').waitFor();
  await expect(page.getByText('Verificando sesión...', { exact: true })).toHaveCount(0);
  await page.evaluate(() => document.fonts.ready);
  const medicion = await page.evaluate(() => ({
    ancho: innerWidth, documento: document.documentElement.scrollWidth,
    principales: [...document.querySelectorAll('main')].filter(elemento => elemento.getClientRects().length).length,
    desbordados: [...document.querySelectorAll('body *')].filter(elemento => elemento.getBoundingClientRect().right > innerWidth + 1 && getComputedStyle(elemento).position !== 'absolute')
      .slice(0, 8).map(elemento => ({ etiqueta: elemento.tagName, clase: elemento.className, ancho: elemento.getBoundingClientRect().width })),
  }));
  expect(medicion.principales).toBe(1);
  expect(medicion.documento, `Desbordamiento en ${page.url()}: ${JSON.stringify(medicion.desbordados)}`).toBeLessThanOrEqual(medicion.ancho);
  return medicion;
}

// Ampliación real de las fuentes computadas. No cambia viewport, zoom CSS, transform ni dimensiones.
// Se toma primero la lista completa para no multiplicar dos veces los tamaños heredados.
export async function ampliarTexto(page) {
  const resultado = await page.evaluate(() => {
    const ancho = innerWidth;
    const lista = [...document.body.querySelectorAll('*')].filter(elemento => elemento instanceof HTMLElement)
      .map(elemento => [elemento, parseFloat(getComputedStyle(elemento).fontSize)]);
    const muestra = document.querySelector('h1, h2');
    const antes = parseFloat(getComputedStyle(muestra).fontSize);
    for (const [elemento, tamano] of lista) elemento.style.fontSize = `${tamano * 2}px`;
    return { anchoAntes: ancho, anchoDespues: innerWidth, antes, despues: parseFloat(getComputedStyle(muestra).fontSize) };
  });
  expect(resultado.anchoDespues).toBe(resultado.anchoAntes);
  expect(resultado.despues).toBeCloseTo(resultado.antes * 2, 3);
  return resultado;
}

export async function espaciarTexto(page) {
  await page.addStyleTag({ content: '* { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-bottom: 2em !important; }' });
}
