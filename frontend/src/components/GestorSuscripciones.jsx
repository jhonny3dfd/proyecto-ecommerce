import { useEffect, useRef, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';
import FormularioPlanSuscripcion from './FormularioPlanSuscripcion';
import { formatoPesos } from '../utils/suscripciones';

// Suscripciones (pedido de un cliente, opcional y apagado por defecto): el interruptor, con cuántos días de
// anticipación se crea y avisa cada pedido, y los planes que se ofrecen en /suscripcion
const DIAS_MINIMO = 1;
const DIAS_MAXIMO = 14;

const configuracionDe = (data) => ({
  suscripciones_activas: Boolean(data?.suscripciones_activas),
  suscripciones_dias_aviso: data?.suscripciones_dias_aviso ?? 3
});

function resumenPlan(plan) {
  const partes = [`${formatoPesos(plan.precio)} por entrega`, plan.frecuencia_texto,
    `${plan.unidades} ${plan.unidades === 1 ? 'unidad' : 'unidades'}`];
  if (plan.envio_gratis) partes.push(plan.envio_gratis_compras ? 'envío gratis en todo' : 'envío gratis');
  if (plan.descuento > 0) partes.push(`${plan.descuento}% en sus compras`);
  return partes.join(' · ');
}

export default function GestorSuscripciones() {
  const [config, setConfig] = useState(configuracionDe(null));
  const [planes, setPlanes] = useState([]);
  const [productos, setProductos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState({});
  const [aviso, setAviso] = useState(null);
  // null: la lista; 'nuevo' o un plan: el formulario
  const [editando, setEditando] = useState(null);
  const [ordenando, setOrdenando] = useState(false);
  const botones = useRef({});
  const nuevoPlan = useRef(null);

  useEffect(() => {
    Promise.all([
      clienteAxios.get('configuracion/negocio/'),
      clienteAxios.get('ventas/admin/suscripciones/planes/'),
      clienteAxios.get('catalogo/productos/?todos=true')
    ]).then(([configuracion, respuestaPlanes, respuestaProductos]) => {
      setConfig(configuracionDe(configuracion.data));
      setPlanes(respuestaPlanes.data?.planes || []);
      const lista = Array.isArray(respuestaProductos.data) ? respuestaProductos.data : (respuestaProductos.data?.results || []);
      setProductos(lista.map(p => ({ id: String(p.id || p._id), nombre: p.nombre, categoria: p.categoria || '' }))
        .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es')));
    }).catch(() => setAviso({ tipo: 'error', texto: 'No se pudieron cargar las suscripciones. Vuelve a abrir Configuración.' }))
      .finally(() => setCargando(false));
  }, []);

  const categorias = [...new Set(productos.map(p => p.categoria).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'es'));
  const planesActivos = planes.filter(plan => plan.activo).length;

  const guardarConfiguracion = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrores({});
    setAviso(null);
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', {
        suscripciones_activas: config.suscripciones_activas,
        suscripciones_dias_aviso: Number(config.suscripciones_dias_aviso)
      });
      setConfig(configuracionDe(data));
      await recargarConfiguracion();
      setAviso({ tipo: 'exito', texto: data.suscripciones_activas
        ? 'Suscripciones activadas: tus clientes ya ven "Suscripción" en el menú de la tienda.'
        : 'Suscripciones desactivadas: la tienda ya no muestra la página. Las suscripciones actuales quedan guardadas, pero no se crean pedidos nuevos mientras esté apagado.' });
    } catch (error) {
      const mensaje = error.response?.data?.suscripciones_dias_aviso;
      setErrores(mensaje ? { dias: [].concat(mensaje).join(' ') } : {});
      setAviso({ tipo: 'error', texto: mensaje ? 'Revisa los datos marcados.' : 'No se pudieron guardar los cambios. Inténtalo de nuevo.' });
    } finally {
      setGuardando(false);
    }
  };

  const alGuardarPlan = (guardado) => {
    const existia = planes.some(plan => plan.id === guardado.id);
    // La cantidad de suscripciones no viene al crear o editar: se conserva la que había
    setPlanes(actuales => existia
      ? actuales.map(plan => plan.id === guardado.id ? { ...guardado, suscripciones: plan.suscripciones } : plan)
      : [...actuales, { ...guardado, suscripciones: 0 }]);
    setEditando(null);
    setAviso({ tipo: 'exito', texto: existia ? `Guardaste los cambios de "${guardado.nombre}".` : `Creaste el plan "${guardado.nombre}".` });
    requestAnimationFrame(() => (botones.current[`editar:${guardado.id}`] || nuevoPlan.current)?.focus());
  };

  const cancelarFormulario = () => {
    const anterior = editando;
    setEditando(null);
    requestAnimationFrame(() => (anterior !== 'nuevo' && botones.current[`editar:${anterior.id}`] || nuevoPlan.current)?.focus());
  };

  const mover = async (indice, desplazamiento) => {
    const orden = [...planes];
    [orden[indice], orden[indice + desplazamiento]] = [orden[indice + desplazamiento], orden[indice]];
    const anterior = planes;
    setPlanes(orden);
    setOrdenando(true);
    setAviso(null);
    const plan = orden[indice + desplazamiento];
    const destino = indice + desplazamiento;
    const direccion = destino === 0 ? 1 : destino === orden.length - 1 ? -1 : desplazamiento;
    requestAnimationFrame(() => botones.current[`mover:${plan.id}:${direccion}`]?.focus());
    try {
      await clienteAxios.put('ventas/admin/suscripciones/planes/orden/', { ids: orden.map(p => p.id) });
      setAviso({ tipo: 'exito', texto: `${plan.nombre}: posición ${destino + 1} de ${orden.length}.` });
    } catch {
      setPlanes(anterior);
      setAviso({ tipo: 'error', texto: 'No se pudo cambiar el orden. Inténtalo de nuevo.' });
    } finally {
      setOrdenando(false);
    }
  };

  const borrar = async (plan) => {
    if (!window.confirm(`¿Borrar el plan "${plan.nombre}"? No se puede deshacer.`)) return;
    setAviso(null);
    try {
      await clienteAxios.delete(`ventas/admin/suscripciones/planes/${plan.id}/`);
      setPlanes(actuales => actuales.filter(p => p.id !== plan.id));
      setAviso({ tipo: 'exito', texto: `Borraste el plan "${plan.nombre}".` });
      requestAnimationFrame(() => nuevoPlan.current?.focus());
    } catch (error) {
      setAviso({ tipo: 'error', texto: error.response?.data?.detail || `No se pudo borrar el plan "${plan.nombre}".` });
    }
  };

  if (cargando) return <Cargando texto="Cargando suscripciones..."><EsqueletoFormulario campos={2} /></Cargando>;

  if (editando) {
    return (
      <FormularioPlanSuscripcion plan={editando === 'nuevo' ? null : editando} categorias={categorias}
        productos={productos} alGuardar={alGuardarPlan} alCancelar={cancelarFormulario} />
    );
  }

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Tus clientes reciben un producto cada cierto tiempo, con su cuenta. Antes de cada entrega la tienda crea el
        pedido y le envía al cliente el enlace para pagarlo; si no lo paga a tiempo, esa entrega se cancela y la
        suscripción sigue con la siguiente. Los pedidos aparecen en Ventas como cualquier otro, y los suscriptores en
        la sección Suscriptores.
      </p>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      <form onSubmit={guardarConfiguracion} className="admin-formulario">
        <div>
          <label className="admin-casilla">
            <input type="checkbox" checked={config.suscripciones_activas}
              aria-describedby="suscripciones-activas-ayuda"
              onChange={e => { setConfig(actual => ({ ...actual, suscripciones_activas: e.target.checked })); setAviso(null); }} />
            Ofrecer suscripciones en mi tienda
          </label>
          <p id="suscripciones-activas-ayuda" className="admin-ayuda admin-ayuda--sangria">
            {planesActivos === 0
              ? 'Crea al menos un plan disponible: sin planes, la página de suscripciones se muestra vacía.'
              : `Se muestran ${planesActivos === 1 ? 'el plan disponible' : `los ${planesActivos} planes disponibles`} en "Suscripción", en el menú de la tienda.`}
          </p>
        </div>

        <div className="admin-campo">
          <label htmlFor="suscripciones-dias-aviso">Días de anticipación de cada pedido</label>
          <input id="suscripciones-dias-aviso" type="number" inputMode="numeric" min={DIAS_MINIMO} max={DIAS_MAXIMO}
            step={1} value={config.suscripciones_dias_aviso}
            aria-describedby={`suscripciones-dias-aviso-ayuda${errores.dias ? ' suscripciones-dias-aviso-error' : ''}`}
            aria-invalid={errores.dias ? true : undefined}
            onChange={e => { setConfig(actual => ({ ...actual, suscripciones_dias_aviso: e.target.value })); setErrores({}); setAviso(null); }} />
          <p id="suscripciones-dias-aviso-ayuda" className="admin-ayuda">
            Cuántos días antes de cada entrega se crea el pedido y se le avisa al cliente para que pague (de {DIAS_MINIMO} a {DIAS_MAXIMO}).
            Es también el plazo para pagarlo, y la primera entrega es en ese mismo número de días desde que se suscribe.
          </p>
          {errores.dias && <p id="suscripciones-dias-aviso-error" className="admin-error-campo">{errores.dias}</p>}
        </div>

        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar suscripciones'}
          </button>
        </div>
      </form>

      <hr className="admin-separador" />

      <div className="admin-encabezado-vista">
        <h5 className="plan-lista-titulo">Planes</h5>
        <button ref={nuevoPlan} type="button" className="boton boton-primario" onClick={() => { setAviso(null); setEditando('nuevo'); }}>
          + Nuevo plan
        </button>
      </div>

      {planes.length === 0 ? (
        <p className="texto-secundario">Todavía no has creado ningún plan.</p>
      ) : (
        <ol className="lista-sin-estilo blog-admin-lista" aria-label="Planes, en el orden en que se muestran">
          {planes.map((plan, indice) => (
            <li key={plan.id} className="blog-admin-item">
              <div className="blog-admin-item-texto">
                <h6 className="blog-admin-item-titulo plan-item-titulo">{plan.nombre}</h6>
                <span className={`blog-admin-estado${plan.activo ? ' blog-admin-estado--publicada' : ''}`}>
                  {plan.activo ? 'Disponible' : 'No disponible'}
                </span>
                <p className="texto-secundario plan-resumen">{resumenPlan(plan)}</p>
                <p className="texto-secundario plan-resumen">
                  {plan.suscripciones ? `${plan.suscripciones} ${plan.suscripciones === 1 ? 'suscripción' : 'suscripciones'}` : 'Sin suscripciones'}
                </p>
              </div>
              <div className="publicacion-acciones">
                <button type="button" className="boton boton-contorno" ref={el => { botones.current[`editar:${plan.id}`] = el; }}
                  aria-label={`Editar ${plan.nombre}`} onClick={() => { setAviso(null); setEditando(plan); }}>
                  Editar
                </button>
                {[-1, 1].map(cambio => (
                  <button key={cambio} type="button" className="boton boton-contorno"
                    ref={el => { botones.current[`mover:${plan.id}:${cambio}`] = el; }}
                    aria-label={`${cambio === -1 ? 'Subir' : 'Bajar'} ${plan.nombre}`}
                    disabled={ordenando || (cambio === -1 ? indice === 0 : indice === planes.length - 1)}
                    onClick={() => mover(indice, cambio)}>
                    {cambio === -1 ? 'Subir' : 'Bajar'}
                  </button>
                ))}
                {!plan.suscripciones && (
                  <button type="button" className="boton boton-contorno" aria-label={`Borrar ${plan.nombre}`}
                    onClick={() => borrar(plan)}>
                    Borrar
                  </button>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {planes.some(plan => plan.suscripciones) && (
        <p className="admin-ayuda">
          Un plan con suscripciones no se puede borrar: desmárcalo como disponible y quienes ya están suscritos siguen igual.
        </p>
      )}
    </>
  );
}
