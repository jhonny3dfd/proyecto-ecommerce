import { formatearMonto, plural } from './formato';

export default function MasVendidos({ productos }) {
  return (
    <section className="dashboard-bloque" aria-labelledby="dashboard-mas-vendidos">
      <h3 id="dashboard-mas-vendidos" className="dashboard-bloque-titulo">Más vendidos</h3>
      {productos.length === 0 ? (
        <p className="dashboard-vacio">Aún no hay ventas en este periodo.</p>
      ) : (
        <ol className="dashboard-ranking">
          {productos.map((producto) => (
            <li key={producto.producto_id}>
              <span className="dashboard-ranking-nombre">{producto.nombre}</span>
              <span className="dashboard-ranking-cifra">{plural(producto.unidades, 'unidad', 'unidades')}</span>
              <span className="dashboard-ranking-monto">{formatearMonto(producto.total)}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
