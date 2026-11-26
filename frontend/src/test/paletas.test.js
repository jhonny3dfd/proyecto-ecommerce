import { describe, it, expect } from 'vitest';
import { PALETTES, TEMA_PREDETERMINADO, aplicarPaleta, obtenerPaleta } from '../constants/palettes';

// Contraste WCAG 2.1 entre dos colores #RRGGBB
const luminancia = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const canal = parseInt(hex.slice(i, i + 2), 16) / 255;
    return canal <= 0.03928 ? canal / 12.92 : ((canal + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contraste = (a, b) => {
  const [clara, oscura] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (clara + 0.05) / (oscura + 0.05);
};

// Textos claros fijos sobre el fondo del footer y de la barra del panel (footer.css y Admin.css)
const TEXTO_FOOTER = '#F3EFE9';
const TEXTO_FOOTER_SECUNDARIO = '#B9B1A6';
const TEXTO_BARRA_PANEL = '#D9D2C8';

const variable = (nombre) => document.documentElement.style.getPropertyValue(nombre);

describe('Paletas de la tienda (RF-01.2)', () => {
  it('ofrece 8 temas con los IDs 1 a 8 que guarda el backend, y el 1 es el predeterminado', () => {
    expect(PALETTES.map(({ id }) => id)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(TEMA_PREDETERMINADO).toBe(1);
  });

  it('cada tema define todos sus colores', () => {
    const claves = ['primary', 'onPrimary', 'secondary', 'accent', 'background', 'surface', 'text', 'muted', 'border', 'footer'];
    for (const { name, colors } of PALETTES) {
      expect(name).toBeTruthy();
      for (const clave of claves) expect(colors[clave], `${name}.${clave}`).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('un ID desconocido usa el primer tema', () => {
    for (const valor of [9, 0, 'abc', undefined]) expect(obtenerPaleta(valor).id).toBe(1);
    expect(obtenerPaleta('3').id).toBe(3);
  });

  it('aplicarPaleta pone los colores del tema en las variables que usa la tienda', () => {
    const { colors } = obtenerPaleta(2);

    aplicarPaleta(2);

    expect(variable('--color-primary')).toBe(colors.primary);
    expect(variable('--color-on-primary')).toBe(colors.onPrimary);
    expect(variable('--color-muted')).toBe(colors.muted);
    expect(variable('--color-footer')).toBe(colors.footer);
    expect(variable('--catalogo-text')).toBe(colors.text);
  });
});

// RNF-01: contraste AA (>= 4,5:1) en todos los temas para cada combinación de texto y fondo que usa la tienda
describe.each(PALETTES)('Contraste AA del tema $name', ({ colors }) => {
  const combinaciones = [
    ['texto sobre el fondo', colors.text, colors.background],
    ['texto sobre tarjetas', colors.text, colors.surface],
    ['texto sobre secciones alternas', colors.text, colors.secondary],
    ['texto secundario sobre el fondo', colors.muted, colors.background],
    ['texto secundario sobre tarjetas', colors.muted, colors.surface],
    ['texto secundario sobre secciones alternas', colors.muted, colors.secondary],
    ['texto de los botones', colors.onPrimary, colors.primary],
    ['antetítulos y enlaces sobre el fondo', colors.primary, colors.background],
    ['antetítulos y enlaces sobre tarjetas', colors.primary, colors.surface],
    ['texto del footer', TEXTO_FOOTER, colors.footer],
    ['texto secundario del footer', TEXTO_FOOTER_SECUNDARIO, colors.footer],
    ['menú de la barra del panel', TEXTO_BARRA_PANEL, colors.footer],
  ];

  it.each(combinaciones)('%s', (_, texto, fondo) => {
    expect(contraste(texto, fondo)).toBeGreaterThanOrEqual(4.5);
  });

  it('el botón principal mantiene el contraste con la opacidad del hover', () => {
    // index.css baja la opacidad de .boton-primario a 0.88: texto y fondo se mezclan con lo que hay detrás
    const mezclar = (hex, detras) => '#' + [1, 3, 5].map((i) => Math.round(
      parseInt(hex.slice(i, i + 2), 16) * 0.88 + parseInt(detras.slice(i, i + 2), 16) * 0.12,
    ).toString(16).padStart(2, '0')).join('');
    for (const detras of [colors.background, colors.surface, colors.secondary]) {
      expect(contraste(mezclar(colors.onPrimary, detras), mezclar(colors.primary, detras))).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('permite identificar los campos sobre cada fondo sin oscurecer bordes decorativos', () => {
    aplicarPaleta(PALETTES.find(p => p.colors === colors).id);
    expect(variable('--color-control-border')).toBe(colors.controlBorder);
    for (const fondo of [colors.surface, colors.background, colors.secondary]) {
      expect(contraste(colors.controlBorder, fondo)).toBeGreaterThanOrEqual(3);
    }
    expect(colors.controlBorder).not.toBe(colors.border);
  });
});
