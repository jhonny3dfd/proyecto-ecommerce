// Indicador del dashboard: etiqueta chica, cifra grande con la tipografía de títulos y una descripción
export default function DashboardCard({ titulo, valor, descripcion, icono }) {
  return (
    <div className="admin-indicador">
      <div className="admin-indicador-etiqueta">
        {icono}
        <p>{titulo}</p>
      </div>
      <p className="admin-indicador-valor">{valor}</p>
      <p className="admin-indicador-descripcion">{descripcion}</p>
    </div>
  );
}
