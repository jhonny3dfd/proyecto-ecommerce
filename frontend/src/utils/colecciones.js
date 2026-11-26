// Colecciones de todos los productos activos (publicados o en borrador), sin repetir aunque cambien las mayúsculas
// o los espacios. Mismo criterio que limpiar_colecciones del dominio: se ordenan antes de deduplicar, así que gana
// siempre la misma escritura (con mayúscula antes que sin ella), la misma que muestra el filtro del catálogo.
export function coleccionesDelInventario(productos) {
  const todas = (Array.isArray(productos) ? productos : [])
    .filter(p => p && p.activo !== false)
    .flatMap(p => (Array.isArray(p.colecciones) ? p.colecciones : []))
    .filter(col => typeof col === 'string' && col.trim())
    .map(col => col.trim())
    .sort();
  const vistas = new Set();
  return todas.filter(col => {
    const clave = col.toLowerCase();
    if (vistas.has(clave)) return false;
    vistas.add(clave);
    return true;
  });
}
