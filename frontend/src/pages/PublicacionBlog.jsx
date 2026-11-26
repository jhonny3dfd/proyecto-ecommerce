import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
// Mismas clases que el editor: alineaciones, sangrías y viñetas de las listas
import 'react-quill-new/dist/quill.snow.css';
import clienteAxios from '../components/auth/axiosConfig';
import GaleriaPublicacion from '../components/GaleriaPublicacion';
import VideoYouTube from '../components/VideoYouTube';
import Header from '../components/header/header';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { formatearFechaLarga } from '../utils/fechas';
// El texto del editor se muestra con los mismos estilos que las páginas legales (.legal-contenido)
import './PaginaLegal.css';
import './Blog.css';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoTexto } from '../components/carga/EsqueletosTienda';

// Una publicación del blog: portada, texto y galería. Un borrador responde igual que una que no existe
export default function PublicacionBlog() {
  const { slug } = useParams();
  const configuracion = useConfiguracionTienda();
  const nombre = configuracion?.blog_nombre || 'Nosotros';
  // Se guarda a qué slug corresponde: si no coincide con la URL, aún está cargando
  const [resultado, setResultado] = useState({ slug: null, publicacion: null, error: null });

  useEffect(() => {
    clienteAxios.get(`ventas/blog/${encodeURIComponent(slug)}/`)
      .then(({ data }) => setResultado({ slug, publicacion: data, error: null }))
      .catch((error) => setResultado({
        slug, publicacion: null, error: error.response?.status === 404 ? 'no-encontrada' : 'conexion'
      }));
  }, [slug]);

  const cargando = resultado.slug !== slug;
  const { publicacion, error } = resultado;

  useEffect(() => {
    if (publicacion) document.title = publicacion.titulo;
  }, [publicacion]);

  // Con el blog apagado, el 404 no es de esta publicación: la sección completa no está disponible
  const blogApagado = configuracion && !configuracion.blog_activo;

  return (
    <>
      <Header />

      <main className="blog-main">
        <div className="blog-articulo">
          {cargando ? (
            <Cargando texto="Cargando la publicación..."><EsqueletoTexto /></Cargando>
          ) : publicacion ? (
            <article>
              <Link to="/blog" className="enlace-flecha blog-volver">
                <span aria-hidden="true">←</span> {nombre}
              </Link>
              <h1 className="blog-titulo">{publicacion.titulo}</h1>
              {publicacion.fecha_publicacion && (
                <time className="blog-fecha" dateTime={publicacion.fecha_publicacion}>
                  {formatearFechaLarga(publicacion.fecha_publicacion)}
                </time>
              )}
              {publicacion.resumen && <p className="blog-resumen texto-secundario">{publicacion.resumen}</p>}
              {publicacion.portada && (
                <img className="blog-portada" src={publicacion.portada} alt={`Portada de "${publicacion.titulo}"`} />
              )}
              {publicacion.youtube_id && (
                <VideoYouTube
                  className="blog-video"
                  youtubeId={publicacion.youtube_id}
                  titulo={publicacion.titulo}
                  portada={publicacion.portada}
                />
              )}
              {publicacion.contenido && (
                <div className="legal-contenido ql-snow">
                  {/* El servidor limpia este HTML al guardarlo: solo queda el formato del editor */}
                  <div className="ql-editor" dangerouslySetInnerHTML={{ __html: publicacion.contenido }} />
                </div>
              )}
              {publicacion.fotos.length > 0 && (
                <GaleriaPublicacion fotos={publicacion.fotos} titulo={publicacion.titulo} />
              )}
            </article>
          ) : (
            <div className="blog-error" role={error === 'conexion' ? 'alert' : undefined}>
              <h1 className="blog-titulo">
                {error === 'conexion' ? 'No pudimos cargar esta página'
                  : blogApagado ? 'Esta página no está disponible' : 'Publicación no encontrada'}
              </h1>
              <p>
                {error === 'conexion' ? 'Revisa tu conexión e inténtalo nuevamente.'
                  : blogApagado ? 'La tienda no tiene esta sección activa por ahora.'
                    : 'La publicación que buscas no existe o ya no está disponible.'}
              </p>
              {blogApagado || error === 'conexion'
                ? <Link to="/" className="boton boton-contorno">Ir al inicio</Link>
                : <Link to="/blog" className="boton boton-contorno">Ver {nombre}</Link>}
            </div>
          )}
        </div>
      </main>
    </>
  );
}
