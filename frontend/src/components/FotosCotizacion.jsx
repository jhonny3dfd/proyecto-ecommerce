import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import './FotosCotizacion.css';

// Las fotos que adjuntó el cliente. No están en /media/ (que es público): se piden a la API con la sesión del
// admin, así que un <img src> no sirve (no manda el token). Se descargan y se muestran como object URL.
export default function FotosCotizacion({ cotizacionId, fotos }) {
  const [vistas, setVistas] = useState({ estado: 'cargando', urls: [] });

  useEffect(() => {
    let vigente = true;
    let creadas = [];
    Promise.all(fotos.map(foto => clienteAxios.get(`ventas/admin/cotizaciones/${cotizacionId}/fotos/${foto}/`,
      { responseType: 'blob' })))
      .then(respuestas => {
        creadas = respuestas.map(({ data }) => URL.createObjectURL(data));
        if (vigente) setVistas({ estado: 'listo', urls: creadas });
        else creadas.forEach(url => URL.revokeObjectURL(url));
      })
      .catch(() => { if (vigente) setVistas({ estado: 'error', urls: [] }); });
    return () => {
      vigente = false;
      creadas.forEach(url => URL.revokeObjectURL(url));
    };
  }, [cotizacionId, fotos]);

  if (vistas.estado === 'error') {
    return <p className="texto-secundario">No se pudieron cargar las fotos. Recarga la página para intentarlo de nuevo.</p>;
  }
  if (vistas.estado === 'cargando') {
    return <p className="texto-secundario">Cargando {fotos.length === 1 ? 'la foto' : 'las fotos'}...</p>;
  }
  return (
    <ul className="cotizacion-fotos" aria-label={`Fotos de la cotización #${cotizacionId}`}>
      {vistas.urls.map((url, indice) => (
        <li key={url}>
          {/* Se abre en grande en otra pestaña */}
          <a href={url} target="_blank" rel="noopener noreferrer">
            <img src={url} alt={`Foto ${indice + 1} de la cotización #${cotizacionId} (se abre en otra pestaña)`} />
          </a>
        </li>
      ))}
    </ul>
  );
}
