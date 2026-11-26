import { textoVariante } from '../../utils/suscripciones';
import { Link } from 'react-router-dom';

// Qué recibe el cliente en cada entrega: uno de los productos del plan y su variante (RN-03: una variante sin stock
// para una entrega no se puede elegir). `valor`: { producto_mongo_id, variante_sku }
export default function ElegirProducto({ productos, valor, onCambiar, unidades = 1, prefijo = 'suscripcion' }) {
  const producto = productos.find(p => p.id === valor.producto_mongo_id) || null;
  const variantes = producto?.variantes || [];

  const elegirProducto = (elegido) => {
    // Con una sola variante disponible, queda elegida
    const disponibles = elegido.variantes.filter(v => v.disponible);
    onCambiar({ producto_mongo_id: elegido.id, variante_sku: disponibles.length === 1 ? disponibles[0].sku : '' });
  };

  if (productos.length === 0) {
    return <p className="checkout-aviso checkout-aviso--advertencia">Este plan no tiene productos disponibles por ahora.</p>;
  }

  return (
    <>
      <fieldset className="checkout-grupo">
        <legend className="checkout-etiqueta">Producto</legend>
        <div className="suscripcion-productos">
          {productos.map(p => {
            const sinStock = !p.variantes.some(v => v.disponible);
            const elegido = valor.producto_mongo_id === p.id;
            return (
              <label key={p.id} className={`suscripcion-producto${elegido ? ' suscripcion-producto--elegido' : ''}${sinStock ? ' suscripcion-producto--agotado' : ''}`}>
                <input type="radio" name={`${prefijo}-producto`} value={p.id} checked={elegido} disabled={sinStock}
                  onChange={() => elegirProducto(p)} />
                {p.imagen
                  ? <img src={p.imagen} alt="" className="suscripcion-producto-foto" loading="lazy" />
                  : <span className="suscripcion-producto-foto" aria-hidden="true" />}
                <span className="suscripcion-producto-texto">
                  <strong>{p.nombre}</strong>
                  {p.categoria && <span className="checkout-ayuda">{p.categoria}</span>}
                  {p.requiere_suscripcion
                    ? <span className="checkout-ayuda">Exclusivo para suscriptores con acceso a este plan.</span>
                    : sinStock && <span className="checkout-ayuda">Sin stock por ahora</span>}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      {productos.some(p => p.requiere_suscripcion) && <p>Para elegir los exclusivos necesitas una suscripción vigente.{' '}
        <Link to="/suscripcion">Ver planes de Suscripción</Link></p>}

      {producto && variantes.length > 1 && (
        <div className="checkout-campo">
          <label htmlFor={`${prefijo}-variante`}>Opción</label>
          <select id={`${prefijo}-variante`} value={valor.variante_sku} aria-describedby={`${prefijo}-variante-ayuda`}
            onChange={e => onCambiar({ ...valor, variante_sku: e.target.value })}>
            <option value="" disabled>Elige una opción</option>
            {variantes.map(v => (
              <option key={v.sku} value={v.sku} disabled={!v.disponible}>
                {textoVariante(v.atributos) || v.sku}{v.disponible ? '' : ' (sin stock)'}
              </option>
            ))}
          </select>
          <span id={`${prefijo}-variante-ayuda`} className="checkout-ayuda">
            {unidades === 1 ? 'Recibes 1 unidad en cada entrega.' : `Recibes ${unidades} unidades en cada entrega.`}
          </span>
        </div>
      )}
      {producto && variantes.length <= 1 && (
        <p className="checkout-ayuda">
          {unidades === 1 ? 'Recibes 1 unidad en cada entrega.' : `Recibes ${unidades} unidades en cada entrega.`}
        </p>
      )}
    </>
  );
}
