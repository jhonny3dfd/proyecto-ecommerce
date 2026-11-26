// Redes sociales de la tienda (Configuración > Contacto y Redes). Se guardan como enlaces; el pie y Sobre mí las
// muestran solo si el admin las cargó, con el usuario cuando el enlace lo trae.
export const REDES_SOCIALES = [
  { campo: 'facebook_url', nombre: 'Facebook', icono: 'M22 12a10 10 0 1 0-11.56 9.88v-6.99H7.9V12h2.54V9.8c0-2.5 1.49-3.89 3.77-3.89 1.09 0 2.23.19 2.23.19v2.46h-1.26c-1.24 0-1.63.77-1.63 1.56V12h2.77l-.44 2.89h-2.33v6.99A10 10 0 0 0 22 12z' },
  { campo: 'x_url', nombre: 'X', icono: 'M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932 6.064-6.933zm-1.29 19.49h2.039L6.486 3.24H4.298z' },
  { campo: 'youtube_url', nombre: 'YouTube', icono: 'M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.6 12 3.6 12 3.6s-7.5 0-9.4.5A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.5 9.4.5 9.4.5s7.5 0 9.4-.5a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8zM9.6 15.6V8.4l6.2 3.6z' },
  { campo: 'tiktok_url', nombre: 'TikTok', icono: 'M16.7 0h-4.1v16.5a3.5 3.5 0 1 1-3-3.5V8.8a7.7 7.7 0 1 0 7.1 7.7V8.1a10 10 0 0 0 5.8 1.9V5.9A5.9 5.9 0 0 1 16.7 0z' },
];

// Rutas de X que no son un perfil (x.com/home, x.com/intent/...)
const RUTAS_X = new Set(['home', 'i', 'intent', 'share', 'search', 'explore', 'hashtag', 'settings']);
const USUARIO = /^[\w.]{1,50}$/;

// "@usuario" sacado del enlace (tiktok.com/@usuario, youtube.com/@canal, x.com/usuario); null si no lo trae
export function usuarioDeRed(campo, enlace) {
  let primero;
  try {
    const url = new URL(String(enlace || '').trim());
    primero = decodeURIComponent(url.pathname.split('/').filter(Boolean)[0] || '');
  } catch {
    return null;
  }
  if (campo === 'tiktok_url' || campo === 'youtube_url') {
    const usuario = primero.startsWith('@') ? primero.slice(1) : '';
    return USUARIO.test(usuario) ? `@${usuario}` : null;
  }
  if (campo === 'x_url') {
    const usuario = primero.replace(/^@/, '');
    return USUARIO.test(usuario) && !RUTAS_X.has(usuario.toLowerCase()) ? `@${usuario}` : null;
  }
  return null;
}

// Las redes que cargó el admin, con lo que se muestra de cada una
export function redesDeLaTienda(configuracion) {
  return REDES_SOCIALES.filter(red => configuracion?.[red.campo]).map(red => ({
    ...red, url: configuracion[red.campo], usuario: usuarioDeRed(red.campo, configuracion[red.campo])
  }));
}
