import DashboardCard from '../DashboardCard';
import { formatearMonto, formatearNumero, plural } from './formato';

// Sin colores: el signo y la palabra dicen si subió o bajó (los colores de alerta quedan solo para "Para hoy")
const textoVariacion = (variacion, hayAnterior) => {
  if (!hayAnterior) return 'Desde la primera venta';
  if (variacion === null || variacion === undefined) return 'Sin ventas en el periodo anterior';
  if (variacion === 0) return 'Igual que el periodo anterior';
  return `${variacion > 0 ? '+' : '−'}${formatearNumero(Math.abs(variacion))} % frente al periodo anterior`;
};

const textoDiferencia = (diferencia, hayAnterior) => {
  if (!hayAnterior || diferencia === null || diferencia === undefined) return 'Desde la primera venta';
  if (diferencia === 0) return 'Igual que el periodo anterior';
  return `${plural(Math.abs(diferencia), 'pedido')} ${diferencia > 0 ? 'más' : 'menos'} que el periodo anterior`;
};

export default function TarjetasResumen({ tarjetas, hayAnterior }) {
  return (
    <div className="dashboard-tarjetas">
      <DashboardCard titulo="Ventas" valor={formatearMonto(tarjetas.ventas)}
        descripcion={textoVariacion(tarjetas.variacion_ventas, hayAnterior)} />
      <DashboardCard titulo="Pedidos" valor={formatearNumero(tarjetas.pedidos)}
        descripcion={textoDiferencia(tarjetas.diferencia_pedidos, hayAnterior)} />
      <DashboardCard titulo="Ticket promedio" valor={formatearMonto(tarjetas.ticket_promedio)}
        descripcion={textoVariacion(tarjetas.variacion_ticket, hayAnterior)} />
      <DashboardCard titulo="Clientes nuevos" valor={formatearNumero(tarjetas.clientes_nuevos)}
        descripcion="Compraron por primera vez en el periodo" />
    </div>
  );
}
