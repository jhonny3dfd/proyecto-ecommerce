import { plural } from './formato';

// Qué dice cada tarea y adónde lleva su "Ver" (la vista del panel y el filtro con que se abre)
const TAREAS = {
  POR_PREPARAR: {
    texto: (n) => `${plural(n, 'pedido pagado', 'pedidos pagados')} por preparar`,
    vista: 'ventas', filtro: { estado: 'PAGADO' },
  },
  TRANSFERENCIAS: {
    texto: (n) => `${plural(n, 'transferencia')} por validar`,
    vista: 'ventas', filtro: { estado: 'PENDIENTE' },
  },
  REVISION: {
    texto: (n) => `${plural(n, 'pedido')} para revisar`,
    vista: 'ventas', filtro: { revision: true },
  },
  ORDEN_TRANSPORTE: {
    texto: (n) => `${plural(n, 'orden', 'órdenes')} de transporte con error`,
    vista: 'ventas', filtro: { ordenTransporte: true },
  },
  DOCUMENTOS: {
    texto: (n) => `${plural(n, 'boleta, factura o nota de crédito', 'boletas, facturas o notas de crédito')} por emitir`,
    vista: 'ventas', filtro: { documento: true },
  },
  COTIZACIONES: {
    texto: (n) => plural(n, 'cotización nueva', 'cotizaciones nuevas'),
    vista: 'cotizaciones',
  },
  RESENAS: {
    texto: (n) => `${plural(n, 'reseña')} por aprobar`,
    vista: 'resenas',
  },
};

function BotonVer({ onClick, contexto, children = 'Ver' }) {
  return (
    <button type="button" className="dashboard-ver" onClick={onClick}>
      {children}{' '}<span className="visualmente-oculto">{contexto}</span> <span aria-hidden="true">→</span>
    </button>
  );
}

function ListaVariantes({ titulo, variantes }) {
  if (!variantes.length) return null;
  return (
    <>
      <h4 className="dashboard-stock-titulo">{titulo}</h4>
      <ul className="dashboard-stock-lista">
        {variantes.map((variante) => (
          <li key={`${variante.producto_id}-${variante.sku}`}>
            <span>{variante.producto} · {variante.detalle || variante.sku}</span>
            <span className="dashboard-stock-unidades">{plural(variante.stock, 'unidad', 'unidades')}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

// RF-03.1: lo que el admin tiene que atender. Solo aparece lo que no está en cero; si no hay nada, "Todo al día"
export default function ParaHoy({ pendientes, error, onIrA }) {
  return (
    <section className="dashboard-bloque dashboard-para-hoy" aria-labelledby="dashboard-para-hoy">
      <h3 id="dashboard-para-hoy" className="dashboard-bloque-titulo">Para hoy</h3>
      {error && <p role="alert" className="dashboard-error">{error}</p>}
      {pendientes?.al_dia && (
        <p className="dashboard-al-dia">
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
          Todo al día: no hay pedidos ni avisos pendientes.
        </p>
      )}
      {pendientes && !pendientes.al_dia && (
        <ul className="dashboard-tareas">
          {pendientes.tareas.map(({ tarea, cantidad, por_vencer: porVencer }) => {
            const { texto, vista, filtro } = TAREAS[tarea];
            return (
              <li key={tarea}>
                <span>
                  {texto(cantidad)}
                  {porVencer > 0 && (
                    <strong className="dashboard-urgente">
                      {' '}({porVencer === 1 ? '1 vence' : `${porVencer} vencen`} en menos de 24 horas)
                    </strong>
                  )}
                </span>
                <BotonVer onClick={() => onIrA(vista, filtro)} contexto={texto(cantidad)} />
              </li>
            );
          })}
          {(pendientes.agotadas.length > 0 || pendientes.stock_bajo.length > 0) && (
            <li className="dashboard-tarea-stock">
              <details>
                <summary>
                  {[
                    pendientes.agotadas.length > 0 && (
                      <strong key="agotadas" className="dashboard-urgente">
                        {plural(pendientes.agotadas.length, 'variante agotada', 'variantes agotadas')}
                      </strong>
                    ),
                    pendientes.stock_bajo.length > 0 && (
                      <span key="bajo">{plural(pendientes.stock_bajo.length, 'con stock bajo', 'con stock bajo')}</span>
                    ),
                  ].filter(Boolean).reduce((partes, parte) => (partes.length ? [...partes, ' · ', parte] : [parte]), [])}
                </summary>
                <ListaVariantes titulo="Agotadas" variantes={pendientes.agotadas} />
                <ListaVariantes titulo="Con 5 unidades o menos" variantes={pendientes.stock_bajo} />
              </details>
              <BotonVer onClick={() => onIrA('inventario')} contexto="el inventario">Ir al inventario</BotonVer>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}
