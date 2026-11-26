import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';
import { ESTADOS_SUSCRIPCION, fechaLarga, formatoPesos, nombreMedioPago } from '../utils/suscripciones';

// Suscriptores (pedido de un cliente, opcional): quién está suscrito, a qué, cuándo es su próxima entrega y si
// tiene un pedido por pagar. Los cambios los hace el cliente desde su cuenta; los pedidos se atienden en Ventas
// Igual que PaginacionSuscriptores en el backend
const POR_PAGINA = 20;
const FILTRO_INICIAL = { estado: '', plan: '', pago_pendiente: false, buscar: '', pagina: 1 };

export default function GestorSuscriptores() {
  const [filtro, setFiltro] = useState(FILTRO_INICIAL);
  const [buscar, setBuscar] = useState('');
  const [planes, setPlanes] = useState([]);
  const [cargada, setCargada] = useState({ filtro: null, filas: [], total: 0 });
  const [error, setError] = useState('');

  useEffect(() => {
    clienteAxios.get('ventas/admin/suscripciones/planes/')
      .then(({ data }) => setPlanes(data?.planes || []))
      .catch(() => setPlanes([]));
  }, []);

  useEffect(() => {
    let vigente = true;
    const params = { pagina: filtro.pagina };
    if (filtro.estado) params.estado = filtro.estado;
    if (filtro.plan) params.plan = filtro.plan;
    if (filtro.pago_pendiente) params.pago_pendiente = 1;
    if (filtro.buscar) params.buscar = filtro.buscar;
    clienteAxios.get('ventas/admin/suscripciones/', { params })
      .then(({ data }) => {
        if (!vigente) return;
        setError('');
        setCargada({ filtro, filas: data.results || [], total: data.count || 0 });
      })
      .catch(() => {
        if (!vigente) return;
        setError('No se pudieron cargar los suscriptores.');
        setCargada({ filtro, filas: [], total: 0 });
      });
    return () => { vigente = false; };
  }, [filtro]);

  const cambiar = (cambios) => setFiltro(actual => ({ ...actual, ...cambios, pagina: 1 }));
  const cargando = cargada.filtro !== filtro;
  const paginas = Math.ceil(cargada.total / POR_PAGINA);
  const hayFiltros = filtro.estado || filtro.plan || filtro.pago_pendiente || filtro.buscar;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Cada entrega es un pedido normal: lo ves en Ventas cuando se crea, unos días antes de la fecha, y lo
        preparas y despachas como los demás. Los clientes pausan, saltan una entrega, cambian el producto o cancelan
        desde su cuenta. Los planes se configuran en Configuración &gt; Suscripciones.
      </p>

      <form className="suscriptores-filtros" role="search" aria-label="Filtrar suscriptores"
        onSubmit={e => { e.preventDefault(); cambiar({ buscar: buscar.trim() }); }}>
        <div className="admin-campo">
          <label htmlFor="suscriptores-estado">Estado</label>
          <select id="suscriptores-estado" value={filtro.estado} onChange={e => cambiar({ estado: e.target.value })}>
            <option value="">Todos</option>
            {ESTADOS_SUSCRIPCION.map(([valor, etiqueta]) => <option key={valor} value={valor}>{etiqueta}</option>)}
          </select>
        </div>
        <div className="admin-campo">
          <label htmlFor="suscriptores-plan">Plan</label>
          <select id="suscriptores-plan" value={filtro.plan} onChange={e => cambiar({ plan: e.target.value })}>
            <option value="">Todos</option>
            {planes.map(plan => <option key={plan.id} value={plan.id}>{plan.nombre}</option>)}
          </select>
        </div>
        <div className="admin-campo suscriptores-buscar">
          <label htmlFor="suscriptores-buscar">Buscar</label>
          <div className="suscriptores-buscar-fila">
            <input id="suscriptores-buscar" type="search" value={buscar} onChange={e => setBuscar(e.target.value)}
              placeholder="Nombre, correo o producto" />
            <button type="submit" className="boton boton-contorno">Buscar</button>
          </div>
        </div>
        <label className="admin-casilla suscriptores-pendiente">
          <input type="checkbox" checked={filtro.pago_pendiente} onChange={e => cambiar({ pago_pendiente: e.target.checked })} />
          Solo con un pedido por pagar
        </label>
      </form>

      {error && <p role="alert" className="admin-aviso admin-aviso--error">{error}</p>}

      <p role="status" className="texto-secundario suscriptores-total">
        {cargando ? '' : `${cargada.total} ${cargada.total === 1 ? 'suscripción' : 'suscripciones'}${hayFiltros ? ' con estos filtros' : ''}`}
      </p>

      {cargando ? (
        <Cargando texto="Cargando suscriptores..."><EsqueletoLista /></Cargando>
      ) : cargada.filas.length === 0 ? (
        <p className="texto-secundario">{hayFiltros ? 'Ninguna suscripción coincide con estos filtros.' : 'Todavía no tienes suscriptores.'}</p>
      ) : (
        <ul className="lista-sin-estilo cotizaciones-lista">
          {cargada.filas.map(fila => (
            <li key={fila.id} className="cotizacion-tarjeta">
              <article aria-labelledby={`suscripcion-${fila.id}-titulo`}>
                <div className="cotizacion-tarjeta-encabezado">
                  <h3 id={`suscripcion-${fila.id}-titulo`}>{fila.cliente?.nombre || fila.cliente?.email} · {fila.plan.nombre}</h3>
                  <span className={`blog-admin-estado${fila.estado === 'ACTIVA' ? ' blog-admin-estado--publicada' : ''}`}>
                    {fila.estado_texto}
                  </span>
                </div>
                <p className="texto-secundario cotizacion-tarjeta-fecha">
                  Suscripción #{fila.id}, desde el {new Date(fila.fecha_creacion).toLocaleDateString('es-CL', { day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
                <dl className="cotizacion-tarjeta-datos">
                  <dt>Correo</dt>
                  <dd><a href={`mailto:${fila.cliente?.email}`}>{fila.cliente?.email}</a></dd>
                  <dt>Producto</dt>
                  <dd>{fila.plan.unidades} × {fila.producto}</dd>
                  <dt>Frecuencia</dt>
                  <dd>{fila.plan.frecuencia_texto}, {formatoPesos(fila.plan.precio)} por entrega</dd>
                  <dt>Entrega</dt>
                  <dd>{fila.entrega.texto}</dd>
                  <dt>Pago</dt>
                  <dd>{nombreMedioPago(fila.metodo_pago)}</dd>
                  {fila.estado !== 'CANCELADA' && (
                    <>
                      <dt>Próxima entrega</dt>
                      <dd>{fila.estado === 'PAUSADA' || !fila.proxima_entrega ? 'En pausa' : fechaLarga(fila.proxima_entrega)}</dd>
                    </>
                  )}
                  {fila.pedido_pendiente && (
                    <>
                      <dt>Por pagar</dt>
                      <dd>
                        Pedido #{fila.pedido_pendiente.orden_id} de {formatoPesos(fila.pedido_pendiente.total)}, entrega
                        del {fechaLarga(fila.pedido_pendiente.ciclo_fecha)}
                      </dd>
                    </>
                  )}
                  {fila.estado === 'CANCELADA' && fila.motivo_cancelacion && (
                    <>
                      <dt>Motivo</dt>
                      <dd>{fila.motivo_cancelacion}</dd>
                    </>
                  )}
                </dl>
              </article>
            </li>
          ))}
        </ul>
      )}

      {!cargando && paginas > 1 && (
        <nav className="publicacion-acciones cotizaciones-paginacion" aria-label="Páginas de suscriptores">
          <button type="button" className="boton boton-contorno" disabled={filtro.pagina === 1}
            onClick={() => setFiltro(actual => ({ ...actual, pagina: actual.pagina - 1 }))}>
            <span aria-hidden="true">←</span> Anteriores
          </button>
          <span className="texto-secundario">Página {filtro.pagina} de {paginas}</span>
          <button type="button" className="boton boton-contorno" disabled={filtro.pagina === paginas}
            onClick={() => setFiltro(actual => ({ ...actual, pagina: actual.pagina + 1 }))}>
            Siguientes <span aria-hidden="true">→</span>
          </button>
        </nav>
      )}
    </>
  );
}
