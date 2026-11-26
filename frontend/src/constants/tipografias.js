// RF-01.2: las 5 combinaciones de fuentes (títulos + texto) que el admin elige en el panel. Los IDs coinciden con
// ConfiguracionGlobal.tipografia_seleccionada (1 a 5). Las fuentes vienen incluidas en la tienda (@fontsource): se
// sirven desde el mismo servidor, sin pedirle nada a Google, y el navegador solo descarga las de la combinación
// elegida (se registran con la API FontFace al aplicarla).
import cormorantLatin from '@fontsource-variable/cormorant-garamond/files/cormorant-garamond-latin-wght-normal.woff2?url';
import cormorantLatinExt from '@fontsource-variable/cormorant-garamond/files/cormorant-garamond-latin-ext-wght-normal.woff2?url';
import interLatin from '@fontsource-variable/inter/files/inter-latin-wght-normal.woff2?url';
import interLatinExt from '@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2?url';
import oswaldLatin from '@fontsource-variable/oswald/files/oswald-latin-wght-normal.woff2?url';
import oswaldLatinExt from '@fontsource-variable/oswald/files/oswald-latin-ext-wght-normal.woff2?url';
import sourceSansLatin from '@fontsource-variable/source-sans-3/files/source-sans-3-latin-wght-normal.woff2?url';
import sourceSansLatinExt from '@fontsource-variable/source-sans-3/files/source-sans-3-latin-ext-wght-normal.woff2?url';
import dmSerifLatin from '@fontsource/dm-serif-display/files/dm-serif-display-latin-400-normal.woff2?url';
import dmSerifLatinExt from '@fontsource/dm-serif-display/files/dm-serif-display-latin-ext-400-normal.woff2?url';
import dmSansLatin from '@fontsource-variable/dm-sans/files/dm-sans-latin-wght-normal.woff2?url';
import dmSansLatinExt from '@fontsource-variable/dm-sans/files/dm-sans-latin-ext-wght-normal.woff2?url';
import manropeLatin from '@fontsource-variable/manrope/files/manrope-latin-wght-normal.woff2?url';
import manropeLatinExt from '@fontsource-variable/manrope/files/manrope-latin-ext-wght-normal.woff2?url';
import fredokaLatin from '@fontsource-variable/fredoka/files/fredoka-latin-wght-normal.woff2?url';
import fredokaLatinExt from '@fontsource-variable/fredoka/files/fredoka-latin-ext-wght-normal.woff2?url';
import nunitoLatin from '@fontsource-variable/nunito/files/nunito-latin-wght-normal.woff2?url';
import nunitoLatinExt from '@fontsource-variable/nunito/files/nunito-latin-ext-wght-normal.woff2?url';

// Subconjuntos de Fontsource: latin trae el español (ñ, tildes, ¿, ¡); latin-ext, letras menos comunes
const LATIN = 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,'
  + 'U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
const LATIN_EXT = 'U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,'
  + 'U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF';

const SERIF = "Georgia, 'Times New Roman', serif";
const SANS = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";

const FUENTES = {
  cormorant: { latin: cormorantLatin, latinExt: cormorantLatinExt, pesos: '300 700', respaldo: SERIF },
  inter: { latin: interLatin, latinExt: interLatinExt, pesos: '100 900', respaldo: SANS },
  oswald: { latin: oswaldLatin, latinExt: oswaldLatinExt, pesos: '200 700', respaldo: SANS },
  sourceSans: { latin: sourceSansLatin, latinExt: sourceSansLatinExt, pesos: '200 900', respaldo: SANS },
  dmSerif: { latin: dmSerifLatin, latinExt: dmSerifLatinExt, pesos: '400', respaldo: SERIF },
  dmSans: { latin: dmSansLatin, latinExt: dmSansLatinExt, pesos: '100 1000', respaldo: SANS },
  manrope: { latin: manropeLatin, latinExt: manropeLatinExt, pesos: '200 800', respaldo: SANS },
  fredoka: { latin: fredokaLatin, latinExt: fredokaLatinExt, pesos: '300 700', respaldo: SANS },
  nunito: { latin: nunitoLatin, latinExt: nunitoLatinExt, pesos: '200 1000', respaldo: SANS },
};

// Los tamaños del diseño están calibrados con Cormorant (títulos) e Inter (texto). "ajuste" es el size-adjust de
// cada fuente (medido el 2026-10-18 en el navegador): en los títulos iguala el ancho de Cormorant, para que la
// portada y los títulos corten igual; en el texto iguala la altura de la x de Inter, que es lo que hace cómoda la
// lectura. Así ninguna combinación descuadra el diseño. Oswald y Fredoka se midieron el 2026-11-09 con el mismo método
// (reemplazaron a Playfair y Fraunces, que se parecían demasiado a la Editorial).
export const TIPOGRAFIAS = [
  {
    id: 1,
    nombre: 'Editorial',
    descripcion: 'Elegante y clásica',
    titulos: { fuente: 'cormorant', nombre: 'Cormorant Garamond', ajuste: 1 },
    texto: { fuente: 'inter', nombre: 'Inter', ajuste: 1 },
  },
  {
    id: 2,
    nombre: 'Urbana',
    descripcion: 'Condensada y firme',
    titulos: { fuente: 'oswald', nombre: 'Oswald', ajuste: 1.03 },
    texto: { fuente: 'sourceSans', nombre: 'Source Sans 3', ajuste: 1.09 },
  },
  {
    id: 3,
    nombre: 'Moderna',
    descripcion: 'Títulos con carácter, texto limpio',
    titulos: { fuente: 'dmSerif', nombre: 'DM Serif Display', ajuste: 0.89 },
    texto: { fuente: 'dmSans', nombre: 'DM Sans', ajuste: 1.06 },
  },
  {
    id: 4,
    nombre: 'Minimalista',
    descripcion: 'Sin serifas, sobria y directa',
    titulos: { fuente: 'manrope', nombre: 'Manrope', ajuste: 0.85 },
    texto: { fuente: 'manrope', nombre: 'Manrope', ajuste: 1 },
  },
  {
    id: 5,
    nombre: 'Cercana',
    descripcion: 'Redondeada y amable',
    titulos: { fuente: 'fredoka', nombre: 'Fredoka', ajuste: 0.87 },
    texto: { fuente: 'nunito', nombre: 'Nunito', ajuste: 1.09 },
  },
];

export const TIPOGRAFIA_PREDETERMINADA = 1;
export const CLAVE_TIPOGRAFIA = 'ecommerce_tipografia';

export const obtenerTipografia = (id) =>
  TIPOGRAFIAS.find((tipografia) => tipografia.id === Number(id)) || TIPOGRAFIAS[0];

// Cada fuente se registra con un nombre propio por combinación y rol, porque el ajuste cambia (Manrope va al 85%
// en los títulos de la Minimalista y al 100% en su texto)
const familiaDe = (id, rol) => `Tienda ${rol} ${id}`;
const registradas = new Set();

const registrar = (familia, { fuente, ajuste }) => {
  if (registradas.has(familia) || typeof FontFace === 'undefined' || !document.fonts) return;
  registradas.add(familia);
  const { latin, latinExt, pesos } = FUENTES[fuente];
  for (const [archivo, unicodeRange] of [[latin, LATIN], [latinExt, LATIN_EXT]]) {
    const cara = new FontFace(familia, `url(${archivo}) format('woff2')`, {
      weight: pesos, unicodeRange, display: 'swap', sizeAdjust: `${Math.round(ajuste * 100)}%`,
    });
    document.fonts.add(cara);
  }
};

/** Pila de fuentes de una combinación (para las muestras del selector): registra sus fuentes si hace falta. */
export function familiasDe(id) {
  const tipografia = obtenerTipografia(id);
  const titulos = familiaDe(tipografia.id, 'Titulos');
  const texto = familiaDe(tipografia.id, 'Texto');
  registrar(titulos, tipografia.titulos);
  registrar(texto, tipografia.texto);
  return {
    titulos: `"${titulos}", ${FUENTES[tipografia.titulos.fuente].respaldo}`,
    texto: `"${texto}", ${FUENTES[tipografia.texto.fuente].respaldo}`,
  };
}

// Única función que cambia las fuentes: toda la tienda y el panel usan --fuente-titulos y --fuente-texto
export function aplicarTipografia(id) {
  const { titulos, texto } = familiasDe(id);
  const raiz = document.documentElement.style;
  raiz.setProperty('--fuente-titulos', titulos);
  raiz.setProperty('--fuente-texto', texto);
}
