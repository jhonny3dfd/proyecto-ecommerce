// Compra como empresa: datos para la factura. El backend los vuelve a validar (domain/empresa.py)

export const CAMPOS_EMPRESA = ['razon_social', 'rut', 'giro', 'direccion', 'correo'];

export const EMPRESA_VACIA = Object.fromEntries(CAMPOS_EMPRESA.map(campo => [campo, '']));

// Módulo 11: los dígitos, de derecha a izquierda, se multiplican por 2, 3, 4, 5, 6, 7, 2, 3...
const digitoVerificador = (cuerpo) => {
  const suma = [...cuerpo].reverse().reduce((total, digito, i) => total + Number(digito) * (2 + (i % 6)), 0);
  const resto = 11 - (suma % 11);
  return resto === 11 ? '0' : resto === 10 ? 'K' : String(resto);
};

// '76123456-0' o '761234560' -> '76.123.456-0'; null si el RUT no es válido
export function normalizarRut(texto) {
  const limpio = String(texto || '').replace(/[.\-\s]/g, '').toUpperCase();
  const coincidencia = limpio.match(/^(\d{7,8})([\dK])$/);
  if (!coincidencia || digitoVerificador(coincidencia[1]) !== coincidencia[2]) return null;
  const cuerpo = String(Number(coincidencia[1])).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${cuerpo}-${coincidencia[2]}`;
}

// { campo: mensaje } con lo que falta o está mal; vacío si los datos sirven para la factura
export function validarDatosEmpresa(datos) {
  const errores = {};
  CAMPOS_EMPRESA.forEach(campo => {
    if (!String(datos[campo] || '').trim()) errores[campo] = 'Este dato es obligatorio para la factura.';
  });
  if (!errores.rut && !normalizarRut(datos.rut)) {
    errores.rut = 'El RUT no es válido. Revisa los números y el dígito verificador (ej. 76.123.456-0).';
  }
  if (!errores.correo && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(datos.correo.trim())) {
    errores.correo = 'Escribe un correo válido.';
  }
  return errores;
}
