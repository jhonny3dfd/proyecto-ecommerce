
import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import Spinner from './carga/Spinner';

export default function SelectorProyectosSobreMi({ blogActivo = true }) {
  const [publicaciones, setPublicaciones] = useState([]);
  const [seleccionados, setSeleccionados] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [exito, setExito] = useState('');

  useEffect(() => {
    Promise.all([
      clienteAxios.get('ventas/admin/blog/'),
      clienteAxios.get('ventas/admin/sobre-mi/proyectos/')
    ])
      .then(([respuestaBlog, respuestaProyectos]) => {
        setPublicaciones(respuestaBlog.data);
        setSeleccionados(respuestaProyectos.data.proyectos || []);
      })
      .catch((errorCarga) => {
        console.error('Error al cargar los proyectos:', errorCarga);
        setError('No se pudieron cargar las publicaciones o los proyectos destacados.');
      })
      .finally(() => setCargando(false));
  }, []);

  const alternar = (id) => {
    setSeleccionados((actuales) =>
      actuales.includes(id)
        ? actuales.filter((actual) => actual !== id)
        : [...actuales, id]
    );
    setExito('');
    setError('');
  };

  const mover = (indice, direccion) => {
    const nuevoIndice = indice + direccion;

    if (nuevoIndice < 0 || nuevoIndice >= seleccionados.length) return;

    setSeleccionados((actuales) => {
      const copia = [...actuales];
      [copia[indice], copia[nuevoIndice]] = [
        copia[nuevoIndice],
        copia[indice]
      ];
      return copia;
    });

    setExito('');
  };

  const guardar = async () => {
    setGuardando(true);
    setError('');
    setExito('');

    try {
      const { data } = await clienteAxios.put(
        'ventas/admin/sobre-mi/proyectos/',
        { proyectos: seleccionados }
      );

      setSeleccionados(data.proyectos);
      setExito('Los proyectos destacados se guardaron correctamente.');
    } catch (errorGuardado) {
      console.error('Error al guardar proyectos:', errorGuardado);
      setError('No se pudieron guardar los proyectos destacados.');
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) {
    return <Cargando texto="Cargando proyectos destacados..." />;
  }

  const publicacionesPorId = new Map(
    publicaciones.map((publicacion) => [publicacion.id, publicacion])
  );

  return (
    <section aria-labelledby="sobre-mi-proyectos-titulo">
      <h5 id="sobre-mi-proyectos-titulo">Proyectos destacados</h5>

      <p className="texto-secundario admin-descripcion">
        Selecciona las publicaciones del blog que quieras destacar
        en tu página Sobre mí. Puedes cambiar su orden.
        Los borradores no serán visibles para los clientes.
        {!blogActivo && ' El blog está apagado: los proyectos no se mostrarán hasta que lo actives.'}
      </p>

      {error && (
        <p role="alert" className="admin-aviso admin-aviso--error">
          {error}
        </p>
      )}

      {exito && (
        <p role="status" className="admin-aviso admin-aviso--exito">
          {exito}
        </p>
      )}

      {publicaciones.length === 0 ? (
        <p className="texto-secundario">
          Todavía no tienes publicaciones. Puedes crearlas
          desde la sección Blog del panel.
        </p>
      ) : (
        <>
          <div className="admin-campo">
            <p><strong>Seleccionar publicaciones</strong></p>

            {publicaciones.map((publicacion) => (
              <label
                key={publicacion.id}
                className="admin-casilla"
              >
                <input
                  type="checkbox"
                  checked={seleccionados.includes(publicacion.id)}
                  onChange={() => alternar(publicacion.id)}
                />

                {publicacion.titulo}

                {' '}
                ({publicacion.estado === 'PUBLICADA'
                  ? 'Publicada'
                  : 'Borrador'})
              </label>
            ))}
          </div>

          {seleccionados.length > 0 && (
            <div className="admin-campo">
              <p><strong>Orden de aparición</strong></p>

              <ol>
                {seleccionados.map((id, indice) => {
                  const publicacion = publicacionesPorId.get(id);

                  return (
                    <li key={id}>
                      <span>
                        {publicacion?.titulo || `Publicación ${id}`}
                      </span>

                      {' '}

                      <button
                        type="button"
                        className="boton boton-contorno"
                        disabled={indice === 0}
                        onClick={() => mover(indice, -1)}
                        aria-label={`Subir ${publicacion?.titulo || id}`}
                      >
                        Subir
                      </button>

                      {' '}

                      <button
                        type="button"
                        className="boton boton-contorno"
                        disabled={indice === seleccionados.length - 1}
                        onClick={() => mover(indice, 1)}
                        aria-label={`Bajar ${publicacion?.titulo || id}`}
                      >
                        Bajar
                      </button>
                    </li>
                  );
                })}
              </ol>
            </div>
          )}
        </>
      )}

      <button
        type="button"
        className="boton boton-primario"
        onClick={guardar}
        disabled={guardando || Boolean(error)}
      >
        {guardando && <Spinner />}
        {guardando ? 'Guardando...' : 'Guardar proyectos destacados'}
      </button>
    </section>
  );
}
