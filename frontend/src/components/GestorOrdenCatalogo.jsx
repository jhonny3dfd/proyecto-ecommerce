import { useEffect, useRef, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';

export default function GestorOrdenCatalogo() {
  const [config, setConfig] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const botones = useRef({});
  useEffect(() => {
    Promise.all([clienteAxios.get('configuracion/negocio/'), clienteAxios.get('catalogo/productos/?todos=true')])
      .then(([{ data }, productos]) => {
        setConfig({ orden_catalogo: data.orden_catalogo || 'destacados', orden_categorias: data.orden_categorias || [] });
        setCategorias([...new Set(productos.data.filter(p => p.activo !== false).map(p => p.categoria).filter(Boolean))].sort());
      }).catch(() => setError('No se pudo cargar la configuración del catálogo. Vuelve a abrir Configuración.'));
  }, []);
  const prioridades = config?.orden_categorias || [];
  const visibles = prioridades.filter(categoria => categorias.includes(categoria));
  const lista = [...visibles, ...categorias.filter(categoria => !visibles.includes(categoria))];
  const mover = (categoria, desplazamiento) => {
    const orden = [...lista];
    const indice = orden.indexOf(categoria);
    [orden[indice], orden[indice + desplazamiento]] = [orden[indice + desplazamiento], orden[indice]];
    let finPrioridades = orden.length;
    for (let inicio = 0; inicio < orden.length; inicio++) {
      const resto = orden.slice(inicio);
      const alfabetico = [...resto].sort();
      if (resto.every((nombre, i) => nombre === alfabetico[i])) {
        finPrioridades = inicio;
        break;
      }
    }
    setConfig(actual => ({ ...actual, orden_categorias: [...orden.slice(0, finPrioridades), ...prioridades.filter(c => !categorias.includes(c))] }));
    setAviso(`${categoria}: posición ${indice + desplazamiento + 1} de ${lista.length}.`);
    setError('');
    const direccion = indice + desplazamiento === 0 ? 1 : indice + desplazamiento === lista.length - 1 ? -1 : desplazamiento;
    requestAnimationFrame(() => botones.current[`${categoria}:${direccion}`]?.focus());
  };
  const guardar = async event => {
    event.preventDefault(); setGuardando(true); setError(''); setAviso('');
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', config);
      setConfig({ orden_catalogo: data.orden_catalogo, orden_categorias: data.orden_categorias });
      try { await recargarConfiguracion(); setAviso('Orden del catálogo y categorías guardado.'); }
      catch { setAviso('Configuración guardada. Recarga la tienda para ver los cambios.'); }
    } catch (fallo) {
      const datos = fallo.response?.data;
      setError(datos ? Object.values(datos).flat().join(' ') : 'No se pudo guardar. Inténtalo de nuevo.');
    } finally { setGuardando(false); }
  };
  return <>
    <p className="texto-secundario">Las categorías priorizadas aparecen primero; las demás, al final en orden alfabético. Incluye categorías de borradores activos. El comprador conserva su selector de orden.</p>
    {error && <p role="alert">{error}</p>}
    <p role="status">{aviso}</p>
    {!config ? !error && <p>Cargando configuración...</p> : <form onSubmit={guardar} className="admin-formulario">
      <fieldset disabled={guardando} className="orden-catalogo-campos">
        <legend>Preferencias del catálogo</legend>
        <div className="admin-campo">
          <label htmlFor="orden-catalogo-inicial">Orden inicial del catálogo</label>
          <select id="orden-catalogo-inicial" aria-describedby="orden-catalogo-ayuda" value={config.orden_catalogo} onChange={e => { setConfig({ ...config, orden_catalogo: e.target.value }); setAviso(''); }}>
            <option value="destacados">Por categorías priorizadas</option><option value="recientes">Recientes primero</option>
            <option value="precio-desc">Mayor precio</option><option value="precio-asc">Menor precio</option>
          </select>
          <p id="orden-catalogo-ayuda" className="texto-secundario">
            Por categorías priorizadas: primero las categorías priorizadas, agrupando sus productos; dentro de cada categoría, los más recientes primero.
            Sin categorías priorizadas, se muestran los productos más recientes.
            Recientes primero: productos más nuevos globalmente, sin agruparlos por categoría.
          </p>
        </div>
        <ol className="orden-catalogo-lista">{lista.map((categoria, indice) => <li key={categoria}>
          <span>{categoria} <small>({prioridades.includes(categoria) ? 'Priorizada' : 'Alfabética'})</small></span>
          <div className="orden-catalogo-acciones">{[-1, 1].map(cambio => <button key={cambio} type="button" className="boton boton-secundario"
            ref={elemento => { botones.current[`${categoria}:${cambio}`] = elemento; }}
            aria-label={`${cambio === -1 ? 'Subir' : 'Bajar'} ${categoria}`}
            disabled={cambio === -1 ? indice === 0 : indice === lista.length - 1} onClick={() => mover(categoria, cambio)}>{cambio === -1 ? 'Subir' : 'Bajar'}</button>)}</div>
        </li>)}</ol>
        {!lista.length && <p>No hay categorías de productos activos.</p>}
        <div className="orden-catalogo-acciones">
          <button className="boton boton-primario" type="submit">{guardando ? 'Guardando...' : 'Guardar orden'}</button>
          <button className="boton boton-secundario" type="button" onClick={() => { setConfig({ orden_catalogo: 'destacados', orden_categorias: [] }); setError(''); setAviso('Valores predeterminados preparados. Guarda para publicarlos.'); }}>Restablecer valores predeterminados</button>
        </div>
      </fieldset>
    </form>}
  </>;
}
