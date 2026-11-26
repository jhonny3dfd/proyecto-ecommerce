import { formatoPesos } from '../../utils/suscripciones';
import { NOMBRES_TIPO_ENTREGA, tiposDeEntrega } from '../../utils/entregaSuscripcion';

// Cómo recibe el cliente sus entregas (RF-02.3): a domicilio con los couriers activos, retiro en el local o entrega
// coordinada, según lo que ofrece la tienda. `cotizacion` viene de useCotizacionEntrega.
export default function EntregaSuscripcion({ config, direcciones, comunas, valor, onCambiar, cotizacion, envioGratis,
  prefijo = 'entrega' }) {
  const tipos = tiposDeEntrega(config);
  const cambiar = (cambios) => onCambiar({ ...valor, ...cambios });
  const cambiarDireccion = (campo, texto) => cambiar({ direccion: { ...valor.direccion, [campo]: texto } });
  const conDireccion = valor.tipo === 'DOMICILIO' || valor.tipo === 'ENTREGA_COORDINADA';
  const opcional = valor.tipo === 'ENTREGA_COORDINADA';
  const hayCouriers = (config?.couriers || []).length > 0;
  const precio = (monto) => (envioGratis ? 'Gratis con tu plan' : formatoPesos(monto));

  if (tipos.length === 0) {
    return <p className="checkout-aviso checkout-aviso--advertencia">La tienda no tiene formas de entrega disponibles por ahora.</p>;
  }

  return (
    <>
      <fieldset className="checkout-grupo checkout-opciones">
        <legend className="checkout-etiqueta">Forma de entrega</legend>
        <div className="checkout-fila suscripcion-tipos-entrega">
          {tipos.map(tipo => (
            <label key={tipo} className={`checkout-opcion${valor.tipo === tipo ? ' checkout-opcion--elegida' : ''}`}>
              <input type="radio" name={`${prefijo}-tipo`} value={tipo} checked={valor.tipo === tipo}
                onChange={() => cambiar({ tipo })} className="checkout-radio-oculto" />
              {NOMBRES_TIPO_ENTREGA[tipo]}
            </label>
          ))}
        </div>
      </fieldset>

      {valor.tipo === 'RETIRO_LOCAL' && (
        <p className="checkout-ayuda suscripcion-entrega-nota">
          Retiras cada entrega en {[config?.calle_origen, config?.numero_origen].filter(Boolean).join(' ') || 'el local'}
          {config?.comuna_origen ? `, ${config.comuna_origen}` : ''}. Sin costo de despacho.
        </p>
      )}

      {opcional && (
        <p className="checkout-ayuda suscripcion-entrega-nota">
          {config?.instrucciones_entrega_coordinada?.trim() || 'La tienda te contactará para acordar el día y la hora de cada entrega.'}
          {' '}La dirección es opcional: si prefieres, déjala en blanco y la acuerdas con la tienda.
        </p>
      )}

      {conDireccion && (
        <>
          {direcciones.length > 0 && (
            <fieldset className="checkout-grupo checkout-direcciones">
              <legend className="checkout-etiqueta">Dirección</legend>
              {direcciones.map(d => (
                <label key={d.id} className={`checkout-opcion checkout-opcion--fila${valor.direccionId === d.id ? ' checkout-opcion--elegida' : ''}`}>
                  <input type="radio" name={`${prefijo}-direccion`} value={d.id} checked={valor.direccionId === d.id}
                    onChange={() => cambiar({ direccionId: d.id })} />
                  <span>
                    <strong>{d.calle} {d.calle_numero}{d.dpto_casa ? ` - ${d.dpto_casa}` : ''}</strong>
                    <span className="checkout-ayuda">{[d.comuna, d.ciudad].filter(Boolean).join(', ')}</span>
                  </span>
                </label>
              ))}
              <label className={`checkout-opcion checkout-opcion--fila${valor.direccionId === 'nueva' ? ' checkout-opcion--elegida' : ''}`}>
                <input type="radio" name={`${prefijo}-direccion`} value="nueva" checked={valor.direccionId === 'nueva'}
                  onChange={() => cambiar({ direccionId: 'nueva' })} />
                <span><strong>Otra dirección</strong></span>
              </label>
            </fieldset>
          )}

          {valor.direccionId === 'nueva' && (
            <div className="checkout-direccion-nueva">
              <div className="checkout-fila">
                <div className="checkout-campo checkout-campo--ancho">
                  <label htmlFor={`${prefijo}-calle`}>Calle</label>
                  <input id={`${prefijo}-calle`} type="text" maxLength={255} autoComplete="address-line1" required={!opcional}
                    value={valor.direccion.calle} onChange={e => cambiarDireccion('calle', e.target.value)} />
                </div>
                <div className="checkout-campo">
                  <label htmlFor={`${prefijo}-numero`}>Número</label>
                  <input id={`${prefijo}-numero`} type="text" maxLength={50} required={!opcional}
                    value={valor.direccion.numero} onChange={e => cambiarDireccion('numero', e.target.value)} />
                </div>
              </div>
              <div className="checkout-campo">
                <label htmlFor={`${prefijo}-dpto`}>Dpto, casa o referencia (opcional)</label>
                <input id={`${prefijo}-dpto`} type="text" maxLength={100} autoComplete="address-line2"
                  value={valor.direccion.dpto_casa} onChange={e => cambiarDireccion('dpto_casa', e.target.value)} />
              </div>
              <div className="checkout-fila">
                <div className="checkout-campo">
                  <label htmlFor={`${prefijo}-comuna`}>Comuna</label>
                  {valor.tipo === 'DOMICILIO' && hayCouriers ? (
                    <select id={`${prefijo}-comuna`} required value={valor.direccion.comuna}
                      onChange={e => cambiarDireccion('comuna', e.target.value)}>
                      <option value="">{comunas.length ? '-- Selecciona --' : 'Cargando...'}</option>
                      {/* Una comuna guardada que ya no tiene cobertura se muestra igual, para que se vea qué había */}
                      {valor.direccion.comuna && !comunas.includes(valor.direccion.comuna) && (
                        <option value={valor.direccion.comuna}>{valor.direccion.comuna}</option>
                      )}
                      {comunas.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  ) : (
                    <input id={`${prefijo}-comuna`} type="text" maxLength={100} autoComplete="address-level2"
                      required={!opcional} value={valor.direccion.comuna} onChange={e => cambiarDireccion('comuna', e.target.value)} />
                  )}
                </div>
                <div className="checkout-campo">
                  <label htmlFor={`${prefijo}-ciudad`}>Ciudad (opcional)</label>
                  <input id={`${prefijo}-ciudad`} type="text" maxLength={100}
                    value={valor.direccion.ciudad} onChange={e => cambiarDireccion('ciudad', e.target.value)} />
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {valor.tipo === 'DOMICILIO' && (
        <div className="suscripcion-cotizacion" aria-live="polite">
          {cotizacion.cargando && <p className="checkout-ayuda">Calculando el despacho...</p>}
          {!cotizacion.cargando && cotizacion.error && <p className="checkout-error-campo">{cotizacion.error}</p>}
          {cotizacion.opciones.length > 1 ? (
            <fieldset className="checkout-grupo">
              <legend className="checkout-etiqueta">Despacho de cada entrega</legend>
              {cotizacion.opciones.map(o => (
                <label key={o.proveedor} className={`checkout-opcion checkout-opcion--fila${cotizacion.opcion?.proveedor === o.proveedor ? ' checkout-opcion--elegida' : ''}`}>
                  <input type="radio" name={`${prefijo}-courier`} value={o.proveedor}
                    checked={cotizacion.opcion?.proveedor === o.proveedor} onChange={() => cambiar({ proveedor: o.proveedor })} />
                  <span>{o.nombre}</span>
                  <span className="checkout-opcion-precio">{precio(o.precio)}</span>
                </label>
              ))}
            </fieldset>
          ) : cotizacion.opcion && (
            <p className="checkout-ayuda">Despacho de cada entrega: {cotizacion.opcion.nombre}, {precio(cotizacion.opcion.precio)}.</p>
          )}
        </div>
      )}

      <div className="checkout-fila">
        <div className="checkout-campo">
          <label htmlFor={`${prefijo}-nombre`}>Nombre de quien recibe</label>
          <input id={`${prefijo}-nombre`} type="text" maxLength={120} autoComplete="name" required
            value={valor.nombre} onChange={e => cambiar({ nombre: e.target.value })} />
        </div>
        <div className="checkout-campo">
          <label htmlFor={`${prefijo}-telefono`}>Teléfono</label>
          <input id={`${prefijo}-telefono`} type="tel" maxLength={30} autoComplete="tel" required placeholder="+56 9 1234 5678"
            value={valor.telefono} onChange={e => cambiar({ telefono: e.target.value })} />
        </div>
      </div>
    </>
  );
}
