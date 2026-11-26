// Suscripciones (pedido de un cliente, opcional): lo mismo que calcula el servidor (domain/suscripciones.py), solo para
// mostrarlo antes de pagar. El total que se cobra lo calcula siempre el servidor.

// Pesos de descuento del suscriptor sobre lo que queda después del cupón; nunca más que esa base (RF-04.1)
export function descuentoSuscriptor(base, porcentaje) {
  const monto = Math.max(0, Number(base) || 0);
  const pct = Number(porcentaje) || 0;
  if (pct <= 0) return 0;
  return Math.min(monto, Math.round((monto * pct) / 100));
}

export function frecuenciaTexto(semanas) {
  return Number(semanas) === 1 ? 'Cada semana' : `Cada ${semanas} semanas`;
}

export const formatoPesos = (valor) => `$${Math.round(Number(valor) || 0).toLocaleString('es-CL')}`;

// "11 de noviembre de 2026" a partir de "2026-11-11" (sin pasar por la zona horaria del navegador)
export const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre',
  'noviembre', 'diciembre'];
export function fechaLarga(texto) {
  if (!texto) return '';
  const [anio, mes, dia] = String(texto).slice(0, 10).split('-').map(Number);
  return `${dia} de ${MESES[mes - 1]} de ${anio}`;
}

// Cómo paga cada ciclo (los códigos de domain/medios_pago.py)
const NOMBRES_MEDIO_PAGO = {
  TRANSBANK: 'Webpay (Transbank)',
  MERCADO_PAGO: 'Mercado Pago',
  TRANSFERENCIA: 'Transferencia bancaria'
};
export const nombreMedioPago = (codigo) => NOMBRES_MEDIO_PAGO[codigo] || codigo || '';

// Igual que ETIQUETAS_ESTADO_SUSCRIPCION en domain/suscripciones.py
export const ESTADOS_SUSCRIPCION = [
  ['ACTIVA', 'Activas'],
  ['PENDIENTE', 'Esperando el primer pago'],
  ['PAUSADA', 'Pausadas'],
  ['CANCELADA', 'Canceladas']
];

// Lo que se lista en la tarjeta del plan: los beneficios que escribió el admin y, al final, los que da el plan solo
export function beneficiosDelPlan(plan) {
  const lista = [...(plan?.beneficios || [])];
  if (plan?.envio_gratis) lista.push(plan.envio_gratis_compras ? 'Envío gratis en tus entregas y en todas tus compras' : 'Envío gratis en tus entregas');
  if (plan?.descuento > 0) lista.push(`${plan.descuento}% de descuento en todas tus compras en la tienda`);
  return lista;
}

// "Molienda: Grano · Peso: 250 g"
export function textoVariante(atributos) {
  return Object.entries(atributos || {}).filter(([, valor]) => valor !== '' && valor != null)
    .map(([clave, valor]) => `${clave.charAt(0).toUpperCase()}${clave.slice(1)}: ${valor}`).join(' · ');
}

// "AAAA-MM-DD" de hoy más `dias`, con la fecha local del navegador (el servidor fija la fecha real)
export function fechaEnDias(dias, desde = new Date()) {
  const fecha = new Date(desde.getFullYear(), desde.getMonth(), desde.getDate() + Number(dias || 0));
  const dos = (n) => String(n).padStart(2, '0');
  return `${fecha.getFullYear()}-${dos(fecha.getMonth() + 1)}-${dos(fecha.getDate())}`;
}

// Acciones de Mis suscripciones: el texto del botón y la confirmación (el servidor dice cuáles se permiten)
export const ACCIONES_SUSCRIPCION = {
  adelantar: { boton: 'Recibirla antes', confirmar: '¿Adelantar tu próxima entrega a hoy? Se crea el pedido ahora y lo pagas enseguida; las siguientes se cuentan desde hoy.' },
  saltar: { boton: 'Saltar la próxima entrega', confirmar: '¿Saltar tu próxima entrega? Si ya tiene un pedido sin pagar, se cancela; la siguiente llega en la fecha de siempre.' },
  pausar: { boton: 'Pausar', confirmar: '¿Pausar tu suscripción? No recibirás entregas hasta que la reanudes, y un pedido sin pagar se cancela (uno ya pagado llega igual).' },
  reanudar: { boton: 'Reanudar', confirmar: null },
  cancelar: { boton: 'Cancelar suscripción', confirmar: '¿Cancelar tu suscripción? No se puede deshacer: para volver tendrás que suscribirte de nuevo.' }
};
