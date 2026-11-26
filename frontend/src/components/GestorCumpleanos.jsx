import { useEffect, useId, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { MESES, fechaLarga } from '../utils/suscripciones';

function direccionCompleta(fila) {
  const direccion = fila.direccion_envio || {};
  return [direccion.calle, direccion.numero, direccion.dpto_casa, direccion.comuna, direccion.ciudad,
    direccion.region, direccion.referencia].filter(Boolean).join(', ') || fila.direccion;
}

export default function GestorCumpleanos() {
  const id = useId();
  const [filtro, setFiltro] = useState({ mes: new Date().getMonth() + 1, pagina: 1 });
  const [carga, setCarga] = useState(null);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [guardando, setGuardando] = useState(null);
  useEffect(() => {
    let vigente = true;
    clienteAxios.get('ventas/admin/suscripciones/cumpleanos/', { params: filtro })
      .then(({ data }) => { if (vigente) { setCarga({ filtro, datos: data }); setError(''); } })
      .catch(() => { if (vigente) { setCarga({ filtro, datos: null }); setError('No se pudieron cargar los cumpleaños.'); } });
    return () => { vigente = false; };
  }, [filtro]);
  const cargando = carga?.filtro !== filtro;
  const datos = !cargando ? carga?.datos : null;

  async function marcar(fila) {
    setGuardando(fila.usuario_id); setError(''); setAviso('');
    try {
      await clienteAxios.post(`ventas/admin/suscripciones/cumpleanos/${fila.usuario_id}/regalo/`);
      setCarga(actual => ({ ...actual, datos: { ...actual.datos, results: actual.datos.results.map(persona =>
        persona.usuario_id === fila.usuario_id ? { ...persona, regalo_enviado: true } : persona) } }));
      setAviso(`Regalo de ${fila.nombre} registrado como enviado.`);
    } catch { setError('No se pudo registrar el regalo. Comprueba que la suscripción siga vigente e inténtalo nuevamente.'); }
    finally { setGuardando(null); }
  }

  return <>
    <p className="texto-secundario admin-descripcion">Solo se muestran las personas con suscripciones vigentes.
      Cada persona recibe un único registro de regalo por año, aunque tenga varios planes. La dirección corresponde a su entrega más próxima.</p>
    <div className="admin-campo"><label htmlFor={`${id}-mes`}>Mes de cumpleaños</label>
      <select id={`${id}-mes`} value={filtro.mes} disabled={guardando !== null}
        onChange={e => { setFiltro({ mes: Number(e.target.value), pagina: 1 }); setAviso(''); }}>
        {MESES.map((mes, i) => <option key={mes} value={i + 1}>{mes}</option>)}
      </select></div>
    {cargando && <p role="status">Cargando cumpleaños…</p>}
    {error && <p role="alert">{error}{' '}
      <button type="button" className="boton-texto" onClick={() => setFiltro(f => ({ ...f }))}>Actualizar listado</button></p>}
    {aviso && <p role="status">{aviso}</p>}
    {datos && <>
      <p role="status">{datos.count} cumpleaños en {MESES[filtro.mes - 1]} de {datos.anio}.</p>
      {datos.results.length === 0 && <p>No hay suscriptores vigentes con cumpleaños registrado en este mes.</p>}
      <ul className="cumpleanos-lista lista-sin-estilo">
        {datos.results.map(fila => <li key={fila.usuario_id} className="plan-item">
          <h3>{fila.nombre}</h3><p>Cumpleaños: {fila.dia} de {MESES[fila.mes - 1]}</p>
          <dl><dt>Próxima entrega</dt><dd>{fechaLarga(fila.proxima_entrega) || 'Sin fecha programada'}</dd>
            <dt>Dirección o forma de entrega</dt><dd>{direccionCompleta(fila)}</dd>
            {fila.destinatario && <><dt>Recibe</dt><dd>{fila.destinatario}</dd></>}
            <dt>Plan de esa entrega</dt><dd>{fila.plan}</dd></dl>
          <label className="cumpleanos-regalo"><input type="checkbox" checked={fila.regalo_enviado}
            disabled={guardando !== null || fila.regalo_enviado} onChange={() => marcar(fila)}
            aria-label={`Regalo enviado a ${fila.nombre} en ${datos.anio}`} /> Regalo enviado en {datos.anio}</label>
        </li>)}
      </ul>
      {datos.count > 20 && <nav aria-label="Paginación de cumpleaños" className="catalogo-paginacion">
        <button type="button" disabled={filtro.pagina <= 1 || guardando !== null}
          onClick={() => setFiltro(f => ({ ...f, pagina: f.pagina - 1 }))}>Anterior</button>
        <span>Página {filtro.pagina}</span>
        <button type="button" disabled={!datos.next || guardando !== null}
          onClick={() => setFiltro(f => ({ ...f, pagina: f.pagina + 1 }))}>Siguiente</button>
      </nav>}
    </>}
  </>;
}
