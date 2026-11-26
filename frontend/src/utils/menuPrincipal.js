export const ORDEN_MENU = ['inicio', 'catalogo', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion'];

export function resolverMenu(config = {}) {
  config = config || {};
  const menu = config.menu_principal || {};
  const orden = Array.isArray(menu.orden) ? [...new Set(menu.orden.filter(id => ORDEN_MENU.includes(id)))] : [];
  orden.push(...ORDEN_MENU.filter(id => !orden.includes(id)));
  const enlaces = {
    inicio: { base: 'Inicio', to: '/', visible: true },
    catalogo: { base: 'Catálogo', to: '/catalogo', visible: true },
    nosotros: { base: config.blog_activo ? config.blog_nombre || 'Nosotros' : 'Nosotros',
      to: config.blog_activo ? '/blog' : '/#nosotros', visible: Boolean(config.blog_activo || config.nosotros_texto) },
    sobre_mi: { base: config.sobre_mi_nombre || 'Sobre mí', to: '/sobre-mi', visible: Boolean(config.sobre_mi_activo) },
    cotizar: { base: 'Cotizar', to: '/cotizar', visible: Boolean(config.cotizaciones_activas) },
    // Suscripciones (pedido de un cliente, opcional): solo con el módulo activo
    suscripcion: { base: 'Suscripción', to: '/suscripcion', visible: Boolean(config.suscripciones_activas) },
  };
  return orden.map(id => {
    // Solo se renombra Catálogo: el blog y Sobre mí se nombran en su módulo, y los nombres antiguos de otros botones se ignoran
    const personalizado = id === 'catalogo' ? menu.nombres?.catalogo : undefined;
    return { id, ...enlaces[id],
      nombre: typeof personalizado === 'string' && personalizado.trim() ? personalizado.trim().replace(/\s+/g, ' ') : enlaces[id].base };
  });
}

// Botón de cada foto del carrusel (SCRUM-194): lleva a una página del header y toma su nombre del menú.
// Blog y Cotizar solo se muestran con su módulo activo; si el módulo se apaga, la foto queda sin botón (null)
const ENLACE_POR_DESTINO = { INICIO: 'inicio', CATALOGO: 'catalogo', BLOG: 'nosotros', COTIZAR: 'cotizar' };

export function botonDeFoto(configuracion, destino = 'CATALOGO') {
  const id = ENLACE_POR_DESTINO[destino] ?? 'catalogo';
  // Sin el blog, "nosotros" lleva a la sección de la landing: no es el blog
  if (destino === 'BLOG' && !configuracion?.blog_activo) return null;
  const enlace = resolverMenu(configuracion).find(item => item.id === id);
  if (!enlace?.visible) return null;
  return { to: enlace.to, texto: `Ver ${enlace.nombre.toLocaleLowerCase('es')}` };
}

export function textoBotonCatalogo(configuracion) {
  const catalogo = resolverMenu(configuracion).find(enlace => enlace.id === 'catalogo');
  return `Ver ${catalogo.nombre.toLocaleLowerCase('es')}`;
}
