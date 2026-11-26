import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// Correo, horario e Instagram de la tienda: van en el pie de página y en la sección de Instagram de la landing
const CAMPOS = ['correo_contacto', 'horario_atencion', 'instagram_usuario', 'mostrar_direccion_pie',
  'telefono_comercial', 'facebook_url', 'x_url', 'youtube_url', 'tiktok_url'
];

const formularioDe = (configuracion) => ({
  correo_contacto: configuracion?.correo_contacto || '',
  horario_atencion: configuracion?.horario_atencion || '',
  instagram_usuario: configuracion?.instagram_usuario || '',
  mostrar_direccion_pie: Boolean(configuracion?.mostrar_direccion_pie),
  telefono_comercial: configuracion?.telefono_comercial || '',
  facebook_url: configuracion?.facebook_url || '',
  x_url: configuracion?.x_url || '',
  youtube_url: configuracion?.youtube_url || '',
  tiktok_url: configuracion?.tiktok_url || '',
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

export default function GestorContacto() {
  const [formulario, setFormulario] = useState(formularioDe(null));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState({});
  const [exito, setExito] = useState('');

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setFormulario(formularioDe(data)))
      .catch((error) => {
        console.error('Error al cargar el contacto de la tienda:', error);
        setErrores({ general: 'No se pudieron cargar los datos de contacto.' });
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
      // El servidor normaliza el usuario de Instagram (@MiTienda -> mitienda)
      setFormulario(formularioDe(data));
      await recargarConfiguracion();
      setExito('Datos de contacto guardados: ya se ven en tu tienda.');
    } catch (error) {
      setErrores(erroresDe(error));
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando datos de contacto..."><EsqueletoFormulario campos={4} /></Cargando>;

  // Asocia el error del backend con su campo (aria-describedby)
  const describir = (campo, ayuda) => {
    const ids = [ayuda, errores[campo] && `contacto-${campo}-error`].filter(Boolean).join(' ');
    return { 'aria-describedby': ids || undefined, 'aria-invalid': errores[campo] ? true : undefined };
  };
  const errorCampo = (campo) => errores[campo]
    ? <p id={`contacto-${campo}-error`} className="admin-error-campo">{errores[campo]}</p>
    : null;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Se muestran en el pie de página de tu tienda. Si un dato queda vacío, no aparece.
      </p>

      {errores.general && <p role="alert" className="admin-aviso admin-aviso--error">{errores.general}</p>}
      {exito && <p role="status" className="admin-aviso admin-aviso--exito">{exito}</p>}

      <form onSubmit={guardar} className="admin-formulario">
        <div className="admin-campo">
          <label htmlFor="contacto-correo">Correo de contacto</label>
          <input
            id="contacto-correo"
            type="email"
            value={formulario.correo_contacto}
            onChange={(e) => editar('correo_contacto', e.target.value)}
            placeholder="Ej: hola@mitienda.cl"
            {...describir('correo_contacto')}
          />
          {errorCampo('correo_contacto')}
        </div>

        <div className="admin-campo">
          <label htmlFor="contacto-horario">Horario de atención</label>
          <textarea
            id="contacto-horario"
            rows={3}
            maxLength={500}
            value={formulario.horario_atencion}
            onChange={(e) => editar('horario_atencion', e.target.value)}
            placeholder={'Ej: Lunes a viernes, 10:00 a 19:00\nSábado, 10:00 a 14:00'}
            {...describir('horario_atencion', 'contacto-horario-ayuda')}
          />
          <p id="contacto-horario-ayuda" className="admin-ayuda">Cada línea se muestra por separado.</p>
          {errorCampo('horario_atencion')}
        </div>

        <div className="admin-campo">
          <label htmlFor="contacto-instagram">Instagram</label>
          <input
            id="contacto-instagram"
            type="text"
            value={formulario.instagram_usuario}
            onChange={(e) => editar('instagram_usuario', e.target.value)}
            placeholder="Ej: @mitienda"
            {...describir('instagram_usuario', 'contacto-instagram-ayuda')}
          />
          <p id="contacto-instagram-ayuda" className="admin-ayuda">
            Tu usuario o el enlace a tu perfil. Con él aparece la sección de Instagram en la página de inicio;
            sus fotos se suben desde "Editar página de inicio".
          </p>
          {errorCampo('instagram_usuario')}
        </div>

        {/* Teléfono comercial del emprendedor */}
        <div className="admin-campo">
          <label htmlFor="contacto-telefono">Teléfono comercial</label>
          <input
            id="contacto-telefono"
            type="tel"
            value={formulario.telefono_comercial}
            onChange={(e) => editar('telefono_comercial', e.target.value)}
            placeholder="Ej: +56 9 1234 5678"
            autoComplete="tel"
            {...describir('telefono_comercial', 'contacto-telefono-ayuda')}
          />
          <p id="contacto-telefono-ayuda" className="admin-ayuda">
            Número de contacto de tu negocio. Se mostrará en el pie de página.
          </p>
          {errorCampo('telefono_comercial')}
        </div>

        {/* Enlaces a redes sociales del emprendedor */}
        {[
          {
            campo: 'facebook_url',
            nombre: 'Facebook',
            ejemplo: 'https://www.facebook.com/mitienda'
          },
          {
            campo: 'x_url',
            nombre: 'X (Twitter)',
            ejemplo: 'https://x.com/mitienda'
          },
          {
            campo: 'youtube_url',
            nombre: 'YouTube',
            ejemplo: 'https://www.youtube.com/@mitienda'
          },
          {
            campo: 'tiktok_url',
            nombre: 'TikTok',
            ejemplo: 'https://www.tiktok.com/@mitienda'
          }
        ].map(({ campo, nombre, ejemplo }) => (
          <div className="admin-campo" key={campo}>
            <label htmlFor={`contacto-${campo}`}>{nombre}</label>
            <input
              id={`contacto-${campo}`}
              type="url"
              value={formulario[campo]}
              onChange={(e) => editar(campo, e.target.value)}
              placeholder={ejemplo}
              {...describir(campo)}
            />
            {errorCampo(campo)}
          </div>
        ))}
        
        <div>
          <label className="admin-casilla">
            <input
              type="checkbox"
              checked={formulario.mostrar_direccion_pie}
              onChange={(e) => editar('mostrar_direccion_pie', e.target.checked)}
              aria-describedby="contacto-direccion-ayuda"
            />
            Mostrar la dirección del local en el pie de página
          </label>
          <p id="contacto-direccion-ayuda" className="admin-ayuda admin-ayuda--sangria">
            Es la de "Dirección del Local y Retiro en Tienda". Déjala sin marcar si despachas desde tu casa.
          </p>
        </div>

        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar contacto y redes'}
          </button>
        </div>
      </form>
    </>
  );
}
