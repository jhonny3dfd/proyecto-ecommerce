import { useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import useConfiguracionTienda, { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// RF-01.4: cómo se muestran los productos en el catálogo público. Los valores son los del backend
// (TIPOS_LAYOUT en ventas/models.py) y los que aplica pages/Catalogo.jsx
const VISTAS_CATALOGO = [
  { id: 'GRID_3', nombre: 'Cuadrícula de 3', descripcion: 'Tres productos por fila, con fotos grandes.', columnas: 3 },
  { id: 'GRID_4', nombre: 'Cuadrícula de 4', descripcion: 'Cuatro por fila: se ven más productos a la vez.', columnas: 4 },
  { id: 'LISTA', nombre: 'Lista con descripción', descripcion: 'Uno debajo del otro, con la descripción al costado.' },
];
const VISTA_PREDETERMINADA = 'GRID_3';

export default function VistaCatalogoSelector() {
  const configuracion = useConfiguracionTienda();
  const guardada = VISTAS_CATALOGO.some(({ id }) => id === configuracion?.layout_catalogo)
    ? configuracion.layout_catalogo : VISTA_PREDETERMINADA;
  // null = sin elegir todavía: se muestra la guardada
  const [elegida, setElegida] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const seleccionada = elegida ?? guardada;

  const elegir = (id) => {
    setElegida(id);
    setAviso(null);
  };

  const guardar = async () => {
    setGuardando(true);
    setAviso(null);
    try {
      await clienteAxios.patch('configuracion/negocio/', { layout_catalogo: seleccionada });
      await recargarConfiguracion();
      setElegida(null);
      setAviso({ tipo: 'exito', texto: 'Vista guardada: el catálogo ya muestra tus productos así.' });
    } catch (error) {
      console.error('Error al guardar la vista del catálogo:', error);
      setAviso({ tipo: 'error', texto: 'No se pudo guardar la vista del catálogo. Inténtalo de nuevo.' });
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="selector-vistas-catalogo">
      <p className="texto-secundario admin-descripcion">
        Elige cómo se ordenan los productos en la página del catálogo. Se publica cuando la guardas.
      </p>

      <div className="selector-paletas-opciones" role="group" aria-label="Vistas del catálogo">
        {VISTAS_CATALOGO.map((vista) => (
          <button
            key={vista.id}
            type="button"
            aria-pressed={seleccionada === vista.id}
            onClick={() => elegir(vista.id)}
            className="selector-paleta selector-vista-catalogo"
          >
            {/* Esquema de la vista: cuadros por fila, o filas con la foto a un lado y el texto al otro */}
            <span className={`selector-vista-esquema${vista.columnas ? '' : ' selector-vista-esquema--lista'}`}
              style={vista.columnas ? { gridTemplateColumns: `repeat(${vista.columnas}, 1fr)` } : undefined}
              aria-hidden="true">
              {Array.from({ length: vista.columnas ? vista.columnas * 2 : 3 }, (_, indice) => (
                <span key={indice} className="selector-vista-producto">
                  {!vista.columnas && <><span className="selector-vista-foto" /><span className="selector-vista-texto" /></>}
                </span>
              ))}
            </span>
            <span className="selector-paleta-nombre">{vista.nombre}</span>
            <span className="selector-tipografia-descripcion">{vista.descripcion}</span>
          </button>
        ))}
      </div>

      <div className="selector-paletas-acciones">
        <button type="button" onClick={guardar} disabled={guardando || seleccionada === guardada}
          className="boton boton-primario">
          {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar vista del catálogo'}
        </button>
      </div>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'}
          className={`admin-aviso ${aviso.tipo === 'exito' ? 'admin-aviso--exito' : 'admin-aviso--error'}`}>
          {aviso.texto}
        </p>
      )}
    </div>
  );
}
