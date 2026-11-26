import { describe, expect, it } from 'vitest';
import { ORDEN_MENU, botonDeFoto, resolverMenu, textoBotonCatalogo } from '../utils/menuPrincipal';

describe('menú principal', () => {
  it('conserva el orden, nombres y visibilidad heredados', () => {
    expect(resolverMenu().map(e => e.id)).toEqual(ORDEN_MENU);
    expect(resolverMenu().filter(e => e.visible).map(e => e.nombre)).toEqual(['Inicio', 'Catálogo']);
    expect(resolverMenu({ blog_activo: true, blog_nombre: 'Trabajos', sobre_mi_nombre: 'Historia' })[2].nombre).toBe('Trabajos');
  });
  it('cambia nombres y orden conservando destinos y enlaces ocultos', () => {
    const config = { menu_principal: { orden: [...ORDEN_MENU].reverse(), nombres: { nosotros: 'Empresa', catalogo: 'Productos' } } };
    expect(resolverMenu(config)[0]).toMatchObject({ id: 'suscripcion', visible: false, to: '/suscripcion' });
    expect(resolverMenu(config)[1]).toMatchObject({ id: 'cotizar', visible: false, to: '/cotizar' });
    expect(resolverMenu({ ...config, nosotros_texto: 'Texto' })[3]).toMatchObject({ nombre: 'Nosotros', to: '/#nosotros', visible: true });
    expect(resolverMenu({ ...config, blog_activo: true })[3]).toMatchObject({ nombre: 'Nosotros', to: '/blog', visible: true });
    expect(resolverMenu({ ...config, sobre_mi_activo: true, cotizaciones_activas: true, suscripciones_activas: true }).every(e => e.id === 'nosotros' || e.visible)).toBe(true);
  });
  it('recupera identificadores faltantes y descarta desconocidos sin duplicar', () => {
    expect(resolverMenu({ menu_principal: { orden: ['catalogo', 'catalogo', 'ajeno'] } }).map(e => e.id)).toEqual(['catalogo', 'inicio', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion']);
  });
  it('prioriza los nombres de las secciones sobre personalizaciones antiguas', () => {
    const config = { blog_activo: true, blog_nombre: 'Portafolio', sobre_mi_nombre: 'Mi historia',
      menu_principal: { nombres: { nosotros: 'Antiguo blog', sobre_mi: 'Antigua historia', inicio: 'Portada', cotizar: 'Encargos' } } };
    expect(resolverMenu(config).map(e => e.nombre)).toEqual(['Inicio', 'Catálogo', 'Portafolio', 'Mi historia', 'Cotizar', 'Suscripción']);
  });
  it('ignora visibilidad antigua y respeta exclusivamente la habilitación de secciones', () => {
    const config = { blog_activo: true, sobre_mi_activo: true, cotizaciones_activas: true, suscripciones_activas: true,
      menu_principal: { ocultos: ['inicio', 'catalogo', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion'] } };
    const anterior = structuredClone(config);
    expect(resolverMenu(config).filter(e => e.visible).map(e => e.id)).toEqual(ORDEN_MENU);
    expect(resolverMenu({ ...config, blog_activo: false, sobre_mi_activo: false, cotizaciones_activas: false, suscripciones_activas: false })
      .filter(e => e.visible).map(e => e.id)).toEqual(['inicio', 'catalogo']);
    expect(resolverMenu({ ...config, blog_activo: false, nosotros_texto: 'Nuestra tienda' })
      .find(e => e.id === 'nosotros')).toMatchObject({ to: '/#nosotros', visible: true });
    expect(config).toEqual(anterior);
  });
  it.each([['Catálogo', 'Ver catálogo'], ['Productos', 'Ver productos'], ['Nuestra colección', 'Ver nuestra colección'], ['Artículos', 'Ver artículos'], ['   ', 'Ver catálogo']])('deriva el botón de portada desde %s', (nombre, texto) => {
    expect(textoBotonCatalogo({ texto_boton_ingreso: 'Texto antiguo', menu_principal: { nombres: { catalogo: nombre } } })).toBe(texto);
  });
  it('arma el botón de cada foto del carrusel con el nombre y el destino del menú', () => {
    expect(botonDeFoto({})).toEqual({ to: '/catalogo', texto: 'Ver catálogo' });
    expect(botonDeFoto({}, 'INICIO')).toEqual({ to: '/', texto: 'Ver inicio' });
    expect(botonDeFoto({ menu_principal: { nombres: { catalogo: 'Productos' } } }, 'CATALOGO').texto).toBe('Ver productos');
    expect(botonDeFoto({ blog_activo: true, blog_nombre: 'Proyectos' }, 'BLOG')).toEqual({ to: '/blog', texto: 'Ver proyectos' });
    expect(botonDeFoto({ cotizaciones_activas: true }, 'COTIZAR')).toEqual({ to: '/cotizar', texto: 'Ver cotizar' });
  });
  it('el enlace Suscripción solo aparece con el módulo activo (pedido de un cliente)', () => {
    expect(resolverMenu().find(e => e.id === 'suscripcion')).toMatchObject({ visible: false, to: '/suscripcion', nombre: 'Suscripción' });
    expect(resolverMenu({ suscripciones_activas: true }).find(e => e.id === 'suscripcion').visible).toBe(true);
  });
  it('sin el módulo activo, la foto queda sin botón', () => {
    expect(botonDeFoto({ nosotros_texto: 'Nuestra historia' }, 'BLOG')).toBeNull();
    expect(botonDeFoto({}, 'COTIZAR')).toBeNull();
  });
});
