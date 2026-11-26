import { obtenerEtiquetaProducto } from '../utils/etiquetasProducto';
import './EtiquetaProducto.css';

export default function EtiquetaProducto({ producto, etiquetaSeccion, enFicha = false }) {
  // La ficha conserva su presentación anterior cuando el producto no tiene etiqueta propia.
  if (enFicha && !producto.etiqueta?.trim() && !producto.solo_suscriptores) return null;
  const etiqueta = obtenerEtiquetaProducto(producto, etiquetaSeccion);
  if (!etiqueta) return null;
  const clases = ['tarjeta-producto-etiqueta'];
  if (etiqueta.agotado) clases.push('tarjeta-producto-etiqueta--agotado');
  if (etiqueta.personalizada) clases.push(`tarjeta-producto-etiqueta--${etiqueta.color}`);
  if (enFicha) clases.push('tarjeta-producto-etiqueta--ficha');
  return <span className={clases.join(' ')}>{etiqueta.texto}</span>;
}
