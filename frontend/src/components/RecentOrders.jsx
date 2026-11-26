import { formatearMonto } from './dashboard/formato';

const ETIQUETAS_ESTADO = {
  PENDIENTE: 'Pendiente',
  PAGADO: 'Pagado',
  EN_PREPARACION: 'En preparación',
  ENVIADO: 'Despachado',
  ENTREGADO: 'Entregado',
  CANCELADO: 'Cancelado',
};

// Los 5 pedidos más recientes, compactos para ir junto a "Más vendidos". Sin colores de alerta: el estado va escrito
export default function RecentOrders({ ordenes = [], onVerTodos }) {
  return (
    <section className="dashboard-bloque" aria-labelledby="dashboard-ultimos-pedidos">
      <div className="dashboard-bloque-encabezado">
        <h3 id="dashboard-ultimos-pedidos" className="dashboard-bloque-titulo">Últimos pedidos</h3>
        {onVerTodos && ordenes.length > 0 && (
          <button type="button" className="dashboard-ver" onClick={onVerTodos}>
            Ver todos{' '}<span className="visualmente-oculto">los pedidos</span> <span aria-hidden="true">→</span>
          </button>
        )}
      </div>
      {ordenes.length === 0 ? (
        <p className="dashboard-vacio">No hay pedidos registrados.</p>
      ) : (
        <table className="dashboard-tabla dashboard-tabla--pedidos">
          <caption className="visualmente-oculto">Los 5 pedidos más recientes</caption>
          <thead>
            <tr>
              <th scope="col">Pedido</th>
              <th scope="col">Cliente</th>
              <th scope="col">Estado</th>
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {ordenes.map((orden) => (
              <tr key={orden.id}>
                <th scope="row">#{orden.id}</th>
                <td className="dashboard-tabla-cliente">{orden.cliente || '—'}</td>
                <td><span className="dashboard-estado">{ETIQUETAS_ESTADO[orden.estado] || orden.estado}</span></td>
                <td>{formatearMonto(orden.total_final)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
