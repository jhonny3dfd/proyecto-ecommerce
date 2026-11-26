import { useMemo, useSyncExternalStore } from 'react';
import { interpretarCarrito, leerSnapshotCarrito } from '../components/carrito';

const suscribirCarrito = (actualizar) => {
  const alCambiarStorage = (event) => {
    if (event.storageArea === localStorage
      && (event.key === 'carrito_local' || event.key === null)) {
      actualizar();
    }
  };
  window.addEventListener('carritoActualizado', actualizar);
  window.addEventListener('storage', alCambiarStorage);
  return () => {
    window.removeEventListener('carritoActualizado', actualizar);
    window.removeEventListener('storage', alCambiarStorage);
  };
};

export default function useCarrito() {
  // Un string estable evita que React interprete cada lectura como otro carrito.
  const snapshot = useSyncExternalStore(suscribirCarrito, leerSnapshotCarrito);
  return useMemo(() => interpretarCarrito(snapshot), [snapshot]);
}
