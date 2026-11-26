import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import RecentOrders from './RecentOrders';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoDashboard } from './carga/EsqueletosPanel';
import SelectorPeriodo from './dashboard/SelectorPeriodo';
import ExportarVentas from './dashboard/ExportarVentas';
import ParaHoy from './dashboard/ParaHoy';
import TarjetasResumen from './dashboard/TarjetasResumen';
import GraficoVentas from './dashboard/GraficoVentas';
import MasVendidos from './dashboard/MasVendidos';
import DetallesDashboard from './dashboard/DetallesDashboard';
import './dashboard/Dashboard.css';

function Encabezado() {
  return (
    <div className="dashboard-encabezado">
      <h2 className="admin-titulo">Dashboard</h2>
      <p className="dashboard-subtitulo">Lo que tienes que atender hoy y cómo le va a tu tienda.</p>
    </div>
  );
}

// RF-03.1, de arriba abajo: el periodo, "Para hoy", 4 cifras, un gráfico, más vendidos y últimos pedidos, y el
// detalle en pestañas. `onIrA(vista, filtro)` abre otra vista del panel (ej. Ventas con un filtro)
export default function Dashboard({ onIrA = () => {} }) {
  const [consulta, setConsulta] = useState({ periodo: 'ESTE_MES' });
  // A qué consulta corresponden los datos: si no es la pedida, se está actualizando
  const [cargada, setCargada] = useState({ consulta: null, datos: null, error: '' });
  const [pendientes, setPendientes] = useState({ datos: null, error: '' });

  useEffect(() => {
    let vigente = true;
    clienteAxios.get('ventas/dashboard/metricas/', { params: consulta })
      .then(({ data }) => { if (vigente) setCargada({ consulta, datos: data, error: '' }); })
      .catch((error) => {
        if (!vigente) return;
        const mensaje = error.response?.data?.periodo?.[0] || 'No fue posible cargar las cifras de la tienda.';
        setCargada((actual) => ({ ...actual, consulta, error: mensaje }));
      });
    return () => { vigente = false; };
  }, [consulta]);

  // "Para hoy" no depende del periodo: se pide una vez
  useEffect(() => {
    let vigente = true;
    clienteAxios.get('ventas/dashboard/pendientes/')
      .then(({ data }) => { if (vigente) setPendientes({ datos: data, error: '' }); })
      .catch(() => { if (vigente) setPendientes({ datos: null, error: 'No fue posible cargar los pendientes.' }); });
    return () => { vigente = false; };
  }, []);

  const { datos, error } = cargada;
  const actualizando = cargada.consulta !== consulta;

  if (!datos && !error) {
    return (
      <div>
        <Encabezado />
        <Cargando texto="Cargando información..."><EsqueletoDashboard /></Cargando>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <Encabezado />
      <div className="dashboard-periodo-fila">
        <SelectorPeriodo consulta={consulta} onCambiar={setConsulta} periodo={datos?.periodo} anterior={datos?.anterior} />
        <ExportarVentas consulta={consulta} />
      </div>
      {/* Mientras llega otro periodo se deja a la vista el anterior, para que la página no salte */}
      <p role="status" className="visualmente-oculto">{actualizando ? 'Actualizando las cifras…' : ''}</p>
      {error && <p role="alert" className="dashboard-error">{error}</p>}

      <ParaHoy pendientes={pendientes.datos} error={pendientes.error} onIrA={onIrA} />

      {datos && (
        <div className="dashboard-cifras-periodo" aria-busy={actualizando}>
          <TarjetasResumen tarjetas={datos.tarjetas} hayAnterior={Boolean(datos.anterior)} />
          <GraficoVentas serie={datos.serie} periodo={datos.periodo} />
          <div className="dashboard-columnas">
            <MasVendidos productos={datos.mas_vendidos} />
            <RecentOrders ordenes={datos.ultimas_ordenes} onVerTodos={() => onIrA('ventas')} />
          </div>
          <DetallesDashboard detalles={datos.detalles} />
        </div>
      )}
    </div>
  );
}
