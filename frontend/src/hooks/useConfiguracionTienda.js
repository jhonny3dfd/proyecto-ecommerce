import { useEffect, useState } from 'react';
import clienteAxios from '../components/auth/axiosConfig';

// Configuración pública de la tienda (nombre, logo, favicon, textos de la landing...). Se pide una sola vez y la
// comparten el header, el footer y la landing; recargarConfiguracion() la vuelve a pedir tras editarla.
let configuracion = null;
let peticion = null;
let cargando = false;
const oyentes = new Set();

function cargar(refrescar = false) {
  // El catálogo vuelve a consultar al entrar, pero comparte una lectura ya en
  // curso con App, header y footer durante el montaje inicial.
  if (refrescar && !cargando) peticion = null;
  if (!peticion) {
    cargando = true;
    peticion = clienteAxios.get('configuracion/')
      .then(({ data }) => {
        configuracion = Array.isArray(data) ? data[0] : data;
        aplicarIdentidad(configuracion);
        oyentes.forEach((avisar) => avisar(configuracion));
        return configuracion;
      })
      .catch((error) => {
        // Sin configuración la tienda igual se muestra, con sus textos por defecto; se reintenta al volver a montar
        peticion = null;
        oyentes.forEach((avisar) => avisar({}));
        throw error;
      })
      .finally(() => { cargando = false; });
  }
  return peticion;
}

export function recargarConfiguracion() {
  peticion = null;
  return cargar();
}

// Presentación que elige el admin (pedido de un cliente, apagada por defecto): marcas en <html> que el CSS usa en
// toda la tienda. data-fotos="completas" (fotos sin recortar), data-ficha="horizontal" (ficha con la foto apaisada)
// y data-logo="grande" (logo más grande en el computador). Apagada, la marca se quita
const MARCAS_PRESENTACION = {
  fotos: ['fotos_completas', 'completas'],
  ficha: ['ficha_horizontal', 'horizontal'],
  logo: ['logo_grande', 'grande'],
};

function aplicarPresentacion(config) {
  const raiz = document.documentElement;
  Object.entries(MARCAS_PRESENTACION).forEach(([marca, [campo, valor]]) => {
    if (config[campo]) raiz.dataset[marca] = valor;
    else delete raiz.dataset[marca];
  });
}

// Favicon del negocio (RF-01.2) y presentación; cada vista conserva su título descriptivo.
function aplicarIdentidad(config) {
  if (!config) return;
  aplicarPresentacion(config);
  if (config.favicon) {
    let icono = document.querySelector('link[rel="icon"]');
    if (!icono) {
      icono = document.createElement('link');
      icono.rel = 'icon';
      document.head.appendChild(icono);
    }
    icono.removeAttribute('type');
    icono.href = config.favicon;
  }
}

export default function useConfiguracionTienda({ refrescar = false } = {}) {
  const [valor, setValor] = useState(configuracion);

  useEffect(() => {
    oyentes.add(setValor);
    cargar(refrescar).catch((error) => console.error('No se pudo cargar la configuración de la tienda:', error));
    return () => oyentes.delete(setValor);
  }, [refrescar]);

  return valor;
}
