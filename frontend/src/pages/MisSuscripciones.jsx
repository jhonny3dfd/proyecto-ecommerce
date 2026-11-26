import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoLista } from '../components/carga/EsqueletosPanel';
import Spinner from '../components/carga/Spinner';
import CambiarSuscripcion from '../components/suscripciones/CambiarSuscripcion';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { ACCIONES_SUSCRIPCION, fechaLarga, formatoPesos, nombreMedioPago } from '../utils/suscripciones';
import '../components/Checkout.css';
import './Suscripcion.css';

// Mis suscripciones (pedido de un cliente, opcional): ver cada una, pagar la entrega pendiente, pausar, reanudar,
// saltar o adelantar una entrega, cancelar y cambiar lo que recibe. El servidor dice qué acciones se permiten
const ORDEN_ACCIONES = ['adelantar', 'saltar', 'pausar', 'reanudar', 'cancelar'];

const MENSAJES_EXITO = {
  adelantar: 'Creamos el pedido de tu próxima entrega: págalo para que la tienda lo prepare.',
  saltar: (s) => `Saltaste una entrega: la próxima llega el ${fechaLarga(s.proxima_entrega)}.`,
  pausar: 'Pausaste tu suscripción. Puedes reanudarla cuando quieras.',
  reanudar: (s) => `Reanudaste tu suscripción: la próxima entrega es el ${fechaLarga(s.proxima_entrega)}.`,
  cancelar: 'Cancelaste tu suscripción.'
};

export default function MisSuscripciones() {
  const navigate = useNavigate();
  const config = useConfiguracionTienda();
  const conSesion = Boolean(localStorage.getItem('access_token'));
  const [estado, setEstado] = useState({ cargando: conSesion, suscripciones: [], activasEnTienda: true, error: '' });
  const [direcciones, setDirecciones] = useState([]);
  const [comunas, setComunas] = useState([]);
  const [editando, setEditando] = useState(null);
  const [enCurso, setEnCurso] = useState(null);
  const [aviso, setAviso] = useState(null);
  const botonesCambiar = useRef({});

  const irALogin = () => {
    localStorage.setItem('url_anterior_login', window.location.pathname);
    navigate('/login');
  };

  useEffect(() => {
    if (!conSesion) return;
    clienteAxios.get('ventas/suscripciones/mias/')
      .then(({ data }) => setEstado({ cargando: false, suscripciones: data.suscripciones || [],
        activasEnTienda: data.activas_en_tienda !== false, error: '' }))
      .catch(error => {
        if (error.response?.status === 401) {
          setEstado({ cargando: false, suscripciones: [], activasEnTienda: true, error: 'sesion' });
          return;
        }
        setEstado({ cargando: false, suscripciones: [], activasEnTienda: true, error: 'No se pudieron cargar tus suscripciones.' });
      });
    clienteAxios.get('ventas/direcciones/')
      .then(({ data }) => setDirecciones(Array.isArray(data) ? data : []))
      .catch(() => setDirecciones([]));
  }, [conSesion]);

  const hayCouriers = (config?.couriers || []).length > 0;
  useEffect(() => {
    if (!hayCouriers || editando === null) return;
    clienteAxios.get('ventas/logistica/comunas/')
      .then(({ data }) => setComunas(data.comunas || []))
      .catch(() => setComunas([]));
  }, [hayCouriers, editando]);

  const reemplazar = (actualizada) => setEstado(actual => ({
    ...actual, suscripciones: actual.suscripciones.map(s => (s.id === actualizada.id ? actualizada : s))
  }));

  const ejecutar = async (suscripcion, accion) => {
    const { confirmar } = ACCIONES_SUSCRIPCION[accion];
    if (confirmar && !window.confirm(confirmar)) return;
    setEnCurso(suscripcion.id);
    setAviso(null);
    try {
      const { data } = await clienteAxios.post(`ventas/suscripciones/${suscripcion.id}/${accion}/`);
      reemplazar(data);
      const mensaje = MENSAJES_EXITO[accion];
      setAviso({ id: suscripcion.id, tipo: 'exito', texto: typeof mensaje === 'function' ? mensaje(data) : mensaje });
    } catch (error) {
      setAviso({ id: suscripcion.id, tipo: 'error', texto: error.response?.data?.detail || 'No se pudo completar la acción. Inténtalo de nuevo.' });
    } finally {
      setEnCurso(null);
    }
  };

  const cerrarEdicion = (id) => {
    setEditando(null);
    requestAnimationFrame(() => botonesCambiar.current[id]?.focus());
  };

  const sinSesion = !conSesion || estado.error === 'sesion';

  return (
    <>
      <Header />
      <main id="contenido" tabIndex={-1} className="checkout-main">
        <div className="checkout-card suscripcion">
          <span className="antetitulo">Mi cuenta</span>
          <h1 className="checkout-titulo">Mis suscripciones</h1>

          {sinSesion ? (
            <div className="suscripcion-sin-sesion">
              <p>Inicia sesión para ver y administrar tus suscripciones.</p>
              <button type="button" className="boton boton-primario" onClick={irALogin}>Iniciar sesión</button>
            </div>
          ) : estado.cargando ? (
            <Cargando texto="Cargando tus suscripciones..."><EsqueletoLista /></Cargando>
          ) : estado.error ? (
            <p role="alert" className="checkout-aviso checkout-aviso--error">{estado.error}</p>
          ) : (
            <>
              {!estado.activasEnTienda && (
                <p className="checkout-aviso checkout-aviso--advertencia">
                  La tienda pausó las suscripciones por ahora: no se crean pedidos nuevos. Puedes cancelar la tuya cuando quieras.
                </p>
              )}
              {estado.suscripciones.length === 0 ? (
                <p className="texto-secundario">
                  Todavía no tienes suscripciones.{estado.activasEnTienda && <> <Link to="/suscripcion">Ver los planes</Link></>}
                </p>
              ) : (
                <ul className="lista-sin-estilo suscripcion-mias">
                  {estado.suscripciones.map(s => {
                    // El servidor las envía como en el dominio (PAUSAR); las rutas van en minúsculas
                    const permitidas = (s.acciones || []).map(a => String(a).toLowerCase());
                    // Con un pedido esperando su pago no se puede adelantar otro (el servidor también lo rechaza)
                    const acciones = ORDEN_ACCIONES.filter(a => permitidas.includes(a)
                      && !(a === 'adelantar' && s.pedido_pendiente));
                    const ocupada = enCurso === s.id;
                    return (
                      <li key={s.id} className="suscripcion-mia">
                        <article aria-labelledby={`suscripcion-${s.id}-titulo`}>
                          <div className="suscripcion-mia-encabezado">
                            <h2 id={`suscripcion-${s.id}-titulo`} className="suscripcion-plan-nombre">{s.plan.nombre}</h2>
                            <span className={`suscripcion-estado suscripcion-estado--${s.estado.toLowerCase()}`}>{s.estado_texto}</span>
                          </div>

                          {aviso?.id === s.id && (
                            <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`checkout-aviso checkout-aviso--${aviso.tipo}`}>
                              {aviso.texto}
                            </p>
                          )}

                          {s.pedido_pendiente && s.estado !== 'CANCELADA' && (
                            <div className="checkout-aviso checkout-aviso--advertencia suscripcion-por-pagar">
                              <p>
                                Tu entrega del <strong>{fechaLarga(s.pedido_pendiente.ciclo_fecha)}</strong> está esperando su pago
                                ({formatoPesos(s.pedido_pendiente.total)}, pedido #{s.pedido_pendiente.orden_id}).
                                {s.estado === 'PENDIENTE' && ' Tu suscripción comienza cuando se confirma.'}
                              </p>
                              <Link to={`/mis-suscripciones/pagar/${s.pedido_pendiente.orden_id}`} className="boton boton-primario">
                                Pagar esta entrega
                              </Link>
                            </div>
                          )}

                          <dl className="suscripcion-datos">
                            <div><dt>Recibes</dt><dd>{s.plan.unidades} × {s.producto}</dd></div>
                            <div><dt>Frecuencia</dt><dd>{s.plan.frecuencia_texto}, {formatoPesos(s.plan.precio)} por entrega</dd></div>
                            {s.estado !== 'CANCELADA' && (
                              <div><dt>Próxima entrega</dt><dd>{s.estado === 'PAUSADA' || !s.proxima_entrega ? 'En pausa: se fija cuando la reanudes' : fechaLarga(s.proxima_entrega)}</dd></div>
                            )}
                            <div><dt>Entrega</dt><dd>{s.entrega.texto}</dd></div>
                            <div><dt>Pago</dt><dd>{nombreMedioPago(s.metodo_pago)}</dd></div>
                          </dl>

                          {editando === s.id ? (
                            <CambiarSuscripcion suscripcion={s} config={config} direcciones={direcciones} comunas={comunas}
                              alCancelar={() => cerrarEdicion(s.id)}
                              alGuardar={(data) => {
                                reemplazar(data);
                                setAviso({ id: s.id, tipo: 'exito', texto: 'Guardamos tus cambios: rigen desde tu próximo pedido.' });
                                cerrarEdicion(s.id);
                              }} />
                          ) : (acciones.length > 0 || permitidas.includes('cambiar')) && (
                            <div className="suscripcion-acciones">
                              {permitidas.includes('cambiar') && (
                                <button type="button" className="boton boton-contorno" disabled={ocupada}
                                  ref={el => { botonesCambiar.current[s.id] = el; }}
                                  onClick={() => { setAviso(null); setEditando(s.id); }}>
                                  Cambiar producto, entrega o pago
                                </button>
                              )}
                              {acciones.map(accion => (
                                <button key={accion} type="button" disabled={ocupada}
                                  className={`boton boton-contorno${accion === 'cancelar' ? ' suscripcion-boton-cancelar' : ''}`}
                                  onClick={() => ejecutar(s, accion)}>
                                  {ACCIONES_SUSCRIPCION[accion].boton}
                                </button>
                              ))}
                              {ocupada && <span role="status" className="checkout-ayuda"><Spinner /> Guardando...</span>}
                            </div>
                          )}
                        </article>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
