import { CAMPOS_FOTOS_INSTAGRAM } from '../../hooks/useEdicionLanding';
import { SelectorImagen } from './ControlesEdicion';

const perfilDe = (usuario) => `https://www.instagram.com/${encodeURIComponent(usuario)}/`;

// Sección de Instagram de la landing: @usuario, las fotos que sube el admin (no es el feed real: sin API ni
// cookies de terceros) y un botón al perfil. Sin usuario no se muestra, salvo en modo edición.
export default function SeccionInstagram({ configuracion, edicion }) {
  const editando = Boolean(edicion?.editando);
  const usuario = configuracion.instagram_usuario;
  if (!usuario && !editando) return null;
  const fotos = CAMPOS_FOTOS_INSTAGRAM.map((campo) => ({ campo, url: configuracion[campo] }));

  return (
    <section id="instagram" className="seccion-landing seccion-landing--alterna instagram" aria-labelledby="instagram-titulo">
      <div className="contenedor">
        <div className="instagram-encabezado">
          <span className="antetitulo">Síguenos en Instagram</span>
          <h2 id="instagram-titulo">{usuario ? `@${usuario}` : 'Instagram'}</h2>
        </div>

        {editando && !usuario && (
          <p className="seccion-landing-nota instagram-nota">
            Para que esta sección se muestre, escribe tu usuario en el panel: Configuración &gt; Contacto y Redes.
          </p>
        )}

        {editando ? (
          <ul className="lista-sin-estilo instagram-grilla">
            {fotos.map(({ campo, url }, indice) => (
              <li key={campo} className="instagram-espacio">
                <div className="instagram-foto">
                  {url ? <img src={url} alt="" /> : <span className="instagram-foto-vacia">Foto {indice + 1}</span>}
                </div>
                <SelectorImagen campo={campo} nombre={`foto ${indice + 1}`} tieneImagen={Boolean(url)} edicion={edicion} />
              </li>
            ))}
          </ul>
        ) : (
          fotos.some(({ url }) => url) && (
            // Las fotos también llevan al perfil, pero el enlace accesible es el botón de abajo (no se repite 6 veces)
            <div className="instagram-grilla" aria-hidden="true">
              {fotos.filter(({ url }) => url).map(({ campo, url }) => (
                <a key={campo} href={perfilDe(usuario)} target="_blank" rel="noopener noreferrer" tabIndex={-1}
                  className="instagram-foto">
                  <img src={url} alt="" loading="lazy" />
                </a>
              ))}
            </div>
          )
        )}

        {usuario && (
          <div className="instagram-acciones">
            <a href={perfilDe(usuario)} target="_blank" rel="noopener noreferrer" className="boton boton-contorno">
              Seguir en Instagram
              <span className="visualmente-oculto"> (se abre en una pestaña nueva)</span>
            </a>
          </div>
        )}
      </div>
    </section>
  );
}
