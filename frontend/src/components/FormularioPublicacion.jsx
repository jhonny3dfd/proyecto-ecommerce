import { useEffect, useId, useMemo, useState } from 'react';
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';
import clienteAxios from './auth/axiosConfig';
import Spinner from './carga/Spinner';

// Igual que el backend (domain/blog.py)
const MAX_FOTOS = 10;
const FORMATOS = ['image/jpeg', 'image/png', 'image/webp'];
const CAMPOS = ['titulo', 'resumen', 'contenido', 'estado', 'portada', 'youtube'];
// Multipart: sin Content-Type, el navegador lo pone con su separador
const MULTIPART = { headers: { 'Content-Type': undefined } };

const formularioDe = (publicacion) => ({
  titulo: publicacion?.titulo || '',
  resumen: publicacion?.resumen || '',
  contenido: publicacion?.contenido || '',
  youtube: publicacion?.youtube ?? (publicacion?.youtube_id ? `https://www.youtube.com/watch?v=${publicacion.youtube_id}` : '')
});

// DRF responde ['mensaje'], 'mensaje' o, en una lista de archivos, { 0: ['mensaje'] }
const textoDe = (mensajes) => (mensajes && typeof mensajes === 'object' && !Array.isArray(mensajes)
  ? Object.values(mensajes).flat() : [].concat(mensajes)).join(' ');

const erroresDe = (error, general) => {
  const datos = error.response?.data;
  if (!datos || typeof datos !== 'object') return { general };
  const porCampo = Object.fromEntries(Object.entries(datos)
    .filter(([campo]) => CAMPOS.includes(campo))
    .map(([campo, mensajes]) => [campo, textoDe(mensajes)]));
  return { ...porCampo, general: datos.detail || 'Revisa los datos marcados.' };
};

// Crear o editar una publicación del blog. La galería aparece una vez guardada (las fotos necesitan su id)
export default function FormularioPublicacion({ publicacion: inicial, alVolver }) {
  const id = useId();
  // La publicación tal como está guardada (null mientras es nueva)
  const [publicacion, setPublicacion] = useState(inicial);
  const [formulario, setFormulario] = useState(formularioDe(inicial));
  const [portadaNueva, setPortadaNueva] = useState(null);
  const [quitarPortada, setQuitarPortada] = useState(false);
  // Solo cambios hechos por el admin; cargar el texto en el editor no cuenta
  const [modificado, setModificado] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [errores, setErrores] = useState({});
  const [exito, setExito] = useState('');

  // Vista previa de la portada elegida, antes de subirla
  const vistaPortada = useMemo(() => portadaNueva && URL.createObjectURL(portadaNueva), [portadaNueva]);
  useEffect(() => () => vistaPortada && URL.revokeObjectURL(vistaPortada), [vistaPortada]);
  const portada = portadaNueva ? vistaPortada : (quitarPortada ? null : publicacion?.portada);

  const publicada = publicacion?.estado === 'PUBLICADA';
  const fotos = publicacion?.fotos || [];

  const editar = (campo, valor) => {
    setFormulario((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actual) => ({ ...actual, [campo]: undefined }));
    setModificado(true);
    setExito('');
  };

  const elegirPortada = (e) => {
    const [archivo] = e.target.files;
    e.target.value = '';
    if (!archivo) return;
    if (!FORMATOS.includes(archivo.type)) {
      setErrores((actual) => ({ ...actual, portada: 'Solo se permiten imágenes JPG, PNG o WebP.' }));
      return;
    }
    setPortadaNueva(archivo);
    setQuitarPortada(false);
    setErrores((actual) => ({ ...actual, portada: undefined }));
    setModificado(true);
    setExito('');
  };

  const sacarPortada = () => {
    setPortadaNueva(null);
    setQuitarPortada(true);
    setModificado(true);
    setExito('');
  };

  const guardar = async (estado) => {
    setGuardando(true);
    setErrores({});
    setExito('');
    const datos = new FormData();
    Object.entries(formulario).forEach(([campo, valor]) => datos.append(campo, valor));
    datos.append('estado', estado);
    if (portadaNueva) datos.append('portada', portadaNueva);
    else if (quitarPortada) datos.append('quitar_portada', 'true');
    try {
      const { data } = publicacion
        ? await clienteAxios.put(`ventas/admin/blog/${publicacion.id}/`, datos, MULTIPART)
        : await clienteAxios.post('ventas/admin/blog/', datos, MULTIPART);
      setPublicacion(data);
      // Lo que quedó guardado: el servidor limpia el HTML del texto
      setFormulario(formularioDe(data));
      setPortadaNueva(null);
      setQuitarPortada(false);
      setModificado(false);
      setExito(data.estado === 'PUBLICADA'
        ? `"${data.titulo}" está publicada: tus clientes la ven en el blog.`
        : `"${data.titulo}" quedó como borrador: tus clientes no la ven.`);
    } catch (error) {
      setErrores(erroresDe(error, 'No se pudo guardar la publicación. Inténtalo de nuevo.'));
    } finally {
      setGuardando(false);
    }
  };

  const subirFotos = async (e) => {
    const archivos = Array.from(e.target.files);
    e.target.value = '';
    if (archivos.length === 0) return;
    if (archivos.some((archivo) => !FORMATOS.includes(archivo.type))) {
      setErrores({ fotos: 'Solo se permiten imágenes JPG, PNG o WebP.' });
      return;
    }
    if (fotos.length + archivos.length > MAX_FOTOS) {
      const libres = MAX_FOTOS - fotos.length;
      setErrores({ fotos: libres > 0
        ? `Puedes agregar ${libres} ${libres === 1 ? 'foto más' : 'fotos más'} (máximo ${MAX_FOTOS}).`
        : `La galería ya tiene ${MAX_FOTOS} fotos: quita alguna para agregar otra.` });
      return;
    }
    setSubiendo(true);
    setErrores({});
    setExito('');
    const datos = new FormData();
    archivos.forEach((archivo) => datos.append('fotos', archivo));
    try {
      const { data } = await clienteAxios.post(`ventas/admin/blog/${publicacion.id}/fotos/`, datos, MULTIPART);
      // Solo la galería: el resto del formulario puede tener cambios sin guardar
      setPublicacion((actual) => ({ ...actual, fotos: data.fotos }));
      setExito(archivos.length === 1 ? 'Foto agregada.' : `${archivos.length} fotos agregadas.`);
    } catch (error) {
      const datosError = error.response?.data;
      setErrores({ fotos: textoDe(datosError?.fotos ?? datosError?.detail ?? 'No se pudieron subir las fotos.') });
    } finally {
      setSubiendo(false);
    }
  };

  const quitarFoto = async (foto, numero) => {
    if (!window.confirm(`¿Quitar la foto ${numero} de la galería?`)) return;
    setErrores({});
    setExito('');
    try {
      const { data } = await clienteAxios.delete(`ventas/admin/blog/${publicacion.id}/fotos/${foto.id}/`);
      setPublicacion((actual) => ({ ...actual, fotos: data.fotos }));
      setExito('Foto quitada.');
    } catch {
      setErrores({ fotos: 'No se pudo quitar la foto. Inténtalo de nuevo.' });
    }
  };

  const volver = () => {
    if (modificado && !window.confirm('Hay cambios sin guardar en esta publicación. ¿Descartarlos?')) return;
    alVolver();
  };

  // Asocia el error del backend con su campo (aria-describedby)
  const describir = (campo, ayuda) => {
    const ids = [ayuda, errores[campo] && `${id}-${campo}-error`].filter(Boolean).join(' ');
    return { 'aria-describedby': ids || undefined, 'aria-invalid': errores[campo] ? true : undefined };
  };
  const errorCampo = (campo) => errores[campo]
    ? <p id={`${id}-${campo}-error`} className="admin-error-campo">{errores[campo]}</p>
    : null;

  return (
    <div>
      <div className="admin-encabezado-vista">
        <h2 className="admin-titulo">{publicacion ? 'Editar publicación' : 'Nueva publicación'}</h2>
        <button type="button" className="boton boton-contorno" onClick={volver}>Volver a la lista</button>
      </div>

      {errores.general && <p role="alert" className="admin-aviso admin-aviso--error">{errores.general}</p>}
      {exito && <p role="status" className="admin-aviso admin-aviso--exito">{exito}</p>}

      <form className="admin-formulario publicacion-formulario" onSubmit={(e) => e.preventDefault()}>
        <div className="admin-campo">
          <label htmlFor={`${id}-titulo`}>Título</label>
          <input id={`${id}-titulo`} type="text" maxLength={150} value={formulario.titulo}
            onChange={(e) => editar('titulo', e.target.value)} {...describir('titulo')} />
          {errorCampo('titulo')}
        </div>

        <div className="admin-campo">
          <label htmlFor={`${id}-resumen`}>Resumen</label>
          <textarea id={`${id}-resumen`} rows={2} maxLength={300} value={formulario.resumen}
            onChange={(e) => editar('resumen', e.target.value)} {...describir('resumen', `${id}-resumen-ayuda`)} />
          <p id={`${id}-resumen-ayuda`} className="admin-ayuda">
            Opcional. Se muestra en la lista del blog, bajo el título.
          </p>
          {errorCampo('resumen')}
        </div>

        <div className="admin-campo">
          <span className="publicacion-etiqueta" id={`${id}-portada-etiqueta`}>Foto de portada</span>
          {portada ? (
            <img className="publicacion-portada" src={portada} alt="Vista previa de la portada" />
          ) : (
            <p className="admin-ayuda">Sin portada.</p>
          )}
          <div className="publicacion-acciones">
            <input id={`${id}-portada`} type="file" accept={FORMATOS.join(',')} onChange={elegirPortada}
              className="visualmente-oculto galeria-input" {...describir('portada', `${id}-portada-etiqueta`)} />
            <label htmlFor={`${id}-portada`} className="boton boton-contorno galeria-zona">
              {portada ? 'Cambiar portada' : 'Elegir portada'}
            </label>
            {portada && (
              <button type="button" className="boton boton-contorno" onClick={sacarPortada}>Quitar portada</button>
            )}
          </div>
          {errorCampo('portada')}
        </div>

        <div className="admin-campo">
          <label htmlFor={`${id}-youtube`}>Video de YouTube</label>
          <input
            id={`${id}-youtube`}
            type="text"
            value={formulario.youtube}
            placeholder="https://www.youtube.com/watch?v=..."
            onChange={(e) => editar('youtube', e.target.value)}
            {...describir('youtube', `${id}-youtube-ayuda`)}
          />
          <p id={`${id}-youtube-ayuda`} className="admin-ayuda">
            Opcional. Pega el enlace de un video o Short de YouTube.
          </p>
          {errorCampo('youtube')}
        </div>

        <div className="admin-campo publicacion-editor">
          <span className="publicacion-etiqueta" id={`${id}-contenido-etiqueta`}>Texto</span>
          <ReactQuill
            theme="snow"
            // HTML interno de Quill: el semántico convierte los espacios en &nbsp; (el texto no se ajusta al ancho)
            // y quita el marcador de las listas que usa el CSS de la página pública
            useSemanticHTML={false}
            value={formulario.contenido}
            onChange={(valor, _delta, origen) => {
              if (origen === 'user') editar('contenido', valor);
              else setFormulario((actual) => ({ ...actual, contenido: valor }));
            }}
          />
          {errorCampo('contenido')}
        </div>

        <div className="publicacion-acciones">
          {publicada ? (
            <>
              <button type="button" className="boton boton-primario" disabled={guardando}
                onClick={() => guardar('PUBLICADA')}>
                {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar cambios'}
              </button>
              <button type="button" className="boton boton-contorno" disabled={guardando}
                onClick={() => guardar('BORRADOR')}>
                Pasar a borrador
              </button>
              <a className="enlace-flecha" href={`/blog/${publicacion.slug}`} target="_blank" rel="noopener noreferrer">
                Ver en la tienda <span aria-hidden="true">↗</span>
              </a>
            </>
          ) : (
            <>
              <button type="button" className="boton boton-primario" disabled={guardando}
                onClick={() => guardar('PUBLICADA')}>
                {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Publicar'}
              </button>
              <button type="button" className="boton boton-contorno" disabled={guardando}
                onClick={() => guardar('BORRADOR')}>
                Guardar borrador
              </button>
            </>
          )}
        </div>
      </form>

      <hr className="admin-separador" />

      <section aria-labelledby={`${id}-fotos-titulo`}>
        <h3 id={`${id}-fotos-titulo`} className="config-titulo">Galería ({fotos.length} de {MAX_FOTOS})</h3>
        {!publicacion ? (
          <p className="admin-ayuda">Guarda la publicación (como borrador o publicada) para agregarle fotos.</p>
        ) : (
          <>
            {fotos.length > 0 && (
              <ul className="lista-sin-estilo publicacion-fotos">
                {fotos.map((foto, indice) => (
                  <li key={foto.id} className="publicacion-foto">
                    <img src={foto.imagen} alt={`Foto ${indice + 1}`} />
                    <button type="button" className="boton boton-contorno" onClick={() => quitarFoto(foto, indice + 1)}>
                      Quitar <span className="visualmente-oculto">foto {indice + 1}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {fotos.length < MAX_FOTOS && (
              <div className="publicacion-acciones">
                <input id={`${id}-fotos`} type="file" accept={FORMATOS.join(',')} multiple onChange={subirFotos}
                  disabled={subiendo} className="visualmente-oculto galeria-input"
                  aria-describedby={[`${id}-fotos-ayuda`, errores.fotos && `${id}-fotos-error`].filter(Boolean).join(' ')} />
                <label htmlFor={`${id}-fotos`} className="boton boton-contorno galeria-zona">
                  {subiendo ? 'Subiendo...' : 'Agregar fotos'}
                </label>
              </div>
            )}
            <p id={`${id}-fotos-ayuda`} className="admin-ayuda">
              JPG, PNG o WebP. Se suben al elegirlas y se ven en la publicación en el orden en que las agregas.
            </p>
            {errorCampo('fotos')}
          </>
        )}
      </section>
    </div>
  );
}
