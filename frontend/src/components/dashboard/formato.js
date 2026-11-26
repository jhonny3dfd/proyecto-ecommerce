// Formatos del dashboard (RF-03.1): montos en pesos sin decimales y fechas AAAA-MM-DD sin pasar por la zona horaria
const pesos = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });
const numero = new Intl.NumberFormat('es-CL');
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
  'noviembre', 'diciembre'];
const MESES_CORTOS = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];

export const formatearMonto = (monto) => pesos.format(Number(monto) || 0);
export const formatearNumero = (valor) => numero.format(Number(valor) || 0);

// Plural simple: plural(2, 'pedido') -> '2 pedidos'; plural(1, 'cotización nueva', 'cotizaciones nuevas')
export const plural = (cantidad, singular, varios = `${singular}s`) =>
  `${formatearNumero(cantidad)} ${cantidad === 1 ? singular : varios}`;

// '2026-11-05' -> { ano: 2026, mes: 11, dia: 5 }
export const partesFecha = (texto) => {
  const [ano, mes, dia] = String(texto).split('-').map(Number);
  return { ano, mes, dia };
};

export const textoFecha = (texto) => {
  const { ano, mes, dia } = partesFecha(texto);
  return `${dia} de ${MESES[mes - 1]} de ${ano}`;
};

// El rango del periodo para leer: "1 al 5 de noviembre de 2026", "25 de octubre al 2 de noviembre de 2026"
export const textoRango = (desde, hasta) => {
  if (!desde) return `hasta el ${textoFecha(hasta)}`;
  const a = partesFecha(desde);
  const b = partesFecha(hasta);
  if (a.ano === b.ano && a.mes === b.mes) {
    return a.dia === b.dia ? textoFecha(hasta) : `${a.dia} al ${b.dia} de ${MESES[b.mes - 1]} de ${b.ano}`;
  }
  if (a.ano === b.ano) return `${a.dia} de ${MESES[a.mes - 1]} al ${b.dia} de ${MESES[b.mes - 1]} de ${b.ano}`;
  return `${textoFecha(desde)} al ${textoFecha(hasta)}`;
};

// Etiqueta corta del eje del gráfico: '05/11' por día o 'nov 2026' por mes
export const etiquetaPunto = (texto, agrupacion) => {
  const { ano, mes, dia } = partesFecha(texto);
  if (agrupacion === 'MES') return `${MESES_CORTOS[mes - 1]} ${ano}`;
  return `${String(dia).padStart(2, '0')}/${String(mes).padStart(2, '0')}`;
};

const aTexto = (fecha) => [fecha.getFullYear(), String(fecha.getMonth() + 1).padStart(2, '0'),
  String(fecha.getDate()).padStart(2, '0')].join('-');

// El backend solo manda los días (o meses) con ventas: se completan con 0 para que el gráfico no salte días
export function completarSerie(serie, { desde, hasta, agrupacion }) {
  const porFecha = new Map(serie.map((punto) => [punto.fecha, punto]));
  const inicioTexto = desde || serie[0]?.fecha;
  if (!inicioTexto) return [];
  const inicio = partesFecha(inicioTexto);
  const fin = partesFecha(hasta);
  const puntos = [];
  if (agrupacion === 'MES') {
    for (let fecha = new Date(inicio.ano, inicio.mes - 1, 1); fecha <= new Date(fin.ano, fin.mes - 1, 1);
      fecha.setMonth(fecha.getMonth() + 1)) {
      const clave = aTexto(fecha);
      puntos.push(porFecha.get(clave) || { fecha: clave, total: 0, pedidos: 0 });
    }
  } else {
    for (let fecha = new Date(inicio.ano, inicio.mes - 1, inicio.dia); fecha <= new Date(fin.ano, fin.mes - 1, fin.dia);
      fecha.setDate(fecha.getDate() + 1)) {
      const clave = aTexto(fecha);
      puntos.push(porFecha.get(clave) || { fecha: clave, total: 0, pedidos: 0 });
    }
  }
  return puntos;
}
