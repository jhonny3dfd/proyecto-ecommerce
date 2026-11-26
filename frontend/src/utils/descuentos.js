// Vista previa de los descuentos en el checkout: el mismo cálculo que domain/promociones.py. El cobro lo decide el
// servidor al pagar, con el subtotal del catálogo; esto solo muestra al comprador lo que va a pasar.
// Una regla: { tipo_descuento, valor_descuento, monto_minimo, umbral_envio_gratis } (como las envía el servidor)

const numero = (valor) => (valor === null || valor === undefined || valor === '' ? null : Number(valor));

export const cumpleMinimo = (regla, subtotal) => numero(regla.monto_minimo) === null || subtotal >= numero(regla.monto_minimo);

// Nunca más que el subtotal, y cero bajo el monto mínimo
export const montoDescuento = (regla, subtotal) => {
  if (!cumpleMinimo(regla, subtotal)) return 0;
  const valor = Number(regla.valor_descuento);
  const descuento = regla.tipo_descuento === 'PORCENTAJE' ? subtotal * valor / 100 : valor;
  return Math.max(0, Math.min(descuento, subtotal));
};

export const daEnvioGratis = (regla, subtotal) => {
  const umbral = numero(regla.umbral_envio_gratis);
  return cumpleMinimo(regla, subtotal) && umbral !== null && subtotal >= umbral;
};

const ahorro = (regla, subtotal, costoEnvio) => montoDescuento(regla, subtotal) + (daEnvioGratis(regla, subtotal) ? costoEnvio : 0);

// No se suman: gana la que más ahorra; con el mismo ahorro, la primera (el código escrito va primero)
export const elegirDescuento = (reglas, subtotal, costoEnvio) => {
  let mejor = null;
  let mejorAhorro = 0;
  reglas.forEach((regla) => {
    const valor = ahorro(regla, subtotal, costoEnvio);
    if (valor > mejorAhorro) {
      mejor = regla;
      mejorAhorro = valor;
    }
  });
  return mejor;
};

// El automático más cercano que todavía no alcanza: para avisar "te faltan $X"
export const siguienteAutomatico = (automaticos, subtotal) => automaticos
  .filter((regla) => !cumpleMinimo(regla, subtotal))
  .sort((a, b) => numero(a.monto_minimo) - numero(b.monto_minimo))[0] || null;
