import { useState, useEffect } from 'react';
import clienteAxios from './auth/axiosConfig';
import DocumentoPedido from './DocumentoPedido';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoTabla } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

// Nombres de la interfaz. Las transiciones permitidas las informa el backend
const ETIQUETAS_ESTADO = {
  PENDIENTE: 'Pendiente',
  PAGADO: 'Pagado',
  EN_PREPARACION: 'En Preparación',
  ENVIADO: 'Despachado',
  ENTREGADO: 'Entregado',
  CANCELADO: 'Cancelado'
};

const ESTILOS_AVISO = {
  error: { backgroundColor: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b' },
  exito: { backgroundColor: '#f0fdf4', border: '1px solid #86efac', color: '#166534' }
};

const mensajeDeError = (error) => {
  const data = error.response?.data;
  return data?.estado?.[0] || data?.detail || 'Error inesperado. Inténtalo nuevamente.';
};

// Igual que PaginacionPedidos en el backend
const POR_PAGINA = 20;

// Para el mensaje de lista vacía con un filtro de estado
const PLURAL_ESTADO = {
  PENDIENTE: 'pendientes',
  PAGADO: 'pagados',
  EN_PREPARACION: 'en preparación',
  ENVIADO: 'despachados',
  ENTREGADO: 'entregados',
  CANCELADO: 'cancelados'
};

const mensajeVacio = ({ estado, revision, documento, ordenTransporte }) => {
  if (revision) return 'No hay pedidos que requieran revisión.';
  if (ordenTransporte) return 'No hay órdenes de transporte con error.';
  if (documento) return 'No hay boletas, facturas ni notas de crédito pendientes.';
  if (estado) return `No hay pedidos ${PLURAL_ESTADO[estado]} en este momento.`;
  return 'No hay pedidos registrados en la tienda.';
};

// `filtroInicial`: con qué filtro se abre (ej. desde un "Ver" del dashboard): { estado, revision, documento,
// ordenTransporte }
export default function GestorPedidos({ filtroInicial = {} }) {
  // `estado` vacío muestra todos. `version` vuelve a pedir la misma página después de una acción
  // `documento`: solo los que tienen boleta, factura o nota de crédito por emitir
  // `ordenTransporte`: solo los que esperan su orden de transporte y fallaron al generarla
  const [consulta, setConsulta] = useState(() => ({
    estado: filtroInicial.estado || '',
    revision: Boolean(filtroInicial.revision),
    documento: Boolean(filtroInicial.documento),
    ordenTransporte: Boolean(filtroInicial.ordenTransporte),
    pagina: 1,
    version: 0,
  }));
  // A qué consulta corresponde lo cargado: si no coincide con la pedida, aún está cargando
  const [cargada, setCargada] = useState({ consulta: null, pedidos: [], total: 0 });
  // { tipo: 'error' | 'exito', texto }
  const [aviso, setAviso] = useState(null);
  // Id del pedido que se está actualizando, para no enviar dos cambios a la vez
  const [enCurso, setEnCurso] = useState(null);

  useEffect(() => {
    let vigente = true;
    const params = { pagina: consulta.pagina };
    if (consulta.estado) params.estado = consulta.estado;
    if (consulta.revision) params.requiere_revision = 'true';
    if (consulta.documento) params.documento = 'pendiente';
    if (consulta.ordenTransporte) params.orden_transporte = 'error';
    clienteAxios.get('ventas/admin/ordenes/', { params })
      .then(({ data }) => {
        if (vigente) setCargada({ consulta, pedidos: data.results, total: data.count });
      })
      .catch((error) => {
        if (!vigente) return;
        // La última página se quedó vacía (sus pedidos cambiaron de estado): se vuelve a la anterior
        if (error.response?.status === 404 && consulta.pagina > 1) {
          setConsulta(actual => ({ ...actual, pagina: actual.pagina - 1 }));
          return;
        }
        console.error("Error al cargar las órdenes:", error);
        setAviso({ tipo: 'error', texto: 'No se pudieron cargar los pedidos.' });
        setCargada({ consulta, pedidos: [], total: 0 });
      });
    return () => { vigente = false; };
  }, [consulta]);

  // Los avisos de éxito se ocultan solos; los errores y las revisiones quedan hasta la próxima acción
  useEffect(() => {
    if (aviso?.tipo !== 'exito') return;
    const temporizador = setTimeout(() => setAviso(null), 5000);
    return () => clearTimeout(temporizador);
  }, [aviso]);

  const primeraCarga = !cargada.consulta;
  // Tras una acción (cambia solo `version`) la tabla sigue a la vista mientras se recarga, sin acciones
  const recargando = cargada.consulta !== consulta;
  const cargando = primeraCarga || cargada.consulta.estado !== consulta.estado
    || cargada.consulta.revision !== consulta.revision || cargada.consulta.documento !== consulta.documento
    || cargada.consulta.ordenTransporte !== consulta.ordenTransporte
    || cargada.consulta.pagina !== consulta.pagina;
  const ocupado = (pedido) => recargando || enCurso === pedido.id;
  const paginas = Math.ceil(cargada.total / POR_PAGINA);
  const pedidos = cargada.pedidos;

  const filtrar = (cambios) => {
    setAviso(null);
    setConsulta(actual => ({ ...actual, ...cambios, pagina: 1, version: 0 }));
  };

  const irA = (pagina) => {
    setAviso(null);
    setConsulta(actual => ({ ...actual, pagina }));
  };

  // Las transiciones disponibles dependen del nuevo estado: se recarga la página actual
  const recargar = () => setConsulta(actual => ({ ...actual, version: actual.version + 1 }));

  const handleCambioEstado = async (pedido, nuevoEstado) => {
    if (nuevoEstado === 'CANCELADO' && !window.confirm(
      `¿Cancelar el pedido #${pedido.id}? No se puede deshacer y el stock descontado vuelve al catálogo.`
    )) return;

    setEnCurso(pedido.id);
    setAviso(null);
    try {
      const { data } = await clienteAxios.patch(`ventas/admin/ordenes/${pedido.id}/estado/`, {
        estado: nuevoEstado
      });
      setAviso(data.requiere_revision
        ? { tipo: 'error', texto: `Pedido #${pedido.id} quedó ${ETIQUETAS_ESTADO[data.estado]}, pero requiere revisión: ${data.motivo_revision}.` }
        : { tipo: 'exito', texto: `Pedido #${pedido.id} actualizado a ${ETIQUETAS_ESTADO[data.estado]}.` });
    } catch (error) {
      setAviso({ tipo: 'error', texto: `No se pudo actualizar el pedido #${pedido.id}: ${mensajeDeError(error)}` });
    } finally {
      recargar();
      setEnCurso(null);
    }
  };

    // Registra una transferencia recibida después de cancelar el pedido por vencimiento.
  const handleRegistrarPagoFueraPlazo = async (pedido) => {
    setEnCurso(pedido.id);
    setAviso(null);

    try {
      await clienteAxios.post(
        `ventas/admin/ordenes/${pedido.id}/pago-fuera-plazo/`
      );

      setAviso({
        tipo: 'exito',
        texto: `Pago fuera de plazo registrado. El pedido #${pedido.id} quedó pendiente de revisión.`,
      });
    } catch (error) {
      setAviso({
        tipo: 'error',
        texto: `No se pudo registrar el pago fuera de plazo del pedido #${pedido.id}: ${mensajeDeError(error)}`,
      });
    } finally {
      recargar();
      setEnCurso(null);
    }
  };

  const handleResolverRevision = async (pedido) => {
    if (!window.confirm(
      `¿Ya resolviste el pedido #${pedido.id}? (por ejemplo, reembolsaste al comprador o conseguiste el producto)`
    )) return;

    setEnCurso(pedido.id);
    setAviso(null);
    try {
      await clienteAxios.post(`ventas/admin/ordenes/${pedido.id}/revision/resolver/`);
      setAviso({ tipo: 'exito', texto: `Revisión del pedido #${pedido.id} marcada como resuelta.` });
    } catch (error) {
      setAviso({ tipo: 'error', texto: `No se pudo resolver la revisión del pedido #${pedido.id}: ${mensajeDeError(error)}` });
    } finally {
      recargar();
      setEnCurso(null);
    }
  };

  // RF-02.3: si el courier falló al confirmarse el pago, el admin reintenta la orden de transporte
  const handleGenerarOT = async (pedido) => {
    setEnCurso(pedido.id);
    setAviso(null);
    try {
      const { data } = await clienteAxios.post(`ventas/admin/ordenes/${pedido.id}/orden-transporte/`);
      setAviso({ tipo: 'exito', texto: `Orden de transporte ${data.numero_seguimiento_tracking} generada para el pedido #${pedido.id}.` });
    } catch (error) {
      setAviso({ tipo: 'error', texto: `No se pudo generar la orden de transporte del pedido #${pedido.id}: ${mensajeDeError(error)}` });
    } finally {
      recargar();
      setEnCurso(null);
    }
  };

  const celdaEnvio = (pedido) => {
    if (pedido.numero_seguimiento_tracking) {
      return <span>OT {pedido.numero_seguimiento_tracking}</span>;
    }
    if (pedido.proveedor_logistico === 'RETIRO_LOCAL') {
      return <span style={{ color: 'var(--color-muted)' }}>Retiro en local</span>;
    }
    if (pedido.proveedor_logistico === 'ENTREGA_COORDINADA') {
      // La entrega la hace la tienda: la dirección para coordinarla con el comprador, que puede no haberla dado
      const direccion = pedido.direccion_envio_snapshot || {};
      const texto = [[direccion.calle, direccion.numero].filter(Boolean).join(' '), direccion.dpto_casa, direccion.comuna]
        .filter(Boolean).join(', ');
      return (
        <div style={{ fontSize: '0.9rem' }}>
          <span style={{ color: 'var(--color-muted)' }}>Entrega coordinada</span>
          <div>{texto || 'Dirección por acordar con el comprador'}</div>
        </div>
      );
    }
    // Lo que queda es un courier: muestra su OT, el error al generarla o el botón para reintentarla
    if (!pedido.proveedor_logistico) {
      return <span style={{ color: 'var(--color-muted)' }}>—</span>;
    }
    return (
      <div style={{ fontSize: '0.9rem' }}>
        {pedido.error_orden_transporte ? (
          <div style={{ color: '#991b1b' }}>
            <strong>Sin OT:</strong> {pedido.error_orden_transporte}
          </div>
        ) : (
          <span style={{ color: 'var(--color-muted)' }}>Sin OT</span>
        )}
        {pedido.puede_generar_orden_transporte && (
          <div>
            <button
              type="button"
              onClick={() => handleGenerarOT(pedido)}
              disabled={ocupado(pedido)}
              style={{ marginTop: '8px', padding: '6px 10px', backgroundColor: 'var(--color-surface)', color: 'var(--color-primary)', border: '1px solid var(--color-primary)', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
            >
              {pedido.error_orden_transporte ? 'Reintentar OT' : 'Generar OT'}
            </button>
          </div>
        )}
      </div>
    );
  };

  if (primeraCarga) return <Cargando texto="Cargando panel de pedidos..."><EsqueletoTabla filas={6} columnas={7} /></Cargando>;

  return (
    <div>
      {aviso && (
        <div
          role={aviso.tipo === 'error' ? 'alert' : 'status'}
          style={{ ...ESTILOS_AVISO[aviso.tipo], padding: '12px 16px', borderRadius: '6px', marginBottom: '16px' }}
        >
          {aviso.texto}
        </div>
      )}

      {/* Los filtros siguen a la vista mientras se carga, para no perder el foco */}
      <div style={{ display: 'flex', gap: '15px', marginBottom: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          Estado
          <select
            value={consulta.estado}
            onChange={(e) => filtrar({ estado: e.target.value })}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid var(--color-border)' }}
          >
            <option value="">Todos los estados</option>
            {Object.entries(ETIQUETAS_ESTADO).map(([clave, valor]) => (
              <option key={clave} value={clave}>{valor}</option>
            ))}
          </select>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={consulta.revision}
            onChange={(e) => filtrar({ revision: e.target.checked })}
          />
          Requiere revisión
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={consulta.documento}
            onChange={(e) => filtrar({ documento: e.target.checked })}
          />
          Solo con boleta o factura pendiente
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={consulta.ordenTransporte}
            onChange={(e) => filtrar({ ordenTransporte: e.target.checked })}
          />
          Con error en la orden de transporte
        </label>

        {!cargando && (
          <span style={{ marginLeft: 'auto', fontSize: '0.9rem', color: 'var(--color-muted)' }}>
            {cargada.total} pedido(s) encontrado(s)
          </span>
        )}
      </div>

      {cargando ? (
        <Cargando texto="Cargando pedidos..."><EsqueletoTabla filas={6} columnas={7} /></Cargando>
      ) : (
      <>
      <div tabIndex={0} role="region" aria-label="Pedidos y operaciones de venta" style={{ backgroundColor: 'var(--color-surface)', borderRadius: '8px', overflowX: 'auto' }}>
 
        <table style={{ width: '100%', textAlign: 'left', borderCollapse: 'collapse' }}>
          <thead style={{ backgroundColor: 'var(--color-secondary)', borderBottom: '2px solid var(--color-border)' }}>
            <tr>
              <th style={{ padding: '12px' }}>Nº Orden</th>
              <th style={{ padding: '12px' }}>Cliente</th>
              <th style={{ padding: '12px' }}>Total</th>
              <th style={{ padding: '12px' }}>Estado Actual</th>
              <th style={{ padding: '12px' }}>Boleta o factura</th>
              <th style={{ padding: '12px' }}>Revisión</th>
              <th style={{ padding: '12px' }}>Envío</th>
            </tr>
          </thead>
          <tbody>
            {pedidos.map(pedido => {
              const transiciones = pedido.transiciones_permitidas || [];
              return (
                <tr key={pedido.id} style={{ borderBottom: '1px solid var(--color-border)', verticalAlign: 'top' }}>
                  <td style={{ padding: '12px', fontWeight: 'bold' }}>
                    #{pedido.id}
                    {pedido.suscripcion && (
                      // Entrega de una suscripción (pedido de un cliente, opcional): se prepara como cualquier pedido
                      <span className="blog-admin-estado pedido-suscripcion">
                        Suscripción{pedido.ciclo_fecha ? ` · ${pedido.ciclo_fecha.split('-').reverse().join('-')}` : ''}
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {pedido.email_cliente || 'Usuario Registrado'}
                    {pedido.nombre_destinatario && (
                      // Quién recibe o retira (RF-02.3): a quién contactar para coordinar la entrega
                      <div style={{ marginTop: '4px', fontSize: '0.85rem', color: 'var(--color-muted)' }}>
                        Recibe: {pedido.nombre_destinatario}
                        {pedido.telefono_destinatario && (
                          <> · <a href={`tel:${pedido.telefono_destinatario}`} style={{ color: 'var(--color-primary)' }}>{pedido.telefono_destinatario}</a></>
                        )}
                      </div>
                    )}
                    {pedido.datos_empresa && (
                      // Compra como empresa: la tienda emite la factura con estos datos
                      <div style={{ marginTop: '4px', fontSize: '0.85rem', color: 'var(--color-muted)' }}>
                        <strong style={{ color: 'var(--color-text)' }}>Factura:</strong> {pedido.datos_empresa.razon_social} · RUT {pedido.datos_empresa.rut}
                        <div>{pedido.datos_empresa.giro} · {pedido.datos_empresa.direccion}</div>
                        <a href={`mailto:${pedido.datos_empresa.correo}`} style={{ color: 'var(--color-primary)' }}>{pedido.datos_empresa.correo}</a>
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px' }}>${Number(pedido.total_final).toLocaleString('es-CL')}</td>
                  <td style={{ padding: '12px' }}>
                    <select
                      aria-label={`Estado del pedido #${pedido.id}`}
                      value={pedido.estado}
                      onChange={(e) => handleCambioEstado(pedido, e.target.value)}
                      disabled={transiciones.length === 0 || ocupado(pedido)}
                      style={{
                        padding: '6px',
                        borderRadius: '4px',
                        border: '1px solid var(--color-border)',
                        cursor: transiciones.length === 0 ? 'not-allowed' : 'pointer'
                      }}
                    >
                      <option value={pedido.estado}>{ETIQUETAS_ESTADO[pedido.estado] || pedido.estado}</option>
                      {transiciones.map(estado => (
                        <option key={estado} value={estado}>
                          {ETIQUETAS_ESTADO[estado] || estado}
                        </option>
                      ))}
                    </select>
                    {pedido.estado === 'CANCELADO' && pedido.motivo_cancelacion && (
                      <div style={{ marginTop: '6px', fontSize: '0.85rem', color: 'var(--color-muted)' }}>
                        {pedido.motivo_cancelacion}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {/* La tienda emite el documento por su cuenta y anota aquí el folio */}
                    <DocumentoPedido
                      pedido={pedido}
                      deshabilitado={ocupado(pedido)}
                      onGuardado={(texto) => { setAviso({ tipo: 'exito', texto }); recargar(); }}
                    />
                  </td>
                  <td style={{ padding: '12px' }}>
                    {pedido.requiere_revision ? (
                      <div style={{ backgroundColor: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e', borderRadius: '6px', padding: '8px 10px', fontSize: '0.9rem' }}>
                        <strong>Requiere revisión:</strong> {pedido.motivo_revision}
                        <div>
                          <button
                            type="button"
                            onClick={() => handleResolverRevision(pedido)}
                            disabled={ocupado(pedido)}
                            style={{ marginTop: '8px', padding: '6px 10px', backgroundColor: 'var(--color-surface)', color: '#92400e', border: '1px solid #d97706', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
                          >
                            Marcar como revisada
                          </button>
                        </div>
                      </div>
                                        ) : pedido.estado === 'CANCELADO' &&
                      pedido.motivo_cancelacion === 'Pago no recibido a tiempo' ? (
                      <button
                        type="button"
                        onClick={() => handleRegistrarPagoFueraPlazo(pedido)}
                        disabled={ocupado(pedido)}
                        style={{
                          padding: '6px 10px',
                          backgroundColor: 'var(--color-surface)',
                          color: 'var(--color-primary)',
                          border: '1px solid var(--color-primary)',
                          borderRadius: '4px',
                          cursor: ocupado(pedido) ? 'not-allowed' : 'pointer',
                          fontWeight: 'bold',
                        }}
                      >
                        {enCurso === pedido.id && <Spinner />}
                        {enCurso === pedido.id
                          ? 'Registrando...'
                          : 'Registrar pago recibido fuera de plazo'}
                      </button>
                    ) : (
                      <span style={{ color: 'var(--color-muted)' }}>—</span>
                    )}

                  </td>
                  <td style={{ padding: '12px' }}>{celdaEnvio(pedido)}</td>
                </tr>
              );
            })}
            {pedidos.length === 0 && (
              <tr>
                <td colSpan="7" style={{ padding: '20px', textAlign: 'center', color: 'var(--color-muted)' }}>
                  {mensajeVacio(cargada.consulta)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {paginas > 1 && (
        <nav aria-label="Páginas de pedidos" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '15px', marginTop: '20px' }}>
          <button
            type="button"
            disabled={consulta.pagina === 1}
            onClick={() => irA(consulta.pagina - 1)}
            style={{ padding: '8px 12px', cursor: consulta.pagina === 1 ? 'not-allowed' : 'pointer' }}
          >
            Anterior
          </button>

          <span>Página {consulta.pagina} de {paginas}</span>

          <button
            type="button"
            disabled={consulta.pagina >= paginas}
            onClick={() => irA(consulta.pagina + 1)}
            style={{ padding: '8px 12px', cursor: consulta.pagina >= paginas ? 'not-allowed' : 'pointer' }}
          >
            Siguiente
          </button>
        </nav>
      )}
      </>
      )}
    </div>
  );
}
