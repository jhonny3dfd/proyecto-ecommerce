
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { Cargando } from '../components/carga/Esqueleto';
import { redesDeLaTienda } from '../utils/redesSociales';
import './Blog.css';
import './SobreMi.css';

// Página pública independiente del blog.
// El backend devuelve 404 si el emprendedor la desactivó.
export default function SobreMi() {
  const configuracion = useConfiguracionTienda();
  const [resultado, setResultado] = useState({
    cargando: true,
    datos: null,
    error: null
  });

  useEffect(() => {
    clienteAxios.get('ventas/sobre-mi/')
      .then(({ data }) => {
        setResultado({ cargando: false, datos: data, error: null });
      })
      .catch((error) => {
        setResultado({
          cargando: false,
          datos: null,
          error: error.response?.status === 404
            ? 'no-disponible'
            : 'conexion'
        });
      });
  }, []);

  useEffect(() => {
    if (resultado.datos?.nombre) {
      document.title = resultado.datos.nombre;
    }
  }, [resultado.datos]);

  const { cargando, datos, error } = resultado;
  // Fotos junto a la biografía (pedido de un cliente, opcionales) y las redes del pie, con su usuario
  const fotos = datos?.fotos || [];
  const redes = redesDeLaTienda(configuracion);

  return (
    <>
      <Header />

      <main id="contenido" tabIndex={-1} className="blog-main sobre-mi-main">
        <div className="contenedor">
          {cargando ? (
            <Cargando texto="Cargando Sobre mí..." />
          ) : error ? (
            <div
              className="blog-error"
              role={error === 'conexion' ? 'alert' : undefined}
            >
              <h1 className="blog-titulo">
                {error === 'conexion'
                  ? 'No pudimos cargar esta página'
                  : 'Esta página no está disponible'}
              </h1>

              <p>
                {error === 'conexion'
                  ? 'Revisa tu conexión e inténtalo nuevamente.'
                  : 'La tienda no tiene esta sección activa por ahora.'}
              </p>

              <Link to="/" className="boton boton-contorno">
                Ir al inicio
              </Link>
            </div>
          ) : (
            <>
              <header className="blog-cabecera">
                <span className="antetitulo">
                  {configuracion?.nombre_tienda || 'Nuestra tienda'}
                </span>

                <h1 className="blog-titulo">
                  {datos.nombre}
                </h1>
              </header>

              {(datos.biografia || fotos.length > 0) && (
                <section
                  className={`sobre-mi-biografia${fotos.length > 0 ? ' sobre-mi-biografia--con-fotos' : ''}`}
                  aria-label="Nuestra historia"
                >
                  {/* HTML limpiado por el backend antes de guardarse */}
                  {datos.biografia && (
                    <div
                      className="sobre-mi-contenido"
                      dangerouslySetInnerHTML={{
                        __html: datos.biografia
                      }}
                    />
                  )}
                  {fotos.length > 0 && (
                    <div className={`sobre-mi-fotos sobre-mi-fotos--${fotos.length}`}>
                      {fotos.map((foto) => (
                        <figure key={foto.url} className="sobre-mi-foto">
                          <img src={foto.url} alt={foto.alt} loading="lazy" />
                        </figure>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {datos.proyectos?.length > 0 && (
                <section
                  className="sobre-mi-seccion"
                  aria-labelledby="sobre-mi-proyectos"
                >
                  <h2 id="sobre-mi-proyectos">
                    Proyectos destacados
                  </h2>

                  <ul className="lista-sin-estilo blog-grilla">
                    {datos.proyectos.map((publicacion) => (
                      <li key={publicacion.slug}>
                        <article className="blog-tarjeta">
                          <div className="blog-tarjeta-imagen">
                            {publicacion.portada && (
                              <img
                                src={publicacion.portada}
                                alt=""
                                loading="lazy"
                              />
                            )}
                          </div>

                          <div className="blog-tarjeta-texto">
                            <h3 className="blog-tarjeta-titulo">
                              {configuracion?.blog_activo ? (
                                <Link to={`/blog/${publicacion.slug}`}>
                                  {publicacion.titulo}
                                </Link>
                              ) : (
                                publicacion.titulo
                              )}
                            </h3>

                            {publicacion.resumen && (
                              <p className="texto-secundario">
                                {publicacion.resumen}
                              </p>
                            )}
                          </div>
                        </article>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {((datos.contacto && Object.values(datos.contacto).some(Boolean)) || redes.length > 0) && (
                  <section
                    className="sobre-mi-seccion"
                    aria-labelledby="sobre-mi-contacto"
                  >
                    <h2 id="sobre-mi-contacto">
                      Contacto
                    </h2>

                    <ul className="sobre-mi-contactos">
                      {datos.contacto?.correo && (
                        <li>
                          <strong>Correo: </strong>
                          <a href={`mailto:${datos.contacto.correo}`}>
                            {datos.contacto.correo}
                          </a>
                        </li>
                      )}

                      {datos.contacto?.telefono && (
                        <li>
                          <strong>Teléfono: </strong>
                          <a href={`tel:${datos.contacto.telefono.replace(/[^\d+]/g, '')}`}>
                            {datos.contacto.telefono}
                          </a>
                        </li>
                      )}

                      {datos.contacto?.instagram && (
                        <li>
                          <strong>Instagram: </strong>
                          <a
                            href={`https://www.instagram.com/${datos.contacto.instagram.replace(/^@/, '')}/`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            @{datos.contacto.instagram.replace(/^@/, '')}
                          </a>
                        </li>
                      )}

                      {redes.map((red) => (
                        <li key={red.campo}>
                          <strong>{red.nombre}: </strong>
                          <a href={red.url} target="_blank" rel="noopener noreferrer"
                            aria-label={`${red.usuario || 'Ver perfil'} en ${red.nombre} (se abre en una pestaña nueva)`}>
                            {red.usuario || 'Ver perfil'}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
