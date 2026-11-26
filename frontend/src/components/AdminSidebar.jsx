import useConfiguracionTienda from '../hooks/useConfiguracionTienda';

// Íconos de trazo fino (como los del header de la tienda)
const ICONOS = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
    </>
  ),
  inventario: (
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
  ),
  ventas: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />,
  cotizaciones: (
    <>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <line x1="8" y1="9" x2="16" y2="9" /><line x1="8" y1="13" x2="13" y2="13" />
    </>
  ),
  resenas: (
    <path d="M12 2.5l2.94 5.96 6.56.95-4.75 4.63 1.12 6.54L12 17.5l-5.87 3.08 1.12-6.54L2.5 9.41l6.56-.95z" />
  ),
  suscriptores: (
    <>
      <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 0 1 4-4h14" />
      <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 0 1-4 4H3" />
    </>
  ),
  cumpleanos: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 11h18" /></>,
  blog: (
    <>
      <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </>
  ),
  configuracion: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />
    </>
  ),
  paginas: (
    <>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
    </>
  )
};

const VISTAS = [
  { id: 'dashboard', nombre: 'Dashboard' },
  { id: 'inventario', nombre: 'Inventario' },
  { id: 'ventas', nombre: 'Ventas' },
  { id: 'cotizaciones', nombre: 'Cotizaciones' },
  { id: 'resenas', nombre: 'Reseñas' },
  // Suscripciones (pedido de un cliente, opcional): solo con el módulo activo
  { id: 'suscriptores', nombre: 'Suscriptores', visible: (configuracion) => Boolean(configuracion?.suscripciones_activas) },
  { id: 'cumpleanos', nombre: 'Cumpleaños del mes', visible: (configuracion) => Boolean(configuracion?.suscripciones_activas) },
  { id: 'blog', nombre: 'Blog' },
  { id: 'configuracion', nombre: 'Configuración' },
  { id: 'paginas', nombre: 'Páginas legales' }
];

export default function AdminSidebar({
  vistaActiva,
  setVistaActiva,
  setMostrandoFormulario,
  setProductoAEditar,
  navigate
}) {
  const configuracion = useConfiguracionTienda();

  const abrirVista = (id) => {
    setVistaActiva(id);
    // Al entrar al inventario se vuelve a la tabla (sin formulario abierto)
    if (id === 'inventario') {
      setMostrandoFormulario(false);
      setProductoAEditar(null);
    }
  };

  return (
    <aside className="admin-barra">
      <div className="admin-marca">
        <span className="admin-marca-nombre">{configuracion?.nombre_tienda || 'Mi tienda'}</span>
        <h1 className="admin-marca-titulo">Panel de administración</h1>
      </div>

      <nav className="admin-nav" aria-label="Secciones del panel">
        {VISTAS.filter(({ visible }) => !visible || visible(configuracion)).map(({ id, nombre }) => (
          <button
            key={id}
            type="button"
            className="admin-nav-item"
            aria-current={vistaActiva === id ? 'page' : undefined}
            onClick={() => abrirVista(id)}
          >
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              {ICONOS[id]}
            </svg>
            {nombre}
          </button>
        ))}

        <span className="admin-nav-separador" aria-hidden="true" />

        <button type="button" className="admin-nav-item admin-nav-item--externo" onClick={() => navigate('/')}>
          Ver mi tienda <span aria-hidden="true">↗</span>
        </button>
      </nav>
    </aside>
  );
}
