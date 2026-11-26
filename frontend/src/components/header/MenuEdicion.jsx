import { useRef, useState } from 'react';
import { CampoEditable } from '../landing/ControlesEdicion';
import { resolverMenu } from '../../utils/menuPrincipal';

export default function MenuEdicion({ configuracion, edicion }) {
  const [aviso, setAviso] = useState('');
  const botones = useRef({});
  const menu = configuracion.menu_principal || {};
  const todos = resolverMenu(configuracion);
  const enlaces = todos.filter(enlace => enlace.visible);
  const mover = (id, cambio) => {
    const orden = todos.map(enlace => enlace.id);
    const indice = enlaces.findIndex(enlace => enlace.id === id);
    const posicion = orden.indexOf(id);
    const destino = orden.indexOf(enlaces[indice + cambio].id);
    [orden[posicion], orden[destino]] = [orden[destino], orden[posicion]];
    edicion.cambiarMenu({ ...menu, orden });
    setAviso(`${enlaces[indice].nombre}: posición ${indice + cambio + 1} de ${enlaces.length}.`);
    const direccion = indice + cambio === 0 ? 1 : indice + cambio === enlaces.length - 1 ? -1 : cambio;
    requestAnimationFrame(() => botones.current[`${id}:${direccion}`]?.focus());
  };
  return <>
    <span role="status" className="visualmente-oculto">{aviso}</span>
    {enlaces.map((enlace, indice) => {
      return <div key={enlace.id} className="menu-edicion-item">
        {enlace.id === 'catalogo' ? (
          <CampoEditable campo="catalogo" definicion={{ etiqueta: 'Nombre de Catálogo', maximo: 20 }}
            className="menu-edicion-nombre" deshabilitado={edicion.guardando} edicion={{
              textos: { catalogo: menu.nombres?.catalogo ?? enlace.nombre },
              errores: { catalogo: edicion.errores.menu_principal },
              cambiarTexto: (_, valor) => edicion.cambiarMenu({ ...menu, nombres: { ...menu.nombres, catalogo: valor } }),
            }} />
        ) : <span className="menu-edicion-texto">{enlace.nombre}</span>}
        <div className="menu-edicion-movimientos">
          {[-1, 1].map(cambio => <button key={cambio} type="button"
            ref={elemento => { botones.current[`${enlace.id}:${cambio}`] = elemento; }}
            aria-label={`Mover ${enlace.nombre} a la ${cambio === -1 ? 'izquierda' : 'derecha'}`}
            disabled={edicion.guardando || (cambio === -1 ? indice === 0 : indice === enlaces.length - 1)}
            onClick={() => mover(enlace.id, cambio)}>{cambio === -1 ? '←' : '→'}</button>)}
        </div>
      </div>;
    })}
  </>;
}
