import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
// Mismas clases que el editor: alineaciones, sangrías y viñetas de las listas
import 'react-quill-new/dist/quill.snow.css';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import './PaginaLegal.css';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoTexto } from '../components/carga/EsqueletosTienda';

// RF-03.5: página pública de Términos, Privacidad o Reembolsos (solo si está publicada)
export default function PaginaLegal() {
  const { tipo } = useParams();
  // Se guarda a qué tipo corresponde: si no coincide con la URL, la página aún está cargando
  const [resultado, setResultado] = useState({ tipo: null, pagina: null, error: null });

  useEffect(() => {
    clienteAxios.get(`ventas/paginas-legales/${encodeURIComponent(tipo)}/`)
      .then(({ data }) => setResultado({ tipo, pagina: data, error: null }))
      .catch((error) => setResultado({
        tipo,
        pagina: null,
        error: error.response?.status === 404 ? 'no-encontrada' : 'conexion'
      }));
  }, [tipo]);

  const cargando = resultado.tipo !== tipo;
  const { pagina, error } = resultado;

  useEffect(() => {
    if (pagina) document.title = pagina.titulo;
  }, [pagina]);

  return (
    <>
      <Header />

      <main tabIndex={-1} id="contenido" className="legal-main">
        <div className="legal">
          {cargando ? (
            <Cargando texto="Cargando la página..."><EsqueletoTexto lineas={14} /></Cargando>
          ) : pagina ? (
            <article>
              <span className="antetitulo">Información legal</span>
              <h1 className="legal-titulo">{pagina.titulo}</h1>
              <p className="legal-fecha">
                Última actualización: {new Date(pagina.ultima_actualizacion).toLocaleDateString('es-CL', { dateStyle: 'long' })}
              </p>
              <div className="legal-contenido ql-snow">
                {/* El servidor limpia este HTML al guardarlo: solo queda el formato del editor */}
                <div className="ql-editor" dangerouslySetInnerHTML={{ __html: pagina.contenido }} />
              </div>
            </article>
          ) : (
            <div className="legal-error" role={error === 'conexion' ? 'alert' : undefined}>
              <h1 className="legal-titulo">
                {error === 'conexion' ? 'No pudimos cargar esta página' : 'Página no encontrada'}
              </h1>
              <p>
                {error === 'conexion'
                  ? 'Revisa tu conexión e inténtalo nuevamente.'
                  : 'La página legal que buscas no existe o aún no está publicada.'}
              </p>
              <Link to="/catalogo" className="boton boton-contorno">Ir al catálogo</Link>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
