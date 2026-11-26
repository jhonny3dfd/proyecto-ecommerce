import { useEffect, useState } from 'react';
import clienteAxios from '../components/auth/axiosConfig';
import { comunaACotizar } from '../utils/entregaSuscripcion';

// Cotiza el despacho a domicilio de una entrega (el producto elegido por las unidades del plan). `opcion`: la del
// courier elegido o, si no eligió, la primera
export function useCotizacionEntrega(valor, direcciones, item) {
  const comuna = comunaACotizar(valor, direcciones);
  const clave = comuna && item?.producto_mongo_id && item?.variante_sku
    ? JSON.stringify([comuna.toUpperCase(), item.producto_mongo_id, item.variante_sku, item.cantidad]) : null;
  const [resultado, setResultado] = useState({ clave: null, opciones: [], error: '' });

  useEffect(() => {
    if (!clave) return;
    const [destino, producto, sku, cantidad] = JSON.parse(clave);
    let vigente = true;
    clienteAxios.post('ventas/logistica/cotizar/', {
      destino, items: [{ producto_mongo_id: producto, variante_sku: sku, cantidad }]
    }).then(({ data }) => {
      if (vigente) setResultado({ clave, error: '', opciones: (data.opciones || []).map(o => ({
        proveedor: o.proveedor, nombre: o.tiempo_estimado ? `${o.nombre} - ${o.tiempo_estimado}` : o.nombre,
        precio: Number(o.precio) || 0
      })) });
    }).catch(error => {
      if (vigente) setResultado({ clave, opciones: [], error: error.response?.data?.error || 'No se pudo calcular el costo de envío.' });
    });
    return () => { vigente = false; };
  }, [clave]);

  if (!clave) return { cargando: false, opciones: [], opcion: null, error: '' };
  if (resultado.clave !== clave) return { cargando: true, opciones: [], opcion: null, error: '' };
  const opcion = resultado.opciones.find(o => o.proveedor === valor.proveedor) || resultado.opciones[0] || null;
  return { cargando: false, opciones: resultado.opciones, opcion, error: resultado.error };
}

