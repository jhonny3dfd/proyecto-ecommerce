import { useId, useRef, useState } from 'react';
import { formatearMonto, formatearNumero, plural } from './formato';

// Barras horizontales simples con el porcentaje escrito: se leen igual en todos los temas, sin tortas de colores
function Barras({ titulo, barras, vacio }) {
  return (
    <div className="dashboard-barras">
      <h4>{titulo}</h4>
      {barras.length === 0 ? <p className="dashboard-vacio">{vacio}</p> : (
        <ul>
          {barras.map((barra) => (
            <li key={barra.nombre}>
              <div className="dashboard-barra-texto">
                <span>{barra.nombre}</span>
                <span>{barra.porcentaje} % · {barra.detalle}</span>
              </div>
              <div className="dashboard-barra" aria-hidden="true">
                <span style={{ width: `${Math.max(barra.porcentaje, 1)}%` }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const conMonto = (barras) => barras.map((barra) => ({
  ...barra, detalle: `${formatearMonto(barra.total)} (${plural(barra.pedidos, 'pedido')})`,
}));

function ComoCompran({ detalles }) {
  return (
    <div className="dashboard-detalle-columnas">
      <Barras titulo="Medio de pago" barras={conMonto(detalles.medios_pago)} vacio="Sin ventas en este periodo." />
      <Barras titulo="Tipo de entrega" barras={conMonto(detalles.entregas)} vacio="Sin ventas en este periodo." />
      <Barras titulo="Comunas con más ventas" barras={conMonto(detalles.comunas)}
        vacio="Sin despachos en este periodo." />
    </div>
  );
}

function Cancelaciones({ cancelaciones }) {
  const total = cancelaciones.reduce((suma, causa) => suma + causa.cantidad, 0);
  if (total === 0) return <p className="dashboard-vacio">No hubo cancelaciones en este periodo.</p>;
  const barras = cancelaciones.map((causa) => ({
    nombre: causa.nombre,
    porcentaje: Math.round((causa.cantidad * 100) / total),
    detalle: plural(causa.cantidad, 'pedido'),
  }));
  return <Barras titulo={`${plural(total, 'pedido cancelado', 'pedidos cancelados')}, por causa`} barras={barras} />;
}

function Cupones({ cupones }) {
  if (cupones.length === 0) return <p className="dashboard-vacio">No se usaron cupones en este periodo.</p>;
  return (
    <div tabIndex={0} role="region" aria-label="Uso de cupones" className="dashboard-tabla-envoltorio">
      <table className="dashboard-tabla">
        <caption className="visualmente-oculto">Cupones usados en el periodo</caption>
        <thead><tr><th scope="col">Código</th><th scope="col">Usos</th><th scope="col">Descontado</th></tr></thead>
        <tbody>
          {cupones.map((cupon) => (
            <tr key={cupon.codigo}>
              <th scope="row">{cupon.codigo}</th>
              <td>{formatearNumero(cupon.usos)}</td>
              <td>{formatearMonto(cupon.descontado)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Clientes({ clientes, calificacion }) {
  const cifras = [
    ['Nuevos', clientes.nuevos, 'Primera compra en el periodo'],
    ['Recurrentes', clientes.recurrentes, 'Ya habían comprado antes'],
    ['Con cuenta', clientes.registrados, 'Compraron con su sesión iniciada'],
    ['Invitados', clientes.invitados, 'Compraron sin cuenta'],
  ];
  return (
    <>
      <dl className="dashboard-cifras">
        {cifras.map(([nombre, valor, ayuda]) => (
          <div key={nombre}>
            <dt>{nombre}</dt>
            <dd>{formatearNumero(valor)}<span>{ayuda}</span></dd>
          </div>
        ))}
        {calificacion && (
          <div>
            <dt>Calificación de la tienda</dt>
            <dd>
              {calificacion.promedio.toLocaleString('es-CL', { minimumFractionDigits: 1 })} de 5
              <span>{plural(calificacion.cantidad, 'reseña aprobada', 'reseñas aprobadas')}</span>
            </dd>
          </div>
        )}
      </dl>
    </>
  );
}

const PESTANAS = [
  { id: 'compran', nombre: 'Cómo compran' },
  { id: 'cancelaciones', nombre: 'Cancelaciones' },
  { id: 'cupones', nombre: 'Cupones' },
  { id: 'clientes', nombre: 'Clientes' },
];

// Patrón de pestañas ARIA: flechas izquierda/derecha, Inicio y Fin mueven entre pestañas
export default function DetallesDashboard({ detalles }) {
  const [activa, setActiva] = useState(PESTANAS[0].id);
  const id = useId();
  const botones = useRef({});

  const moverCon = (event) => {
    const indice = PESTANAS.findIndex((pestana) => pestana.id === activa);
    const destinos = { ArrowRight: indice + 1, ArrowLeft: indice - 1, Home: 0, End: PESTANAS.length - 1 };
    if (!(event.key in destinos)) return;
    event.preventDefault();
    const siguiente = PESTANAS[(destinos[event.key] + PESTANAS.length) % PESTANAS.length].id;
    setActiva(siguiente);
    botones.current[siguiente]?.focus();
  };

  return (
    <section className="dashboard-bloque" aria-labelledby={`${id}-titulo`}>
      <h3 id={`${id}-titulo`} className="dashboard-bloque-titulo">Más detalles</h3>
      <div role="tablist" aria-labelledby={`${id}-titulo`} className="dashboard-pestanas" onKeyDown={moverCon}>
        {PESTANAS.map((pestana) => (
          <button key={pestana.id} type="button" role="tab" id={`${id}-${pestana.id}`}
            ref={(boton) => { botones.current[pestana.id] = boton; }}
            aria-selected={activa === pestana.id} aria-controls={`${id}-${pestana.id}-panel`}
            tabIndex={activa === pestana.id ? 0 : -1} onClick={() => setActiva(pestana.id)}>
            {pestana.nombre}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`${id}-${activa}-panel`} aria-labelledby={`${id}-${activa}`} tabIndex={0}
        className="dashboard-pestana-panel">
        {activa === 'compran' && <ComoCompran detalles={detalles} />}
        {activa === 'cancelaciones' && <Cancelaciones cancelaciones={detalles.cancelaciones} />}
        {activa === 'cupones' && <Cupones cupones={detalles.cupones} />}
        {activa === 'clientes' && <Clientes clientes={detalles.clientes} calificacion={detalles.calificacion} />}
      </div>
    </section>
  );
}
