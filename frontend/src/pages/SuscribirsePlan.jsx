import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoFormulario } from '../components/carga/EsqueletosPanel';
import Spinner from '../components/carga/Spinner';
import ElegirProducto from '../components/suscripciones/ElegirProducto';
import EntregaSuscripcion from '../components/suscripciones/EntregaSuscripcion';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { useCotizacionEntrega } from '../hooks/useCotizacionEntrega';
import {
  ENTREGA_VACIA, costoEntrega, entregaParaServidor, faltaEnEntrega, tiposDeEntrega
} from '../utils/entregaSuscripcion';
import {
  beneficiosDelPlan, fechaEnDias, fechaLarga, formatoPesos, nombreMedioPago, textoVariante
} from '../utils/suscripciones';
import '../components/Checkout.css';
import './Suscripcion.css';

// Suscribirse a un plan (pedido de un cliente, opcional): con cuenta, se elige el producto, la entrega y el medio de
// pago, se aceptan los términos (RF-04.4) y se paga el primer pedido. El servidor fija el precio y las fechas
export default function SuscribirsePlan() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const config = useConfiguracionTienda();
  const conSesion = Boolean(localStorage.getItem('access_token'));

  const [carga, setCarga] = useState({ listo: false, plan: null, productos: [], diasAviso: 3, error: '' });
  const [direcciones, setDirecciones] = useState([]);
  const [comunas, setComunas] = useState([]);
  const [paginasLegales, setPaginasLegales] = useState([]);
  const [eleccion, setEleccion] = useState({ producto_mongo_id: '', variante_sku: '' });
  const [entrega, setEntrega] = useState(ENTREGA_VACIA);
  const [metodoPago, setMetodoPago] = useState('');
  const [aceptaTerminos, setAceptaTerminos] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let vigente = true;
    Promise.all([
      clienteAxios.get('ventas/suscripciones/planes/'),
      clienteAxios.get(`ventas/suscripciones/planes/${planId}/opciones/`)
    ]).then(([planes, opciones]) => {
      if (!vigente) return;
      const plan = (planes.data.planes || []).find(p => String(p.id) === String(planId)) || null;
      setCarga({ listo: true, plan, productos: opciones.data.productos || [], diasAviso: planes.data.dias_aviso ?? 3,
        error: plan ? '' : 'Este plan ya no está disponible.' });
    }).catch(err => {
      if (vigente) setCarga({ listo: true, plan: null, productos: [], diasAviso: 3,
        error: err.response?.status === 404 ? 'Este plan ya no está disponible.' : 'No se pudo cargar el plan. Inténtalo de nuevo.' });
    });
    return () => { vigente = false; };
  }, [planId]);

  // Con sesión: sus direcciones y quién recibe, como en el checkout
  useEffect(() => {
    if (!conSesion) return;
    clienteAxios.get('ventas/direcciones/')
      .then(({ data }) => {
        const lista = Array.isArray(data) ? data : [];
        setDirecciones(lista);
        const predeterminada = lista.find(d => d.es_predeterminado) || lista[0];
        if (predeterminada) setEntrega(actual => ({ ...actual, direccionId: predeterminada.id }));
      })
      .catch(() => setDirecciones([]));
    clienteAxios.get('usuarios/me/')
      .then(({ data }) => {
        const nombre = (data.nombre || '').trim();
        const apellido = (data.apellido_paterno || '').trim();
        const completo = !apellido || nombre.toLowerCase().includes(apellido.toLowerCase()) ? nombre : `${nombre} ${apellido}`;
        setEntrega(actual => ({ ...actual, nombre: actual.nombre || completo, telefono: actual.telefono || data.telefono || '' }));
      })
      .catch(() => {});
    clienteAxios.get('ventas/paginas-legales/')
      .then(({ data }) => setPaginasLegales((data || []).map(p => p.tipo_pagina)))
      .catch(() => setPaginasLegales([]));
  }, [conSesion]);

  const hayCouriers = (config?.couriers || []).length > 0;
  useEffect(() => {
    if (!hayCouriers || !conSesion) return;
    clienteAxios.get('ventas/logistica/comunas/')
      .then(({ data }) => setComunas(data.comunas || []))
      .catch(() => setComunas([]));
  }, [hayCouriers, conSesion]);

  // Sin elegir, la primera forma de entrega y el primer medio de pago que ofrece la tienda
  const tipos = tiposDeEntrega(config);
  const entregaVigente = entrega.tipo || !tipos.length ? entrega : { ...entrega, tipo: tipos[0] };
  const medios = config?.pasarelas_activas || [];
  const medio = medios.includes(metodoPago) ? metodoPago : (medios[0] || '');

  const { plan, productos } = carga;
  const item = eleccion.variante_sku ? { ...eleccion, cantidad: plan?.unidades || 1 } : null;
  const cotizacion = useCotizacionEntrega(entregaVigente, direcciones, item);
  const despacho = plan?.envio_gratis ? 0 : costoEntrega(entregaVigente, config, cotizacion);
  const total = plan && despacho !== null ? plan.precio + despacho : null;

  const producto = productos.find(p => p.id === eleccion.producto_mongo_id);
  const variante = producto?.variantes.find(v => v.sku === eleccion.variante_sku);
  const faltante = !eleccion.variante_sku ? 'Elige qué quieres recibir.'
    : faltaEnEntrega(entregaVigente, direcciones, cotizacion)
    || (!medio ? 'La tienda no tiene medios de pago disponibles.' : '')
    || (!aceptaTerminos ? 'Acepta los Términos y Condiciones y la Política de Privacidad.' : '');

  const irALogin = () => {
    localStorage.setItem('url_anterior_login', window.location.pathname);
    navigate('/login');
  };

  const suscribirse = async (e) => {
    e.preventDefault();
    if (faltante || enviando) return;
    setEnviando(true);
    setError('');
    try {
      const { data } = await clienteAxios.post('ventas/suscripciones/', {
        plan_id: plan.id, ...eleccion, ...entregaParaServidor(entregaVigente, direcciones, cotizacion),
        metodo_pago: medio, acepta_terminos: aceptaTerminos
      });
      if (data.url_pago) {
        window.location.assign(data.url_pago);
        return;
      }
      navigate(`/pedido-recibido?orden=${encodeURIComponent(data.orden_id)}`, {
        replace: true, state: { instrucciones: data.instrucciones_pago || null }
      });
    } catch (err) {
      if (err.response?.status === 401) {
        irALogin();
        return;
      }
      setError(err.response?.data?.detail || 'No se pudo crear la suscripción. Inténtalo de nuevo.');
      setEnviando(false);
    }
  };

  const enlaceLegal = (tipo, texto) => paginasLegales.includes(tipo) ? (
    <a href={`/legal/${tipo.toLowerCase()}`} target="_blank" rel="noopener noreferrer" aria-label={`${texto} (se abre en otra pestaña)`}>
      {texto}
    </a>
  ) : texto;

  const primeraEntrega = fechaEnDias(carga.diasAviso);

  return (
    <>
      <Header />
      <main id="contenido" tabIndex={-1} className="checkout-main">
        <div className="checkout-card suscripcion">
          <Link to="/suscripcion" className="suscripcion-volver"><span aria-hidden="true">←</span> Todos los planes</Link>
          <span className="antetitulo">Suscripción</span>
          <h1 className="checkout-titulo">{plan ? plan.nombre : 'Suscribirme'}</h1>

          {!carga.listo || (conSesion && !config) ? (
            <Cargando texto="Cargando el plan..."><EsqueletoFormulario campos={3} /></Cargando>
          ) : carga.error ? (
            <p className="checkout-aviso checkout-aviso--advertencia">
              {carga.error} <Link to="/suscripcion">Ver los planes</Link>
            </p>
          ) : !conSesion ? (
            <div className="suscripcion-sin-sesion">
              <p>
                {formatoPesos(plan.precio)} por entrega, {plan.frecuencia_texto.toLowerCase()}. Para suscribirte necesitas una
                cuenta: así recibes los avisos de cada entrega y la administras desde Mis suscripciones.
              </p>
              <button type="button" className="boton boton-primario" onClick={irALogin}>Iniciar sesión o crear cuenta</button>
            </div>
          ) : (
            <form onSubmit={suscribirse} className="checkout-columnas" noValidate>
              <div>
                <section className="checkout-seccion" aria-labelledby="suscribirse-paso-producto">
                  <h2 id="suscribirse-paso-producto" className="checkout-paso">1. Qué quieres recibir</h2>
                  <ElegirProducto productos={productos} valor={eleccion} onCambiar={setEleccion} unidades={plan.unidades} prefijo="suscribirse" />
                </section>

                <section className="checkout-seccion" aria-labelledby="suscribirse-paso-entrega">
                  <h2 id="suscribirse-paso-entrega" className="checkout-paso">2. Cómo la recibes</h2>
                  <EntregaSuscripcion config={config} direcciones={direcciones} comunas={comunas} valor={entregaVigente}
                    onCambiar={setEntrega} cotizacion={cotizacion} envioGratis={plan.envio_gratis} prefijo="suscribirse" />
                </section>

                <section className="checkout-seccion" aria-labelledby="suscribirse-paso-pago">
                  <h2 id="suscribirse-paso-pago" className="checkout-paso">3. Cómo pagas cada entrega</h2>
                  {medios.length === 0 ? (
                    <p className="checkout-aviso checkout-aviso--advertencia">La tienda no tiene medios de pago disponibles por ahora.</p>
                  ) : (
                    <fieldset className="checkout-grupo">
                      <legend className="checkout-solo-lector">Medio de pago</legend>
                      {medios.map(codigo => (
                        <label key={codigo} className={`checkout-opcion checkout-opcion--fila${medio === codigo ? ' checkout-opcion--elegida' : ''}`}>
                          <input type="radio" name="suscribirse-pago" value={codigo} checked={medio === codigo} onChange={() => setMetodoPago(codigo)} />
                          <span>{nombreMedioPago(codigo)}</span>
                        </label>
                      ))}
                    </fieldset>
                  )}
                  <p className="checkout-ayuda">
                    {medio === 'TRANSFERENCIA'
                      ? 'Antes de cada entrega te enviamos los datos para transferir; la tienda la prepara cuando confirma tu pago.'
                      : 'Antes de cada entrega te enviamos un enlace para pagarla. Ahora pagas la primera.'}
                  </p>
                </section>
              </div>

              <aside className="checkout-resumen" aria-labelledby="suscribirse-resumen">
                <h2 id="suscribirse-resumen" className="checkout-paso">Resumen</h2>
                <div className="checkout-resumen-lineas">
                  <div className="checkout-resumen-linea">
                    <span>{plan.nombre}</span>
                    <span>{plan.frecuencia_texto}</span>
                  </div>
                  {producto && (
                    <div className="checkout-resumen-linea">
                      <span>
                        {plan.unidades} × {producto.nombre}
                        {variante && textoVariante(variante.atributos) ? ` (${textoVariante(variante.atributos)})` : ''}
                      </span>
                    </div>
                  )}
                </div>
                <div className="checkout-totales">
                  <div className="checkout-total-linea"><span>Precio por entrega</span><span>{formatoPesos(plan.precio)}</span></div>
                  <div className={`checkout-total-linea${plan.envio_gratis ? ' checkout-envio-gratis' : ''}`}>
                    <span>Despacho</span>
                    <span>{plan.envio_gratis ? 'Gratis con tu plan' : despacho === null ? 'Por calcular' : formatoPesos(despacho)}</span>
                  </div>
                  <div className="checkout-total-linea checkout-total-linea--final">
                    <span>Primera entrega</span>
                    <span>{total === null ? '—' : formatoPesos(total)}</span>
                  </div>
                </div>
                <p className="checkout-ayuda suscripcion-fecha">
                  Llega aproximadamente el <strong>{fechaLarga(primeraEntrega)}</strong> y después {plan.frecuencia_texto.toLowerCase()}.
                </p>
                {beneficiosDelPlan({ ...plan, beneficios: [] }).length > 0 && (
                  <ul className="suscripcion-plan-beneficios suscripcion-resumen-beneficios">
                    {beneficiosDelPlan({ ...plan, beneficios: [] }).map(b => <li key={b}>{b}</li>)}
                  </ul>
                )}

                <div className="checkout-terminos">
                  <label className="checkout-casilla">
                    <input type="checkbox" checked={aceptaTerminos} onChange={e => setAceptaTerminos(e.target.checked)} />
                    <span>
                      Acepto los {enlaceLegal('TERMINOS', 'Términos y Condiciones')} y la {enlaceLegal('PRIVACIDAD', 'Política de Privacidad')}, y
                      que la suscripción sigue hasta que la cancele.
                    </span>
                  </label>
                </div>

                {error && <p role="alert" className="checkout-aviso checkout-aviso--error">{error}</p>}
                {faltante && <p className="checkout-ayuda suscripcion-faltante" id="suscribirse-faltante">{faltante}</p>}

                <button type="submit" className="boton boton-primario checkout-pagar" disabled={Boolean(faltante) || enviando}
                  aria-describedby={faltante ? 'suscribirse-faltante' : undefined}>
                  {enviando && <Spinner />}
                  {enviando ? 'Procesando...' : total === null ? 'Suscribirme y pagar' : `Suscribirme y pagar ${formatoPesos(total)}`}
                </button>
              </aside>
            </form>
          )}
        </div>
      </main>
    </>
  );
}
