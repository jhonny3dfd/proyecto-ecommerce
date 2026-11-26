
import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

const ESTILOS_AVISO = {
  error: {
    backgroundColor: '#fef2f2',
    border: '1px solid #fca5a5',
    color: '#991b1b'
  },
  exito: {
    backgroundColor: '#f0fdf4',
    border: '1px solid #86efac',
    color: '#166534'
  }
};

const estiloCampo = {
  width: '100%',
  padding: '10px',
  boxSizing: 'border-box',
  border: '1px solid var(--color-border)',
  borderRadius: '4px',
  backgroundColor: 'var(--color-surface)',
  color: 'var(--color-text)'
};

const estiloEtiqueta = {
  display: 'block',
  fontSize: '0.9rem',
  fontWeight: 'bold',
  marginBottom: '5px',
  color: 'var(--color-text)'
};

const obtenerMensajeError = (error) => {
  const datos = error.response?.data;

  if (datos?.detail) return datos.detail;

  return 'No se pudo guardar la configuración. Revisa los campos marcados.';
};

export default function GestorAnalitica() {
  const [googleAnalyticsId, setGoogleAnalyticsId] = useState('');
  const [metaPixelId, setMetaPixelId] = useState('');
  const [errores, setErrores] = useState({});
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => {
        setGoogleAnalyticsId(data.google_analytics_id || '');
        setMetaPixelId(data.meta_pixel_id || '');
      })
      .catch((error) => {
        console.error('Error al cargar la configuración de analítica:', error);
        setAviso({
          tipo: 'error',
          texto: 'No se pudo cargar la configuración de analítica.'
        });
      })
      .finally(() => setCargando(false));
  }, []);

  const handleGuardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrores({});
    setAviso(null);

    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', {
        google_analytics_id: googleAnalyticsId.trim(),
        meta_pixel_id: metaPixelId.trim()
      });

      setGoogleAnalyticsId(data.google_analytics_id || '');
      setMetaPixelId(data.meta_pixel_id || '');
      setAviso({
        tipo: 'exito',
        texto: 'La configuración de analítica se guardó correctamente.'
      });
    } catch (error) {
      const datos = error.response?.data || {};
      setErrores({
        google_analytics_id: datos.google_analytics_id?.[0] || '',
        meta_pixel_id: datos.meta_pixel_id?.[0] || ''
      });
      setAviso({
        tipo: 'error',
        texto: obtenerMensajeError(error)
      });
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando configuración de analítica..."><EsqueletoFormulario campos={2} /></Cargando>;

  return (
    <form
      onSubmit={handleGuardar}
      style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '640px' }}
    >
      <p style={{ margin: 0, color: 'var(--color-muted)', fontSize: '0.95rem' }}>
        Configura las herramientas para medir las visitas y la actividad de tu tienda.
        Deja un campo vacío si no deseas utilizar esa integración.
      </p>

      <p style={{ margin: 0, color: 'var(--color-muted)', fontSize: '0.9rem' }}>
        Los scripts de seguimiento solo deben ejecutarse cuando el comprador haya
        otorgado el consentimiento correspondiente para las cookies.
      </p>

      <div>
        <label htmlFor="google-analytics-id" style={estiloEtiqueta}>
          ID de Google Analytics
        </label>
        <input
          id="google-analytics-id"
          type="text"
          value={googleAnalyticsId}
          onChange={(e) => setGoogleAnalyticsId(e.target.value)}
          placeholder="G-XXXXXXXXXX"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={Boolean(errores.google_analytics_id)}
          aria-describedby={errores.google_analytics_id ? 'google-analytics-error' : 'google-analytics-ayuda'}
          style={estiloCampo}
        />
        <p
          id="google-analytics-ayuda"
          style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--color-muted)' }}
        >
          Encuentra el ID de medición en la configuración de tu propiedad de Google Analytics 4.
        </p>
        {errores.google_analytics_id && (
          <p id="google-analytics-error" role="alert" style={{ color: '#991b1b', fontSize: '0.85rem' }}>
            {errores.google_analytics_id}
          </p>
        )}
      </div>

      <div>
        <label htmlFor="meta-pixel-id" style={estiloEtiqueta}>
          ID de Meta Pixel
        </label>
        <input
          id="meta-pixel-id"
          type="text"
          inputMode="numeric"
          value={metaPixelId}
          onChange={(e) => setMetaPixelId(e.target.value)}
          placeholder="123456789012345"
          autoComplete="off"
          spellCheck={false}
          aria-invalid={Boolean(errores.meta_pixel_id)}
          aria-describedby={errores.meta_pixel_id ? 'meta-pixel-error' : 'meta-pixel-ayuda'}
          style={estiloCampo}
        />
        <p
          id="meta-pixel-ayuda"
          style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--color-muted)' }}
        >
          Encuentra el identificador en el administrador de eventos de Meta.
        </p>
        {errores.meta_pixel_id && (
          <p id="meta-pixel-error" role="alert" style={{ color: '#991b1b', fontSize: '0.85rem' }}>
            {errores.meta_pixel_id}
          </p>
        )}
      </div>

      {aviso && (
        <p
          role={aviso.tipo === 'error' ? 'alert' : 'status'}
          style={{
            ...ESTILOS_AVISO[aviso.tipo],
            padding: '8px 12px',
            borderRadius: '6px',
            margin: 0
          }}
        >
          {aviso.texto}
        </p>
      )}

      <div>
        <button
          type="submit"
          disabled={guardando}
          style={{
            padding: '10px 18px',
            backgroundColor: 'var(--color-primary)',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: guardando ? 'not-allowed' : 'pointer',
            fontWeight: 'bold'
          }}
        >
          {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar configuración'}
        </button>
      </div>
    </form>
  );
}
