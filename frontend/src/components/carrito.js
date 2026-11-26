import clienteAxios from './auth/axiosConfig';

export const leerSnapshotCarrito = () => localStorage.getItem('carrito_local');

export const interpretarCarrito = (snapshot) => {
  try {
    const items = JSON.parse(snapshot);
    if (!Array.isArray(items)) return [];
    return items
      .filter(item => item && typeof item === 'object'
        && Number.isFinite(Number(item.precio)) && Number(item.precio) >= 0
        && Number.isInteger(Number(item.cantidad)) && Number(item.cantidad) > 0)
      .map(item => ({ ...item, precio: Number(item.precio), cantidad: Number(item.cantidad) }));
  } catch {
    return [];
  }
};

// RN-03: compara el carrito con el stock y los precios vigentes. No reserva nada:
// el backend vuelve a validar al crear la orden y al confirmar el pago.
export const validarCarrito = async (items) => {
  const { data } = await clienteAxios.post('ventas/carrito/validar/', {
    items: items.map(item => ({ producto_mongo_id: item.id, variante_sku: item.sku, cantidad: item.cantidad }))
  });
  return data;
};

const sincronizarCarrito = async (items) => {
  if (localStorage.getItem('access_token')) {
    try {
      await clienteAxios.post('ventas/carrito/', { items });
    } catch (error) {
      console.error('No se pudo sincronizar el carrito con la base de datos:', error);
    }
  }
};

// La actualización local es inmediata; una escritura idéntica no dispara otra validación.
export const guardarCarrito = async (items) => {
  const snapshot = JSON.stringify(items);
  if (localStorage.getItem('carrito_local') !== snapshot) {
    localStorage.setItem('carrito_local', snapshot);
    window.dispatchEvent(new Event('carritoActualizado'));
  }
  await sincronizarCarrito(items);
};

export const vaciarCarrito = async () => {
  localStorage.removeItem('carrito_local');
  window.dispatchEvent(new Event('carritoActualizado'));
  await sincronizarCarrito([]);
};

// Ajusta el carrito a lo que se puede comprar ahora: quita lo agotado, baja cantidades y
// actualiza precios. Devuelve el carrito ajustado y un aviso por cada cambio.
export const ajustarCarrito = (items, revision) => {
  const lineas = new Map(revision.items.map(linea => [`${linea.producto_mongo_id}|${linea.variante_sku}`, linea]));
  const avisos = [];
  const ajustado = [];
  items.forEach(item => {
    const linea = lineas.get(`${item.id}|${item.sku}`);
    if (!linea) {
      ajustado.push(item);
      return;
    }
    if (['NO_DISPONIBLE', 'SIN_STOCK', 'SUSCRIPCION_REQUERIDA'].includes(linea.problema)) {
      avisos.push(`${linea.mensaje} Lo quitamos de tu carrito.`);
      return;
    }
    let actualizado = item;
    if (linea.problema === 'STOCK_INSUFICIENTE') {
      avisos.push(`${linea.mensaje} Ajustamos la cantidad.`);
      actualizado = { ...actualizado, cantidad: linea.disponible };
    }
    if (linea.precio !== null && Number(linea.precio) !== Number(item.precio)) {
      avisos.push(`El precio de ${linea.nombre} cambió a $${Number(linea.precio).toLocaleString('es-CL')}.`);
      actualizado = { ...actualizado, precio: linea.precio };
    }
    ajustado.push(actualizado);
  });
  return { items: ajustado, avisos };
};
