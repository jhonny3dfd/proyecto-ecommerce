import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { formatearFechaLarga } from '../utils/fechas';
import './Blog.css';
import { Bloque, Cargando } from '../components/carga/Esqueleto';
import { EsqueletoBlog } from '../components/carga/EsqueletosTienda';

// Blog o portafolio de la tienda (si el admin lo activó): las publicaciones más recientes primero
export default function Blog() {
  const configuracion = useConfiguracionTienda();
  const nombre = configuracion?.blog_nombre || 'Nosotros';
  const [parametros] = useSearchParams();
  const pagina = Math.max(Number.parseInt(parametros.get('pagina'), 10) || 1, 1);
  // Se guarda a qué página corresponde: si no coincide con la URL, aún está cargando
  const [resultado, setResultado] = useState({ pagina: null, datos: null, error: null });

  useEffect(() => {
    clienteAxios.get('ventas/blog/', { params: { pagina } })
      .then(({ data }) => setResultado({ pagina, datos: data, error: null }))
      .catch((error) => setResultado({
        pagina, datos: null, error: error.response?.status === 404 ? 'no-disponible' : 'conexion'
      }));
  }, [pagina]);

  useEffect(() => {
    if (configuracion?.blog_activo) document.title = nombre;
  }, [configuracion, nombre]);

  const cargando = resultado.pagina !== pagina;
  const { datos, error } = resultado;

  return (
    <>
      <Header />

      <main className="blog-main">
        <div className="contenedor">
          {cargando ? (
            <Cargando texto="Cargando publicaciones...">
              <div className="blog-cabecera esqueleto-columna">
                <Bloque ancho="9rem" alto="0.75rem" />
                <Bloque ancho="14rem" alto="clamp(2.25rem, 5vw, 3.25rem)" />
              </div>
              <EsqueletoBlog />
            </Cargando>
          ) : error ? (
            <div className="blog-error" role={error === 'conexion' ? 'alert' : undefined}>
              <h1 className="blog-titulo">
                {error === 'conexion' ? 'No pudimos cargar esta página' : 'Esta página no está disponible'}
              </h1>
              <p>
                {error === 'conexion'
                  ? 'Revisa tu conexión e inténtalo nuevamente.'
                  : 'La tienda no tiene esta sección activa por ahora.'}
              </p>
              <Link to="/" className="boton boton-contorno">Ir al inicio</Link>
            </div>
          ) : (
            <>
              <header className="blog-cabecera">
                <span className="antetitulo">{configuracion?.nombre_tienda || 'Nuestra tienda'}</span>
                <h1 className="blog-titulo">{nombre}</h1>
              </header>

              {datos.resultados.length === 0 ? (
                <p className="blog-estado">Aún no hay publicaciones. Vuelve pronto.</p>
              ) : (
                <ul className="lista-sin-estilo blog-grilla">
                  {datos.resultados.map((publicacion) => (
                    <li key={publicacion.slug}>
                      <article className="blog-tarjeta">
                        <div className="blog-tarjeta-imagen">
                          {/* Decorativa: el título de la tarjeta ya dice de qué se trata */}
                          {publicacion.portada && <img src={publicacion.portada} alt="" loading="lazy" />}
                        </div>
                        <div className="blog-tarjeta-texto">
                          {publicacion.fecha_publicacion && (
                            <time className="blog-fecha" dateTime={publicacion.fecha_publicacion}>
                              {formatearFechaLarga(publicacion.fecha_publicacion)}
                            </time>
                          )}
                          <h2 className="blog-tarjeta-titulo">
                            {/* El enlace cubre toda la tarjeta (blog.css) */}
                            <Link to={`/blog/${publicacion.slug}`}>{publicacion.titulo}</Link>
                          </h2>
                          {publicacion.resumen && <p className="texto-secundario">{publicacion.resumen}</p>}
                        </div>
                      </article>
                    </li>
                  ))}
                </ul>
              )}

              {datos.paginas > 1 && (
                <nav className="blog-paginacion" aria-label={`Páginas de ${nombre}`}>
                  {pagina > 1 && (
                    <Link to={`/blog?pagina=${pagina - 1}`} className="enlace-flecha">
                      <span aria-hidden="true">←</span> Anteriores
                    </Link>
                  )}
                  <span className="texto-secundario">Página {pagina} de {datos.paginas}</span>
                  {pagina < datos.paginas && (
                    <Link to={`/blog?pagina=${pagina + 1}`} className="enlace-flecha">
                      Siguientes <span aria-hidden="true">→</span>
                    </Link>
                  )}
                </nav>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
