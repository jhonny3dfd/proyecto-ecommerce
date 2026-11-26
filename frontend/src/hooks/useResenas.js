import { useEffect, useState } from 'react';
import clienteAxios from '../components/auth/axiosConfig';

export const SIN_RESENAS = { promedio: null, total: 0, resenas: [] };

// Reseñas aprobadas para la landing o la ficha: { promedio, total, resenas }. `activas` sale de la configuración
// (undefined mientras carga); con las reseñas apagadas no se consulta. Devuelve null mientras no se sabe
export default function useResenas(ruta, activas) {
  const [cargadas, setCargadas] = useState({ ruta: null, resumen: null });

  useEffect(() => {
    if (!activas) return;
    let vigente = true;
    clienteAxios.get(ruta)
      .then(({ data }) => {
        if (vigente) setCargadas({ ruta, resumen: typeof data?.total === 'number' ? data : SIN_RESENAS });
      })
      // Sin reseñas la página se ve igual: no se avisa del error
      .catch(() => { if (vigente) setCargadas({ ruta, resumen: SIN_RESENAS }); });
    return () => { vigente = false; };
  }, [ruta, activas]);

  if (activas === undefined) return null;
  if (!activas) return SIN_RESENAS;
  return cargadas.ruta === ruta ? cargadas.resumen : null;
}
