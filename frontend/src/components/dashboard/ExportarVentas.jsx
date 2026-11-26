import { useState } from 'react';
import clienteAxios from '../auth/axiosConfig';

const NOMBRE_POR_DEFECTO = 'ventas.xlsx';

// El backend pone el nombre con el periodo (ej. ventas_2026-11-01_a_2026-11-17.xlsx)
function nombreArchivo(cabecera) {
  const coincidencia = /filename="?([^";]+)"?/.exec(cabecera || '');
  return coincidencia ? coincidencia[1] : NOMBRE_POR_DEFECTO;
}

function descargar(archivo, nombre) {
  const direccion = URL.createObjectURL(archivo);
  const enlace = document.createElement('a');
  enlace.href = direccion;
  enlace.download = nombre;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  URL.revokeObjectURL(direccion);
}

// RF-03.1: descarga en Excel las ventas del periodo que muestra el dashboard (`consulta`), con los datos de cada cliente
export default function ExportarVentas({ consulta }) {
  const [descargando, setDescargando] = useState(false);
  const [error, setError] = useState('');

  const exportar = async () => {
    setDescargando(true);
    setError('');
    try {
      const { data, headers } = await clienteAxios.get('ventas/dashboard/exportar/',
        { params: consulta, responseType: 'blob' });
      descargar(data, nombreArchivo(headers?.['content-disposition']));
    } catch {
      setError('No fue posible exportar las ventas. Inténtalo de nuevo.');
    } finally {
      setDescargando(false);
    }
  };

  return (
    <div className="dashboard-exportar">
      <button type="button" className="boton boton-contorno" onClick={exportar} disabled={descargando}>
        {descargando ? 'Preparando el Excel…' : 'Exportar ventas a Excel'}
      </button>
      {error && <p role="alert" className="dashboard-error">{error}</p>}
    </div>
  );
}
