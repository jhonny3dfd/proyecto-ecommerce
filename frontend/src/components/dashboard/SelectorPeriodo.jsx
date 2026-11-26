import { useState } from 'react';
import { textoRango } from './formato';

const PERIODOS = [
  { clave: 'ESTE_MES', nombre: 'Este mes' },
  { clave: 'MES_ANTERIOR', nombre: 'Mes anterior' },
  { clave: 'ULTIMOS_30', nombre: 'Últimos 30 días' },
  { clave: 'ESTE_ANO', nombre: 'Este año' },
  { clave: 'DESDE_INICIO', nombre: 'Desde el inicio' },
  { clave: 'PERSONALIZADO', nombre: 'Personalizado' },
];

// Un solo selector manda en todo el dashboard. El rango personalizado se aplica con su botón, no al escribir cada fecha
export default function SelectorPeriodo({ consulta, onCambiar, periodo, anterior }) {
  const [clave, setClave] = useState(consulta.periodo);
  const [desde, setDesde] = useState(consulta.desde || '');
  const [hasta, setHasta] = useState(consulta.hasta || '');

  const elegir = (nueva) => {
    setClave(nueva);
    if (nueva !== 'PERSONALIZADO') onCambiar({ periodo: nueva });
  };

  const aplicar = (event) => {
    event.preventDefault();
    onCambiar({ periodo: 'PERSONALIZADO', desde, hasta });
  };

  return (
    <div className="dashboard-periodo">
      <form className="dashboard-periodo-controles" onSubmit={aplicar}>
        <label className="dashboard-campo">
          Periodo
          <select value={clave} onChange={(e) => elegir(e.target.value)}>
            {PERIODOS.map(({ clave: valor, nombre }) => <option key={valor} value={valor}>{nombre}</option>)}
          </select>
        </label>
        {clave === 'PERSONALIZADO' && (
          <>
            <label className="dashboard-campo">
              Desde
              <input type="date" value={desde} max={hasta || undefined} required
                onChange={(e) => setDesde(e.target.value)} />
            </label>
            <label className="dashboard-campo">
              Hasta
              <input type="date" value={hasta} min={desde || undefined} required
                onChange={(e) => setHasta(e.target.value)} />
            </label>
            <button type="submit" className="boton boton-primario">Aplicar</button>
          </>
        )}
      </form>
      {periodo && (
        <p className="dashboard-periodo-rango">
          {periodo.desde ? textoRango(periodo.desde, periodo.hasta) : 'Desde la primera venta'}
          {anterior && <> · comparado con {textoRango(anterior.desde, anterior.hasta)}</>}
        </p>
      )}
    </div>
  );
}
