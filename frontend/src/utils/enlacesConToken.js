// Los enlaces de los correos traen un token en la URL: el de nueva contraseña (uid y token) y el de la reseña (t).
// main.jsx los guarda y los quita de la barra de direcciones antes de montar la app: así la analítica (si se
// aceptaron las cookies) nunca los recibe. Dentro de la tienda se navega a la ruta sin token, guardándolo antes.
const ENLACES = {
  '/restablecer-contrasena': ['uid', 'token'],
  '/resena': ['t'],
};

const clave = (ruta) => `enlace_con_token:${ruta}`;

// Respaldo si el navegador bloquea sessionStorage; sessionStorage deja recargar la página sin perder el enlace
const enMemoria = {};

export function guardarTokensDeEnlace(ruta, valores) {
  enMemoria[ruta] = valores;
  try {
    sessionStorage.setItem(clave(ruta), JSON.stringify(valores));
  } catch {
    // Queda solo en memoria
  }
}

export function capturarTokensDeEnlace(ubicacion = window.location, historial = window.history) {
  const nombres = ENLACES[ubicacion.pathname];
  if (!nombres) return;
  const parametros = new URLSearchParams(ubicacion.search);
  const valores = Object.fromEntries(nombres.map((nombre) => [nombre, parametros.get(nombre)]));
  if (nombres.some((nombre) => !valores[nombre])) return;
  guardarTokensDeEnlace(ubicacion.pathname, valores);
  historial.replaceState(historial.state, '', ubicacion.pathname);
}

export function leerTokensDeEnlace(ruta) {
  if (enMemoria[ruta]) return enMemoria[ruta];
  try {
    const guardados = JSON.parse(sessionStorage.getItem(clave(ruta)) || 'null');
    if (guardados && (ENLACES[ruta] || []).every((nombre) => guardados[nombre])) return guardados;
  } catch {
    // Sin enlace guardado
  }
  return null;
}

export function olvidarTokensDeEnlace(ruta) {
  delete enMemoria[ruta];
  try {
    sessionStorage.removeItem(clave(ruta));
  } catch {
    // Nada que borrar
  }
}
