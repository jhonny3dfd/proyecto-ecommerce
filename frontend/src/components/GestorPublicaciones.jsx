import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import FormularioPublicacion from './FormularioPublicacion';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { formatearFechaLarga } from '../utils/fechas';

// Vista "Blog" del panel: las publicaciones (los borradores primero) y el formulario para crear o editar.
// Funciona con el blog apagado, para dejar publicaciones listas antes de activarlo
export default function GestorPublicaciones() {
  const configuracion = useConfiguracionTienda();
  const [publicaciones, setPublicaciones] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [aviso, setAviso] = useState(null);
  // null: la lista; 'nueva' o una publicación: el formulario
  const [editando, setEditando] = useState(null);

  const cargar = () => clienteAxios.get('ventas/admin/blog/')
    .then(({ data }) => setPublicaciones(data))
    .catch((error) => {
      console.error('Error al cargar las publicaciones:', error);
      setAviso({ tipo: 'error', texto: 'No se pudieron cargar las publicaciones.' });
    })
    .finally(() => setCargando(false));

  useEffect(() => {
    cargar();
  }, []);

  const eliminar = async (publicacion) => {
    if (!window.confirm(`¿Eliminar "${publicacion.titulo}"? También se borran sus fotos y no se puede deshacer.`)) return;
    setAviso(null);
    try {
      await clienteAxios.delete(`ventas/admin/blog/${publicacion.id}/`);
      setPublicaciones((actuales) => actuales.filter((p) => p.id !== publicacion.id));
      setAviso({ tipo: 'exito', texto: `"${publicacion.titulo}" se eliminó.` });
    } catch {
      setAviso({ tipo: 'error', texto: 'No se pudo eliminar la publicación. Inténtalo de nuevo.' });
    }
  };

  if (editando) {
    return (
      <FormularioPublicacion
        // Un formulario nuevo por publicación: lee sus datos una sola vez al montarse
        key={editando === 'nueva' ? 'nueva' : editando.id}
        publicacion={editando === 'nueva' ? null : editando}
        alVolver={() => {
          setEditando(null);
          setAviso(null);
          cargar();
        }}
      />
    );
  }

  return (
    <div>
      <div className="admin-encabezado-vista">
        <h2 className="admin-titulo">Blog</h2>
        <button type="button" className="boton boton-primario" onClick={() => setEditando('nueva')}>
          + Nueva publicación
        </button>
      </div>

      {configuracion && !configuracion.blog_activo && (
        <p className="admin-aviso blog-admin-apagado">
          El blog está desactivado: tus clientes no lo ven. Puedes preparar publicaciones y activarlo en
          Configuración, en "Blog o Portafolio".
        </p>
      )}

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      {cargando ? (
        <Cargando texto="Cargando publicaciones..."><EsqueletoLista /></Cargando>
      ) : publicaciones.length === 0 ? (
        <p className="texto-secundario">Aún no tienes publicaciones. Crea la primera con "Nueva publicación".</p>
      ) : (
        <ul className="lista-sin-estilo blog-admin-lista">
          {publicaciones.map((publicacion) => {
            const publicada = publicacion.estado === 'PUBLICADA';
            return (
              <li key={publicacion.id} className="blog-admin-item">
                <div className="blog-admin-item-texto">
                  <h3 className="blog-admin-item-titulo">{publicacion.titulo}</h3>
                  <p className="admin-ayuda">
                    <span className={`blog-admin-estado${publicada ? ' blog-admin-estado--publicada' : ''}`}>
                      {publicada ? 'Publicada' : 'Borrador'}
                    </span>
                    {publicacion.fecha_publicacion && ` · ${formatearFechaLarga(publicacion.fecha_publicacion)}`}
                    {` · ${publicacion.fotos.length} ${publicacion.fotos.length === 1 ? 'foto' : 'fotos'}`}
                  </p>
                </div>
                <div className="publicacion-acciones">
                  <button type="button" className="boton boton-contorno" onClick={() => setEditando(publicacion)}>
                    Editar <span className="visualmente-oculto">"{publicacion.titulo}"</span>
                  </button>
                  <button type="button" className="boton boton-contorno" onClick={() => eliminar(publicacion)}>
                    Eliminar <span className="visualmente-oculto">"{publicacion.titulo}"</span>
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
