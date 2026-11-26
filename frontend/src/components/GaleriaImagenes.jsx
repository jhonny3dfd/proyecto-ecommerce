import { useId, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import Spinner from './carga/Spinner';

// Dirección de una foto subida: catalogo/productos/<producto>/<id>.<formato> (CLAVE_IMAGEN en el backend)
const FOTO_SUBIDA = /\/catalogo\/productos\/[0-9a-f]{24}\/([0-9a-f]{32}(?:_[A-Za-z0-9]{7})*)\.(?:jpg|png|webp)$/;

export default function GaleriaImagenes({
  productoId,
  imagenes = [],
  archivosGestionados = [],
  onImagenesChange,
  onArchivosChange
}) {
  const idInput = useId();

  const [archivosSeleccionados, setArchivosSeleccionados] = useState([]);
  const [subiendo, setSubiendo] = useState(false);
  const [eliminando, setEliminando] = useState(null);
  const [error, setError] = useState('');

  const manejarArchivos = (archivos) => {
    const nuevosArchivos = Array.from(archivos);

    const imagenesValidas = nuevosArchivos.filter((archivo) =>
      ['image/jpeg', 'image/png', 'image/webp'].includes(archivo.type)
    );

    if (imagenesValidas.length !== nuevosArchivos.length) {
      setError('Solo se permiten imágenes JPG, PNG o WebP.');
    } else {
      setError('');
    }

    setArchivosSeleccionados((prev) => [...prev, ...imagenesValidas]);
  };

  const handleInputChange = (e) => {
    manejarArchivos(e.target.files);
    e.target.value = '';
  };

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    manejarArchivos(e.dataTransfer.files);
  };

  const eliminarSeleccionada = (index) => {
    setArchivosSeleccionados((prev) =>
      prev.filter((_, i) => i !== index)
    );
    document.getElementById(idInput)?.focus();
  };

  /*
   * Devuelve el ID de una foto subida a la tienda, o null si la imagen es un enlace externo.
   *
   * Se busca por la dirección y no por la posición: archivosGestionados solo trae las fotos
   * subidas, así que en una galería con enlaces las posiciones no coinciden. Al editar un
   * producto todavía no hay archivosGestionados, y el ID sale de la dirección de la foto.
   */
  const obtenerIdFotoSubida = (url) => {
    const archivo = archivosGestionados.find((a) => a.url === url);
    if (archivo) return archivo.id;

    try {
      const { pathname } = new URL(url, window.location.origin);
      return pathname.match(FOTO_SUBIDA)?.[1] ?? null;
    } catch {
      return null;
    }
  };

  const eliminarImagenExistente = async (url, index) => {
    if (!productoId) {
      setError('No se encontró el producto.');
      return;
    }

    const imagenId = obtenerIdFotoSubida(url);

    const confirmar = window.confirm(
      '¿Estás seguro de que deseas eliminar esta imagen?'
    );

    if (!confirmar) {
      return;
    }

    setEliminando(index);
    setError('');

    try {
      if (imagenId) {
        // Foto subida: el backend también borra su archivo
        await clienteAxios.delete(
          `catalogo/productos/${productoId}/imagenes/${imagenId}/`
        );
      } else {
        // Enlace externo: no hay archivo en la tienda, solo se quita de la galería
        await clienteAxios.delete(
          `catalogo/productos/${productoId}/imagenes/enlace/`,
          { params: { url } }
        );
      }

      // Actualizar las imágenes mostradas
      const nuevasImagenes = imagenes.filter((_, i) => i !== index);

      onImagenesChange(nuevasImagenes);
      document.getElementById(idInput)?.focus();

      // Actualizar archivos gestionados si el padre los utiliza
      if (onArchivosChange) {
        const nuevosArchivos = archivosGestionados.filter(
          (archivo) => archivo.url !== url
        );

        onArchivosChange(nuevosArchivos);
      }
    } catch (err) {
      console.error(
        'Error al eliminar imagen:',
        err.response?.data || err.message
      );

      setError(
        err.response?.data?.detail ||
        'No se pudo eliminar la imagen.'
      );
    } finally {
      setEliminando(null);
    }
  };

  const subirImagenes = async () => {
    if (!productoId) {
      setError('Primero debes guardar el producto.');
      return;
    }

    if (archivosSeleccionados.length === 0) {
      return;
    }

    setSubiendo(true);
    setError('');

    try {
      const formData = new FormData();

      archivosSeleccionados.forEach((archivo) => {
        formData.append('imagenes', archivo);
      });

      const { data } = await clienteAxios.post(
        `catalogo/productos/${productoId}/imagenes/`,
        formData,
        {
          headers: {
            'Content-Type': undefined
          }
        }
      );

      onImagenesChange(data.imagenes || []);
      onArchivosChange(data.archivos || []);

      setArchivosSeleccionados([]);
    } catch (err) {
      console.error(
        'Error al subir imágenes:',
        err.response?.data || err.message
      );

      setError(
        err.response?.data?.detail ||
        'Ocurrió un error al subir las imágenes.'
      );
    } finally {
      setSubiendo(false);
    }
  };

  return (
    <div
      style={{
        // En el formulario de producto va dentro de la grilla de campos (.producto-campos): ocupa la fila completa,
        // como la descripción y el SEO, en vez de una sola columna
        gridColumn: '1 / -1',
        marginTop: '20px',
        padding: '20px',
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '8px'
      }}
    >
      <h4>Galería de imágenes</h4>

      {/* Zona para subir imágenes: es la etiqueta del input, así un clic abre el selector una sola vez (antes el
          input estaba dentro de la zona y su clic volvía a ella, abriendo el selector en bucle). El input va antes y
          oculto solo a la vista, para que reciba el foco del teclado; el foco se dibuja en la zona (Admin.css). */}
      <input
        id={idInput}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        onChange={handleInputChange}
        className="visualmente-oculto galeria-input"
        aria-label="Seleccionar imágenes para la galería"
        aria-describedby={`${idInput}-formatos`}
      />
      <label
        htmlFor={idInput}
        className="galeria-zona"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        style={{
          display: 'block',
          border: '2px dashed var(--color-primary)',
          borderRadius: '8px',
          padding: '30px',
          textAlign: 'center',
          cursor: 'pointer',
          backgroundColor: 'var(--color-secondary)'
        }}
      >
        <p style={{ margin: 0, fontWeight: 'bold' }}>
          Arrastra tus imágenes aquí
        </p>

        <p style={{ color: 'var(--color-muted)' }}>
          o haz clic para seleccionarlas
        </p>

        <small id={`${idInput}-formatos`}>
          Formatos permitidos: JPG, PNG y WebP
        </small>
      </label>

      {/* Mensaje de error */}
      {error && (
        <p
          role="alert"
          style={{
            color: '#b91c1c',
            backgroundColor: '#fee2e2',
            padding: '10px',
            borderRadius: '4px',
            marginTop: '10px'
          }}
        >
          {error}
        </p>
      )}

      {/* Imágenes seleccionadas todavía no subidas */}
      {archivosSeleccionados.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h5>Imágenes seleccionadas</h5>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'repeat(auto-fill, minmax(120px, 1fr))',
              gap: '10px'
            }}
          >
            {archivosSeleccionados.map((archivo, index) => (
              <div key={index}>
                <img
                  src={URL.createObjectURL(archivo)}
                  alt={archivo.name}
                  style={{
                    width: '100%',
                    height: '100px',
                    objectFit: 'cover',
                    borderRadius: '6px'
                  }}
                />

                <button
                  type="button"
                  aria-label={`Quitar imagen seleccionada ${archivo.name}`}
                  onClick={() => eliminarSeleccionada(index)}
                  style={{
                    width: '100%',
                    marginTop: '5px',
                    backgroundColor: '#b91c1c',
                    color: '#fff',
                    border: 'none',
                    padding: '5px',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  Quitar
                </button>
              </div>
            ))}
          </div>

          <button
            type="button"
            onClick={subirImagenes}
            disabled={subiendo}
            style={{
              width: '100%',
              marginTop: '15px',
              padding: '12px',
              backgroundColor: 'var(--color-primary)',
              color: 'var(--color-on-primary)',
              border: 'none',
              borderRadius: '4px',
              cursor: subiendo ? 'not-allowed' : 'pointer'
            }}
          >
            {subiendo ? 'Subiendo imágenes...' : 'Subir imágenes'}
          </button>
        </div>
      )}

      {/* Imágenes que ya están almacenadas */}
      {imagenes.length > 0 && (
        <div style={{ marginTop: '25px' }}>
          <h5>Imágenes de la galería</h5>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns:
                'repeat(auto-fill, minmax(120px, 1fr))',
              gap: '10px'
            }}
          >
            {imagenes.map((url, index) => (
              <div
                key={url || index}
                style={{
                  border: '1px solid var(--color-border)',
                  borderRadius: '6px',
                  padding: '5px'
                }}
              >
                <img
                  src={url}
                  alt={`Producto ${index + 1}`}
                  style={{
                    width: '100%',
                    height: '100px',
                    objectFit: 'cover',
                    borderRadius: '6px'
                  }}
                />

                {index === 0 && (
                  <small
                    style={{
                      display: 'block',
                      textAlign: 'center',
                      marginTop: '5px',
                      fontWeight: 'bold'
                    }}
                  >
                    Portada
                  </small>
                )}

                <button
                  type="button"
                  aria-label={`Eliminar imagen ${index + 1} de la galería`}
                  onClick={() =>
                    eliminarImagenExistente(url, index)
                  }
                  disabled={eliminando === index}
                  style={{
                    width: '100%',
                    marginTop: '6px',
                    backgroundColor:
                      eliminando === index
                        ? '#9ca3af'
                        : '#b91c1c',
                    color: '#fff',
                    border: 'none',
                    padding: '6px',
                    borderRadius: '4px',
                    cursor:
                      eliminando === index
                        ? 'not-allowed'
                        : 'pointer'
                  }}
                >
                  {eliminando === index && <Spinner />}
                  {eliminando === index
                    ? 'Eliminando...'
                    : 'Eliminar'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
