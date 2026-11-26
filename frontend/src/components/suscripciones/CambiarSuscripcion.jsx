import { useEffect, useState } from 'react';
import clienteAxios from '../auth/axiosConfig';
import Spinner from '../carga/Spinner';
import ElegirProducto from './ElegirProducto';
import EntregaSuscripcion from './EntregaSuscripcion';
import { useCotizacionEntrega } from '../../hooks/useCotizacionEntrega';
import { entregaDesdeSuscripcion, entregaParaServidor, faltaEnEntrega } from '../../utils/entregaSuscripcion';
import { nombreMedioPago } from '../../utils/suscripciones';

// Cambiar lo que recibe, la entrega o el medio de pago de una suscripción propia. Solo se envía lo que cambió, y rige
// desde el próximo pedido (uno ya creado conserva lo que tenía)
export default function CambiarSuscripcion({ suscripcion, config, direcciones, comunas, alGuardar, alCancelar }) {
  const prefijo = `cambiar-${suscripcion.id}`;
  const [productos, setProductos] = useState(null);
  const [eleccion, setEleccion] = useState({ producto_mongo_id: suscripcion.producto_mongo_id, variante_sku: suscripcion.variante_sku });
  const [entrega, setEntrega] = useState(() => entregaDesdeSuscripcion(suscripcion.entrega, config));
  const [entregaEditada, setEntregaEditada] = useState(false);
  const [metodoPago, setMetodoPago] = useState(suscripcion.metodo_pago);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  // Si el plan ya no se ofrece, no se puede cambiar el producto (sí la entrega y el pago)
  useEffect(() => {
    clienteAxios.get(`ventas/suscripciones/planes/${suscripcion.plan.id}/opciones/`,
      { params: { suscripcion_id: suscripcion.id } })
      .then(({ data }) => setProductos(data.productos || []))
      .catch(() => setProductos([]));
  }, [suscripcion.id, suscripcion.plan.id, suscripcion.estado]);

  const medios = config?.pasarelas_activas || [];
  const cambioProducto = eleccion.variante_sku && (eleccion.producto_mongo_id !== suscripcion.producto_mongo_id
    || eleccion.variante_sku !== suscripcion.variante_sku);
  const item = { ...eleccion, cantidad: suscripcion.plan.unidades };
  const cotizacion = useCotizacionEntrega(entregaEditada ? entrega : { ...entrega, tipo: '' }, direcciones, item);
  const faltante = entregaEditada ? faltaEnEntrega(entrega, direcciones, cotizacion) : '';
  const hayCambios = cambioProducto || entregaEditada || metodoPago !== suscripcion.metodo_pago;

  const guardar = async (e) => {
    e.preventDefault();
    if (!hayCambios || faltante) return;
    setGuardando(true);
    setError('');
    const datos = {};
    if (cambioProducto) Object.assign(datos, eleccion);
    if (entregaEditada) datos.entrega = entregaParaServidor(entrega, direcciones, cotizacion);
    if (metodoPago !== suscripcion.metodo_pago) datos.metodo_pago = metodoPago;
    try {
      const { data } = await clienteAxios.patch(`ventas/suscripciones/${suscripcion.id}/`, datos);
      alGuardar(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudieron guardar los cambios. Inténtalo de nuevo.');
      setGuardando(false);
    }
  };

  return (
    <form onSubmit={guardar} className="suscripcion-cambiar" noValidate aria-labelledby={`${prefijo}-titulo`}>
      <h3 id={`${prefijo}-titulo`} className="suscripcion-cambiar-titulo">Cambiar mi suscripción</h3>
      <p className="checkout-ayuda">Los cambios rigen desde tu próximo pedido; uno ya creado conserva lo que tenía.</p>

      <fieldset className="checkout-grupo suscripcion-cambiar-bloque">
        <legend className="checkout-paso">Qué recibes</legend>
        {productos === null ? (
          <p className="checkout-ayuda">Cargando los productos del plan...</p>
        ) : productos.length === 0 ? (
          <p className="checkout-ayuda">Este plan ya no se ofrece: puedes seguir con {suscripcion.producto}, pero no cambiarlo.</p>
        ) : (
          <ElegirProducto productos={productos} valor={eleccion} onCambiar={setEleccion}
            unidades={suscripcion.plan.unidades} prefijo={prefijo} />
        )}
      </fieldset>

      <fieldset className="checkout-grupo suscripcion-cambiar-bloque">
        <legend className="checkout-paso">Entrega</legend>
        {entregaEditada ? (
          <EntregaSuscripcion config={config} direcciones={direcciones} comunas={comunas} valor={entrega}
            onCambiar={setEntrega} cotizacion={cotizacion} envioGratis={suscripcion.plan.envio_gratis} prefijo={prefijo} />
        ) : (
          <p className="suscripcion-cambiar-actual">
            {suscripcion.entrega.texto}{' '}
            <button type="button" className="boton boton-contorno suscripcion-boton-chico" onClick={() => setEntregaEditada(true)}>
              Cambiar la entrega
            </button>
          </p>
        )}
      </fieldset>

      <fieldset className="checkout-grupo suscripcion-cambiar-bloque">
        <legend className="checkout-paso">Medio de pago</legend>
        {[...new Set([...medios, ...(medios.includes(suscripcion.metodo_pago) ? [] : [suscripcion.metodo_pago])])].map(codigo => (
          <label key={codigo} className={`checkout-opcion checkout-opcion--fila${metodoPago === codigo ? ' checkout-opcion--elegida' : ''}`}>
            <input type="radio" name={`${prefijo}-pago`} value={codigo} checked={metodoPago === codigo}
              disabled={!medios.includes(codigo)} onChange={() => setMetodoPago(codigo)} />
            <span>
              {nombreMedioPago(codigo)}
              {!medios.includes(codigo) && <span className="checkout-ayuda">La tienda ya no lo ofrece: elige otro.</span>}
            </span>
          </label>
        ))}
      </fieldset>

      {error && <p role="alert" className="checkout-aviso checkout-aviso--error">{error}</p>}
      {faltante && <p className="checkout-ayuda suscripcion-faltante">{faltante}</p>}

      <div className="suscripcion-acciones">
        <button type="submit" className="boton boton-primario" disabled={!hayCambios || Boolean(faltante) || guardando}>
          {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar cambios'}
        </button>
        <button type="button" className="boton boton-contorno" onClick={alCancelar} disabled={guardando}>Cancelar</button>
      </div>
    </form>
  );
}
