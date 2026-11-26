import { obtenerDatosPrecioYStock } from './precios';

// Roles de la paleta activa: el texto ya tiene una pareja de contraste definida.
export const COLORES_ETIQUETA_PRODUCTO = [
  { valor: 'primary', nombre: 'Principal', fondo: 'primary', texto: 'onPrimary' },
  { valor: 'secondary', nombre: 'Secundario', fondo: 'secondary', texto: 'text' },
  { valor: 'accent', nombre: 'Acento', fondo: 'accent', texto: 'text' },
  { valor: 'text', nombre: 'Oscuro', fondo: 'text', texto: 'surface' },
];

export function obtenerEtiquetaProducto(producto, etiquetaSeccion) {
  const privada = Boolean(producto.coleccion_privada);
  const { agotado, tieneOferta } = obtenerDatosPrecioYStock(producto.variantes);
  if (!privada && agotado) return { texto: 'Agotado', color: 'text', agotado: true };
  if (producto.solo_suscriptores) return { texto: 'Exclusivo suscriptores', color: 'primary', personalizada: true };
  const propia = producto.etiqueta?.trim();
  if (propia) {
    const color = COLORES_ETIQUETA_PRODUCTO.some(opcion => opcion.valor === producto.etiqueta_color)
      ? producto.etiqueta_color : 'primary';
    return { texto: propia, color, personalizada: true };
  }
  if (privada) return null;
  const texto = tieneOferta ? 'Oferta' : etiquetaSeccion;
  return texto ? { texto, color: 'primary' } : null;
}
