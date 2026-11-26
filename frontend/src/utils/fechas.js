// "23 de octubre de 2026"
export const formatearFechaLarga = (fecha) =>
  new Date(fecha).toLocaleDateString('es-CL', { dateStyle: 'long' });
