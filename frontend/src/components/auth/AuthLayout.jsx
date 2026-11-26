import Header from '../header/header';
import useConfiguracionTienda from '../../hooks/useConfiguracionTienda';
import { PORTADA_POR_DEFECTO } from '../landing/textosPorDefecto';
import './auth.css';

// Login, registro y recuperar la contraseña: la portada de la landing a la izquierda y el formulario a la derecha
export default function AuthLayout({ children }) {
  // Decorativa: el nombre ya está en el header
  const configuracion = useConfiguracionTienda();
  // La misma foto que se ve primero en la portada: la primera del carrusel (con el carrusel, la foto antigua
  // pasa a ser una de sus fotos y "banner" queda vacío); si no hay, la antigua o la de ejemplo
  const portada = configuracion?.banners?.[0]?.imagen || configuracion?.banner || configuracion?.banner_url?.trim()
    || PORTADA_POR_DEFECTO;

  return (
    <>
      <Header />
      <main tabIndex={-1} id="contenido" className="auth-main">
        <div className="auth-imagen" aria-hidden="true" style={{ backgroundImage: `url("${portada}")` }}>
          {configuracion?.nombre_tienda && <span className="auth-imagen-nombre">{configuracion.nombre_tienda}</span>}
        </div>
        <div className="auth-contenido">{children}</div>
      </main>
    </>
  );
}
