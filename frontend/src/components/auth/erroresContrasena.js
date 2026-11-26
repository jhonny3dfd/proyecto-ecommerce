// El backend responde { campo: [mensajes] } (password, password2 y, al cambiarla, actual) o { enlace: [...] } si el
// enlace del correo ya no sirve. Cada mensaje va bajo su campo; lo demás, arriba del formulario.
export function leerErroresContrasena(error, nombresCampos, textoFallo) {
  const data = error.response?.data;
  if (!error.response) {
    return { general: 'No pudimos conectar con la tienda. Revisa tu conexión e inténtalo de nuevo.', campos: {} };
  }
  if (error.response.status === 429) {
    return { general: 'Hiciste muchos intentos seguidos. Espera un rato e inténtalo de nuevo.', campos: {} };
  }
  if (error.response.status !== 400 || !data || typeof data !== 'object') {
    return { general: textoFallo, campos: {} };
  }
  if (data.enlace) return { general: '', campos: {}, enlaceInvalido: true };
  const campos = {};
  nombresCampos.forEach((nombre) => {
    if (data[nombre]) campos[nombre] = [].concat(data[nombre]).join(' ');
  });
  return { general: 'Revisa los datos marcados.', campos };
}
