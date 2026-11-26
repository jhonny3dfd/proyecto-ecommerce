import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// Blog o portafolio de la tienda: activo, el enlace del menú lleva a /blog con el nombre que elija el admin
const CAMPOS = ['blog_activo', 'blog_nombre'];
const NOMBRE_POR_DEFECTO = 'Nosotros';

const formularioDe = (configuracion) => ({
  blog_activo: Boolean(configuracion?.blog_activo),
  blog_nombre: configuracion?.blog_nombre || NOMBRE_POR_DEFECTO
});

// El backend responde { campo: [mensajes] }
const erroresDe = (error) => {
  const datos = error.response?.data;
  if (!datos || typeof datos !== 'object') return { general: 'No se pudieron guardar los cambios. Inténtalo de nuevo.' };
  const porCampo = Object.fromEntries(Object.entries(datos)
    .filter(([campo]) => CAMPOS.includes(campo))
    .map(([campo, mensajes]) => [campo, [].concat(mensajes).join(' ')]));
  return { ...porCampo, general: 'Revisa los datos marcados.' };
};

export default function GestorBlog() {
  const [formulario, setFormulario] = useState(formularioDe(null));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState({});
  const [exito, setExito] = useState('');

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setFormulario(formularioDe(data)))
      .catch((error) => {
        console.error('Error al cargar la configuración del blog:', error);
        setErrores({ general: 'No se pudo cargar la configuración del blog.' });
      })
      .finally(() => setCargando(false));
  }, []);

  const editar = (campo, valor) => {
    setFormulario((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actual) => ({ ...actual, [campo]: undefined }));
    setExito('');
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrores({});
    setExito('');
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', formulario);
      setFormulario(formularioDe(data));
      await recargarConfiguracion();
      setExito(data.blog_activo
        ? `Blog activado: tus clientes ya ven "${data.blog_nombre}" en el menú de la tienda.`
        : 'Blog desactivado: el menú vuelve a llevar a la sección Nosotros de tu página de inicio.');
    } catch (error) {
      setErrores(erroresDe(error));
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando blog..."><EsqueletoFormulario campos={2} /></Cargando>;

  // Asocia el error del backend con su campo (aria-describedby)
  const describir = (campo, ayuda) => {
    const ids = [ayuda, errores[campo] && `blog-${campo}-error`].filter(Boolean).join(' ');
    return { 'aria-describedby': ids || undefined, 'aria-invalid': errores[campo] ? true : undefined };
  };
  const errorCampo = (campo) => errores[campo]
    ? <p id={`blog-${campo}-error`} className="admin-error-campo">{errores[campo]}</p>
    : null;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Una página propia para contar tu historia o mostrar tus trabajos, con publicaciones de texto y fotos. Las
        escribes en la sección Blog del panel; puedes prepararlas antes de activarlo. Tu página de inicio no cambia.
      </p>

      {errores.general && <p role="alert" className="admin-aviso admin-aviso--error">{errores.general}</p>}
      {exito && <p role="status" className="admin-aviso admin-aviso--exito">{exito}</p>}

      <form onSubmit={guardar} className="admin-formulario">
        <label className="admin-casilla">
          <input
            type="checkbox"
            checked={formulario.blog_activo}
            onChange={(e) => editar('blog_activo', e.target.checked)}
            {...describir('blog_activo')}
          />
          Mostrar el blog en mi tienda
        </label>
        {errorCampo('blog_activo')}

        <div className="admin-campo">
          <label htmlFor="blog-nombre">Nombre en el menú</label>
          <input
            id="blog-nombre"
            type="text"
            maxLength={30}
            value={formulario.blog_nombre}
            onChange={(e) => editar('blog_nombre', e.target.value)}
            placeholder={NOMBRE_POR_DEFECTO}
            {...describir('blog_nombre', 'blog-nombre-ayuda')}
          />
          <p id="blog-nombre-ayuda" className="admin-ayuda">
            Por ejemplo: Nosotros, Blog, Portafolio o Mis trabajos. Si lo dejas vacío, se llama "{NOMBRE_POR_DEFECTO}".
          </p>
          {errorCampo('blog_nombre')}
        </div>

        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar blog'}
          </button>
        </div>
      </form>
    </>
  );
}
