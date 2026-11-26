import { TEXTOS_POR_DEFECTO } from './textosPorDefecto';
import { CampoEditable, SelectorImagen } from './ControlesEdicion';
import { Link } from 'react-router-dom';
import { resolverMenu } from '../../utils/menuPrincipal';

// Sección "Nosotros" de la landing: foto a un lado y el texto del emprendedor al otro. Sin texto no se muestra,
// salvo en modo edición, donde aparece para que el admin pueda llenarla.
export default function SeccionNosotros({ configuracion, edicion }) {
  const editando = Boolean(edicion?.editando);
  if (!configuracion.nosotros_texto && !configuracion.sobre_mi_activo && !editando) return null;
  const imagen = configuracion.nosotros_imagen;
  const nombreSobreMi = resolverMenu(configuracion).find(enlace => enlace.id === 'sobre_mi').nombre;

  return (
    <section id="nosotros" className={`seccion-landing nosotros${imagen ? '' : ' nosotros--sin-imagen'}`}
      aria-labelledby="nosotros-titulo">
      <div className="contenedor nosotros-contenido">
        {(imagen || editando) && (
          <div className="nosotros-imagen">
            {imagen ? <img src={imagen} alt="" loading="lazy" /> : (
              <span className="nosotros-imagen-vacia">Sin foto: la sección se verá solo con texto</span>
            )}
            {editando && (
              <div className="nosotros-imagen-controles">
                <SelectorImagen campo="nosotros_imagen" nombre="foto" tieneImagen={Boolean(imagen)} edicion={edicion} />
              </div>
            )}
          </div>
        )}
        <div className="nosotros-texto">
          <span className="antetitulo">Nosotros</span>
          {editando ? (
            <>
              <h2 id="nosotros-titulo" className="visualmente-oculto">Nosotros</h2>
              <CampoEditable campo="nosotros_titulo" edicion={edicion} className="nosotros-titulo-campo" />
              <CampoEditable campo="nosotros_texto" edicion={edicion} multilinea filas={6}
                className="texto-secundario nosotros-parrafo" />
              {!edicion.textos.nosotros_texto && (
                <p className="nosotros-aviso">Mientras no tenga texto, esta sección no se muestra en tu tienda.</p>
              )}
            </>
          ) : (
            <>
              <h2 id="nosotros-titulo">{configuracion.nosotros_titulo || TEXTOS_POR_DEFECTO.nosotros_titulo}</h2>
              {/* Los saltos de línea que escribe el admin se respetan */}
              {configuracion.nosotros_texto && (
                <p className="texto-secundario nosotros-parrafo">{configuracion.nosotros_texto}</p>
              )}
              {/* Enlace a la página independiente Sobre mí */}
              {configuracion.sobre_mi_activo && (
                <div>
                  <Link to="/sobre-mi" className="boton boton-contorno">Conoce más: {nombreSobreMi}</Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
