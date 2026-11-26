import { useId } from 'react';
import { COLORES_ETIQUETA_PRODUCTO } from '../utils/etiquetasProducto';
import './EtiquetaProducto.css';
import './CampoEtiquetaProducto.css';

export default function CampoEtiquetaProducto({ etiqueta, color, onChange, disabled = false }) {
  const id = useId();
  return (
    <fieldset className="campo-etiqueta-producto" disabled={disabled}>
      <legend>Etiqueta del producto (opcional)</legend>
      <label htmlFor={`${id}-texto`}>Etiqueta</label>
      <input id={`${id}-texto`} type="text" value={etiqueta} maxLength={20}
        aria-describedby={`${id}-ayuda`} onChange={e => onChange({ etiqueta: e.target.value })} />
      <p id={`${id}-ayuda`} className="texto-secundario">
        {etiqueta.length}/20 caracteres. Deja el texto vacío para quitar la etiqueta.
      </p>
      <fieldset className="campo-etiqueta-colores">
        <legend>Color de la etiqueta</legend>
        <p className="texto-secundario">Colores de la paleta activa de tu tienda.</p>
        <div className="campo-etiqueta-opciones">
          {COLORES_ETIQUETA_PRODUCTO.map(opcion => (
            <label key={opcion.valor} className="campo-etiqueta-opcion">
              <input type="radio" name={`${id}-color`} value={opcion.valor}
                checked={color === opcion.valor} onChange={() => onChange({ etiqueta_color: opcion.valor })} />
              <span className="campo-etiqueta-muestra" aria-hidden="true"
                style={{ backgroundColor: `var(--color-${opcion.fondo})` }} />
              {opcion.nombre}
            </label>
          ))}
        </div>
      </fieldset>
      {etiqueta.trim() && (
        <div className="campo-etiqueta-vista" role="group" aria-label="Vista previa de la etiqueta">
          <span className={`tarjeta-producto-etiqueta tarjeta-producto-etiqueta--ficha tarjeta-producto-etiqueta--${color}`}>
            {etiqueta.trim()}
          </span>
        </div>
      )}
      <p className="texto-secundario campo-etiqueta-nota">
        Sin stock se mostrará «Agotado» en su lugar. Las obras de colección privada conservan su etiqueta.
      </p>
    </fieldset>
  );
}
