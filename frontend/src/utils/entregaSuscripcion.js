// Entrega de una suscripción (pedido de un cliente, opcional): las mismas reglas del checkout (RF-02.3); el servidor
// las vuelve a validar. Retiro en sucursal del courier no se ofrece en las suscripciones (fase 1).

export const NOMBRES_TIPO_ENTREGA = {
  DOMICILIO: 'A domicilio',
  RETIRO_LOCAL: 'Retiro en el local',
  ENTREGA_COORDINADA: 'Entrega coordinada'
};

export const DIRECCION_VACIA = { calle: '', numero: '', dpto_casa: '', comuna: '', ciudad: '' };

export const ENTREGA_VACIA = {
  tipo: '', proveedor: '', direccionId: 'nueva', direccion: DIRECCION_VACIA, nombre: '', telefono: ''
};

export function tiposDeEntrega(config) {
  return [
    ...((config?.couriers || []).length > 0 ? ['DOMICILIO'] : []),
    ...(config?.retiro_en_local_activo ? ['RETIRO_LOCAL'] : []),
    ...(config?.entrega_coordinada_activa ? ['ENTREGA_COORDINADA'] : [])
  ];
}

// Desde lo guardado en una suscripción, para editarla
export function entregaDesdeSuscripcion(entrega, config) {
  const proveedor = entrega?.proveedor_logistico || '';
  const tipo = proveedor === 'RETIRO_LOCAL' || proveedor === 'ENTREGA_COORDINADA' ? proveedor : 'DOMICILIO';
  return {
    ...ENTREGA_VACIA,
    tipo: tiposDeEntrega(config).includes(tipo) ? tipo : '',
    proveedor: tipo === 'DOMICILIO' ? proveedor : '',
    direccion: { ...DIRECCION_VACIA, ...(entrega?.direccion_envio_snapshot || {}) },
    nombre: entrega?.nombre_destinatario || '',
    telefono: entrega?.telefono_destinatario || ''
  };
}

export const direccionElegida = (valor, direcciones) => {
  if (valor.direccionId === 'nueva') return valor.direccion;
  const guardada = direcciones.find(d => d.id === valor.direccionId);
  return guardada ? {
    calle: guardada.calle, numero: guardada.calle_numero, dpto_casa: guardada.dpto_casa || '',
    comuna: guardada.comuna, ciudad: guardada.ciudad || '', region: guardada.region || ''
  } : DIRECCION_VACIA;
};

// La comuna a cotizar (solo a domicilio)
export const comunaACotizar = (valor, direcciones) => valor.tipo === 'DOMICILIO'
  ? String(direccionElegida(valor, direcciones).comuna || '').trim() : '';

// Lo que falta para poder suscribirse; '' si está completo
export function faltaEnEntrega(valor, direcciones, cotizacion) {
  if (!valor.tipo) return 'Elige cómo quieres recibir tus entregas.';
  const direccion = direccionElegida(valor, direcciones);
  if (valor.tipo === 'DOMICILIO') {
    if (!direccion.calle?.trim() || !direccion.numero?.trim() || !direccion.comuna?.trim()) {
      return 'Completa la calle, el número y la comuna.';
    }
    if (!cotizacion?.opcion) return cotizacion?.cargando ? 'Calculando el despacho...' : (cotizacion?.error || 'No hay despacho disponible para esa comuna.');
  }
  if (valor.tipo === 'ENTREGA_COORDINADA') {
    const alguna = ['calle', 'numero', 'comuna'].some(campo => direccion[campo]?.trim());
    if (alguna && (!direccion.calle?.trim() || !direccion.comuna?.trim())) {
      return 'Completa la calle y la comuna, o deja la dirección vacía para acordarla con la tienda.';
    }
  }
  if (!valor.nombre.trim() || !valor.telefono.trim()) return 'Indica el nombre y el teléfono de quien recibe.';
  return '';
}

// Lo que se envía al servidor (mismo formato que la entrega del checkout)
export function entregaParaServidor(valor, direcciones, cotizacion) {
  const direccion = direccionElegida(valor, direcciones);
  const limpia = Object.fromEntries(Object.entries(direccion).map(([c, v]) => [c, String(v || '').trim()]).filter(([, v]) => v));
  return {
    proveedor_logistico: valor.tipo === 'DOMICILIO' ? (cotizacion?.opcion?.proveedor || valor.proveedor) : valor.tipo,
    direccion_envio_snapshot: valor.tipo === 'RETIRO_LOCAL' ? {} : limpia,
    nombre_destinatario: valor.nombre.trim(),
    telefono_destinatario: valor.telefono.trim()
  };
}

// Lo que cuesta cada entrega con esa forma; null si aún no se sabe
export function costoEntrega(valor, config, cotizacion) {
  if (valor.tipo === 'RETIRO_LOCAL') return 0;
  if (valor.tipo === 'ENTREGA_COORDINADA') return Number(config?.costo_entrega_coordinada) || 0;
  if (valor.tipo === 'DOMICILIO') return cotizacion?.opcion ? cotizacion.opcion.precio : null;
  return null;
}

