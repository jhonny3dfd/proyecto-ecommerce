import { useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { completarSerie, etiquetaPunto, formatearMonto, formatearNumero } from './formato';

const MEDIDAS = {
  total: { nombre: 'Monto', formato: formatearMonto },
  pedidos: { nombre: 'Pedidos', formato: formatearNumero },
};

// Un solo gráfico con un interruptor entre monto y pedidos. La tabla de abajo da los mismos datos sin el gráfico
export default function GraficoVentas({ serie, periodo }) {
  const [medida, setMedida] = useState('total');
  const puntos = completarSerie(serie, periodo).map((punto) => ({
    ...punto, etiqueta: etiquetaPunto(punto.fecha, periodo.agrupacion),
  }));
  const { nombre, formato } = MEDIDAS[medida];
  const porMes = periodo.agrupacion === 'MES';

  return (
    <section className="dashboard-bloque" aria-labelledby="dashboard-grafico">
      <div className="dashboard-bloque-encabezado">
        <h3 id="dashboard-grafico" className="dashboard-bloque-titulo">
          Ventas del periodo{porMes ? ', por mes' : ''}
        </h3>
        <div className="dashboard-interruptor" role="group" aria-label="Qué mostrar en el gráfico">
          {Object.entries(MEDIDAS).map(([clave, { nombre: texto }]) => (
            <button key={clave} type="button" aria-pressed={medida === clave} onClick={() => setMedida(clave)}>
              {texto}
            </button>
          ))}
        </div>
      </div>

      {serie.length === 0 ? (
        <p className="dashboard-vacio">No hay ventas pagadas en este periodo.</p>
      ) : (
        <>
          <div className="dashboard-grafico" aria-hidden="true">
            <ResponsiveContainer width="100%" height="100%">
              {/* Sin capa de accesibilidad: el gráfico queda fuera del teclado y del lector de pantalla, que usan la
                  tabla de abajo (aria-hidden no puede contener elementos enfocables) */}
              <BarChart data={puntos} margin={{ top: 10, right: 8, left: 8, bottom: 0 }} accessibilityLayer={false}>
                <CartesianGrid vertical={false} stroke="var(--color-border)" />
                <XAxis dataKey="etiqueta" tick={{ fill: 'var(--color-muted)', fontSize: 12 }} tickLine={false}
                  minTickGap={16} />
                <YAxis tick={{ fill: 'var(--color-muted)', fontSize: 12 }} tickLine={false} axisLine={false}
                  allowDecimals={false} width={medida === 'total' ? 84 : 32} tickFormatter={formato} />
                <Tooltip formatter={(valor) => [formato(valor), nombre]} cursor={{ fill: 'var(--color-secondary)' }} />
                <Bar dataKey={medida} name={nombre} fill="var(--color-primary)" radius={[3, 3, 0, 0]} maxBarSize={36} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <details className="dashboard-datos">
            <summary>Ver los datos del gráfico</summary>
            <div tabIndex={0} role="region" aria-label="Datos de las ventas del periodo" className="dashboard-tabla-envoltorio">
              <table className="dashboard-tabla">
                <caption className="visualmente-oculto">Ventas pagadas {porMes ? 'por mes' : 'por día'}</caption>
                <thead>
                  <tr><th scope="col">{porMes ? 'Mes' : 'Día'}</th><th scope="col">Pedidos</th><th scope="col">Monto</th></tr>
                </thead>
                <tbody>
                  {serie.map((punto) => (
                    <tr key={punto.fecha}>
                      <th scope="row">{etiquetaPunto(punto.fecha, periodo.agrupacion)}</th>
                      <td>{formatearNumero(punto.pedidos)}</td>
                      <td>{formatearMonto(punto.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  );
}
