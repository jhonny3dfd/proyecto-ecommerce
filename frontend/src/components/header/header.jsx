import { Link, NavLink } from "react-router-dom";
import "./header.css";
import { resolverMenu } from "../../utils/menuPrincipal";
import logoUniversidad from "./logoU.png";
import MenuUsuario from "../MenuUsuario";
import MenuEdicion from "./MenuEdicion";
import CarritoCompras from "../CarritoCompras";
import useConfiguracionTienda from "../../hooks/useConfiguracionTienda";

// vistaPrevia: el modo edición de la landing muestra aquí el nombre y el logo antes de guardarlos
function Header({ vistaPrevia, edicion }) {
  // Solo conservamos el rol para saber si mostramos el atajo de admin
  const rol = localStorage.getItem("rol");
  const publicada = useConfiguracionTienda();
  const configuracion = vistaPrevia ? { ...publicada, ...vistaPrevia } : publicada;
  const nombreTienda = configuracion?.nombre_tienda || "Tienda";
  // RN-01: si el admin lo llevó al pie de página, se muestra allá, más grande (footer.jsx). Mientras la
  // configuración carga (null) todavía no se sabe dónde va: no se muestra, para que no aparezca un instante arriba
  // en una tienda que lo tiene abajo. Si la carga falla llega {} y queda en el header, el lugar por defecto
  const universidadEnHeader = configuracion !== null && configuracion?.ubicacion_logo_universidad !== "FOOTER";

  return (
    <header className={edicion?.editando ? "header header--editando" : "header"}>
      <div className="header-content">
        {/* RN-01: el logo de la Universidad va aquí junto al del negocio, o en el footer si el admin lo eligió; nunca se oculta */}
        <div className="header-marcas">
          <Link to="/" className="header-marca-negocio" aria-label={`${nombreTienda}, ir al inicio`}>
            {configuracion?.logo ? (
              <img className="header-logo-negocio" src={configuracion.logo} alt="" />
            ) : (
              // Mientras la configuración carga (null) no se muestra "Tienda": el espacio conserva el alto del header
              <span className="header-nombre-tienda">{configuracion === null ? "\u00A0" : nombreTienda}</span>
            )}
          </Link>
          {universidadEnHeader && (
            <>
              <span className="header-separador" aria-hidden="true" />
              <img
                className="header-logo-universidad"
                src={logoUniversidad}
                alt="Logo de la Universidad Autónoma"
              />
            </>
          )}
        </div>

        <nav className="header-nav" aria-label="Navegación de la tienda">
          <div className="header-links">
            {edicion?.editando ? <MenuEdicion configuracion={configuracion} edicion={edicion} /> : resolverMenu(configuracion).filter(enlace => enlace.visible).map(enlace =>
              enlace.to === '/#nosotros' ? (
                <Link key={enlace.id} to={enlace.to}>{enlace.nombre}</Link>
              ) : (
                <NavLink key={enlace.id} to={enlace.to} end={enlace.id === 'inicio'}>{enlace.nombre}</NavLink>
              )
            )}

            {/* Si es ADMIN, le damos un atajo rápido a su panel */}
            {rol === 'ADMIN' && (
              <NavLink to="/admin">Panel admin</NavLink>
            )}
          </div>

          {/* Agrupamos el Menú de Usuario y el Carrito de Compras */}
          <div className="header-actions">
            <MenuUsuario suscripciones={Boolean(configuracion?.suscripciones_activas)} />
            <CarritoCompras />
          </div>
        </nav>
      </div>
    </header>
  );
}

export default Header;
