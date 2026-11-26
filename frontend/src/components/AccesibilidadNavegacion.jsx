import { useEffect, useRef } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';

const TITULOS = {
  '/': 'Inicio', '/catalogo': 'Catálogo', '/checkout': 'Finalizar compra',
  '/login': 'Acceso y registro', '/seguimiento': 'Seguimiento de pedido',
  '/mis-direcciones': 'Mis direcciones', '/mis-pedidos': 'Mis pedidos',
  '/pago-exitoso': 'Resultado del pago', '/pedido-recibido': 'Pedido recibido',
  '/pago-cancelado': 'Pago cancelado', '/pago-rechazado': 'Pago rechazado',
  '/admin': 'Panel de administración', '/variantes': 'Selección de variantes', '/resena': 'Deja tu reseña',
  '/recuperar-contrasena': 'Recuperar contraseña', '/restablecer-contrasena': 'Nueva contraseña',
  '/cambiar-contrasena': 'Cambiar contraseña',
  '/mi-cumpleanos': 'Mi cumpleaños',
  '/suscripcion': 'Suscripciones', '/mis-suscripciones': 'Mis suscripciones',
};

// Rutas con un id: el título va por su comienzo
const TITULOS_POR_PREFIJO = [
  ['/mis-suscripciones/pagar/', 'Pagar mi entrega'], ['/suscripcion/', 'Suscribirme'],
];
const tituloPorPrefijo = (ruta) => TITULOS_POR_PREFIJO.find(([prefijo]) => ruta.startsWith(prefijo))?.[1];

export default function AccesibilidadNavegacion() {
  const { pathname, hash } = useLocation();
  const tipoNavegacion = useNavigationType();
  const configuracion = useConfiguracionTienda();
  const rutaAnterior = useRef(null);
  const rutaDesplazada = useRef(null);
  const cargando = configuracion === null;

  // Una página nueva parte desde arriba: el navegador conserva la posición de la anterior en una aplicación de una
  // sola página. Se respeta el "Atrás" y el "Adelante" (POP), donde el navegador recupera la posición, y los enlaces
  // con ancla (/#nosotros), que bajan solos a su sección. Los filtros del catálogo solo cambian la query: no suben
  useEffect(() => {
    const anterior = rutaDesplazada.current;
    rutaDesplazada.current = pathname;
    if (anterior === null || anterior === pathname || tipoNavegacion === 'POP' || hash) return;
    window.scrollTo(0, 0);
  }, [pathname, hash, tipoNavegacion]);

  useEffect(() => {
    const cambioRuta = rutaAnterior.current !== pathname;
    const inicial = rutaAnterior.current === null;
    // Producto y página legal ponen su título al terminar la consulta. Una actualización
    // posterior de la configuración no debe sustituir esos metadatos específicos.
    const dinamica = pathname.startsWith('/catalogo/producto/') || pathname.startsWith('/legal/');
    if (cambioRuta || !dinamica) {
      const pagina = TITULOS[pathname] || tituloPorPrefijo(pathname) || (dinamica ? 'Contenido de la tienda' : 'Tienda');
      // Mientras la configuración carga (null) va solo el título de la página, sin el nombre por defecto "Tienda"
      document.title = cargando ? pagina : `${pagina} · ${configuracion?.nombre_tienda || 'Tienda'}`;
    }
    if (cambioRuta && !inicial && !document.activeElement?.closest('.cookie-banner')) {
      document.querySelector('main')?.focus({ preventScroll: true });
    }
    rutaAnterior.current = pathname;
  }, [pathname, cargando, configuracion?.nombre_tienda]);

  return <a className="saltar-contenido" href="#contenido" onClick={() => document.querySelector('main')?.focus()}>Saltar al contenido</a>;
}
