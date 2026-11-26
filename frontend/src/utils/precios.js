export const formatearPrecioCLP = (valor) => {
  if (valor === undefined || valor === null || isNaN(valor)) return '';
  return `$${Math.round(Number(valor)).toLocaleString('es-CL')}`;
};

export function obtenerDatosPrecioYStock(variantes = []) {
  if (!variantes || variantes.length === 0) {
    return {
      agotado: true,
      textoPrecio: '',
      precioTachado: '',
      tieneOferta: false,
    };
  }

  // Si ninguna variante tiene stock, se indica "Agotado"
  const stockTotal = variantes.reduce((acc, v) => acc + (Number(v.stock) || 0), 0);
  const agotado = stockTotal <= 0;

  const datosVariantes = variantes.map((v) => {
    const normal = Number(v.precio) || 0;
    const tieneOfertaVar =
      v.precio_oferta != null &&
      Number(v.precio_oferta) > 0 &&
      Number(v.precio_oferta) < normal;
    const final = tieneOfertaVar ? Number(v.precio_oferta) : normal;
    return { normal, final, tieneOfertaVar };
  });

  const preciosFinales = datosVariantes.map((d) => d.final);
  const minFinal = Math.min(...preciosFinales);
  const maxFinal = Math.max(...preciosFinales);
  const preciosDifieren = minFinal !== maxFinal;

  const varianteMenor = datosVariantes.find((d) => d.final === minFinal);
  const tieneOferta = Boolean(varianteMenor?.tieneOfertaVar);

  const prefijo = preciosDifieren ? 'Desde ' : '';
  const textoPrecio = `${prefijo}${formatearPrecioCLP(minFinal)}`;
  const precioTachado = tieneOferta ? formatearPrecioCLP(varianteMenor.normal) : '';

  return {
    agotado,
    textoPrecio,
    precioTachado,
    tieneOferta,
  };
}

// Precio más bajo que paga el comprador (con oferta si la hay); sirve para ordenar el catálogo por precio
export function precioMinimoVigente(variantes = []) {
  const precios = (variantes || []).map((v) => {
    const normal = Number(v.precio) || 0;
    const oferta = Number(v.precio_oferta);
    return oferta > 0 && oferta < normal ? oferta : normal;
  });
  return precios.length ? Math.min(...precios) : Infinity;
}
