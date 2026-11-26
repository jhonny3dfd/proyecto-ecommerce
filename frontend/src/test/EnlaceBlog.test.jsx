import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock } }));
vi.mock('../components/MenuUsuario', () => ({ default: () => null }));
vi.mock('../components/CarritoCompras', () => ({ default: () => null }));

const CONFIGURACION = { nombre_tienda: 'Taller Maché', nosotros_texto: 'Desde 2015 en Valparaíso.' };

function responder(configuracion, paginas = []) {
  getMock.mockImplementation((url) => Promise.resolve({ data: url === 'configuracion/' ? configuracion : paginas }));
}

async function renderTienda() {
  // La configuración se guarda entre montajes: cada test parte con el módulo limpio
  vi.resetModules();
  const [{ default: Header }, { default: Footer }] = await Promise.all([
    import('../components/header/header'),
    import('../components/footer')
  ]);
  return render(<MemoryRouter><Header /><Footer /></MemoryRouter>);
}

const menu = () => screen.findByRole('navigation', { name: 'Navegación de la tienda' });
const columnaTienda = () => screen.findByRole('navigation', { name: 'Tienda' });

describe('Enlace al blog en el header y el footer', () => {
  it('comparte todos los nombres y el orden visibles sin duplicados y deja seguimiento al final', async () => {
    responder({
      ...CONFIGURACION,
      blog_activo: true,
      blog_nombre: 'Proyectos',
      sobre_mi_nombre: 'Mi historia',
      sobre_mi_activo: true,
      cotizaciones_activas: true,
      menu_principal: {
        orden: ['cotizar', 'sobre_mi', 'catalogo', 'nosotros', 'inicio', 'cotizar'],
        nombres: { inicio: 'Portada', catalogo: 'Productos', nosotros: 'Proyectos', sobre_mi: 'Mi historia', cotizar: 'Encargos' }
      }
    });
    await renderTienda();
    const pie = within(await columnaTienda());
    // Solo Catálogo usa su nombre personalizado: Inicio y Cotizar muestran el suyo aunque haya uno antiguo guardado
    await pie.findByRole('link', { name: 'Cotizar' });
    const enlaces = pie.getAllByRole('link');
    expect(enlaces.map(enlace => enlace.textContent)).toEqual(['Cotizar', 'Mi historia', 'Productos', 'Proyectos', 'Inicio', 'Seguimiento de pedido']);
    expect(enlaces.map(enlace => enlace.getAttribute('href'))).toEqual(['/cotizar', '/sobre-mi', '/catalogo', '/blog', '/', '/seguimiento']);
    expect(new Set(enlaces.map(enlace => enlace.getAttribute('href'))).size).toBe(enlaces.length);
    expect(enlaces.slice(0, -1).map(enlace => enlace.textContent)).toEqual(within(await menu()).getAllByRole('link').map(enlace => enlace.textContent));
  });

  it.each([
    [{}, ['/', '/catalogo', '/#nosotros', '/seguimiento']],
    [{ nosotros_texto: '', sobre_mi_activo: false, cotizaciones_activas: false }, ['/', '/catalogo', '/seguimiento']],
    [{ sobre_mi_activo: true }, ['/', '/catalogo', '/#nosotros', '/sobre-mi', '/seguimiento']]
  ])('respeta visibilidad y valores heredados en el pie: %j', async (config, destinos) => {
    responder({ ...CONFIGURACION, ...config });
    await renderTienda();
    const pie = within(await columnaTienda());
    await within(await menu()).findByRole('link', { name: 'Catálogo' });
    expect(pie.getAllByRole('link').map(enlace => enlace.getAttribute('href'))).toEqual(destinos);
    expect(pie.getAllByRole('link').at(-1)).toHaveTextContent('Seguimiento de pedido');
  });

  it('conserva las secciones legales y de contacto', async () => {
    responder({ ...CONFIGURACION, correo_contacto: 'contacto@example.test', facebook_url: 'https://www.facebook.com/tienda' }, [
      { tipo_pagina: 'TERMINOS', titulo: 'Condiciones de compra' }
    ]);
    await renderTienda();
    const legal = within(screen.getByRole('navigation', { name: 'Información legal' }));
    expect(await legal.findByRole('link', { name: 'Condiciones de compra' })).toHaveAttribute('href', '/legal/terminos');
    const contacto = within(screen.getByRole('region', { name: 'Contacto' }));
    expect(contacto.getByRole('link', { name: 'contacto@example.test' })).toHaveAttribute('href', 'mailto:contacto@example.test');
    expect(contacto.getByRole('link', { name: /Facebook de Taller Maché/ })).toHaveAttribute('href', 'https://www.facebook.com/tienda');
  });

  it('personaliza el encabezado y el pie sin cambiar el enlace administrativo', async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder({ ...CONFIGURACION, blog_activo: true, blog_nombre: 'Portafolio', menu_principal: {
      orden: ['nosotros', 'catalogo', 'inicio', 'cotizar', 'sobre_mi'], nombres: { nosotros: 'Proyectos' }
    } });
    await renderTienda();
    const navegacion = within(await menu());
    await navegacion.findByRole('link', { name: 'Portafolio' });
    expect(navegacion.getAllByRole('link').map(enlace => enlace.textContent)).toEqual(['Portafolio', 'Catálogo', 'Inicio', 'Panel admin']);
    expect(navegacion.getByRole('link', { name: 'Portafolio' })).toHaveAttribute('href', '/blog');
    expect(within(await columnaTienda()).getAllByRole('link').map(enlace => enlace.textContent)).toEqual(['Portafolio', 'Catálogo', 'Inicio', 'Seguimiento de pedido']);
    localStorage.removeItem('rol');
  });
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => cleanup());

  it('con el blog activo, el enlace lleva a /blog con el nombre que eligió el admin', async () => {
    responder({ ...CONFIGURACION, blog_activo: true, blog_nombre: 'Portafolio' });
    await renderTienda();

    expect(await within(await menu()).findByRole('link', { name: 'Portafolio' })).toHaveAttribute('href', '/blog');
    expect(within(await menu()).queryByRole('link', { name: 'Nosotros' })).not.toBeInTheDocument();
    expect(within(await columnaTienda()).getByRole('link', { name: 'Portafolio' })).toHaveAttribute('href', '/blog');
  });

  it('con el blog apagado, "Nosotros" sigue llevando a la sección de la landing', async () => {
    responder({ ...CONFIGURACION, blog_activo: false, blog_nombre: 'Portafolio' });
    await renderTienda();

    expect(await within(await menu()).findByRole('link', { name: 'Nosotros' })).toHaveAttribute('href', '/#nosotros');
    expect(screen.queryByRole('link', { name: 'Portafolio' })).not.toBeInTheDocument();
  });

  it('con el blog apagado y sin texto de Nosotros, no hay enlace', async () => {
    responder({ ...CONFIGURACION, nosotros_texto: '', blog_activo: false });
    await renderTienda();

    await within(await menu()).findByRole('link', { name: 'Catálogo' });
    expect(screen.queryByRole('link', { name: 'Nosotros' })).not.toBeInTheDocument();
  });

  it('el blog activo aparece aunque la landing no tenga texto de Nosotros', async () => {
    responder({ ...CONFIGURACION, nosotros_texto: '', blog_activo: true, blog_nombre: 'Nosotros' });
    await renderTienda();

    expect(await within(await menu()).findByRole('link', { name: 'Nosotros' })).toHaveAttribute('href', '/blog');
  });

  it('muestra el enlace independiente de Sobre mí cuando está activo', async () => {
    responder({
      ...CONFIGURACION,
      blog_activo: true,
      blog_nombre: 'Portafolio',
      sobre_mi_activo: true,
      sobre_mi_nombre: 'Mi historia'
    });

    await renderTienda();

    const navegacion = within(await menu());

    expect(
      await navegacion.findByRole('link', { name: 'Mi historia' })
    ).toHaveAttribute('href', '/sobre-mi');

    expect(
      navegacion.getByRole('link', { name: 'Portafolio' })
    ).toHaveAttribute('href', '/blog');
  });

  it('oculta el enlace de Sobre mí cuando está desactivado', async () => {
    responder({
      ...CONFIGURACION,
      sobre_mi_activo: false,
      sobre_mi_nombre: 'Mi historia'
    });

    await renderTienda();

    const navegacion = within(await menu());

    await navegacion.findByRole('link', { name: 'Catálogo' });

    expect(
      navegacion.queryByRole('link', { name: 'Mi historia' })
    ).not.toBeInTheDocument();
  });

  it('muestra Sobre mí aunque el blog esté desactivado', async () => {
    responder({
      ...CONFIGURACION,
      blog_activo: false,
      sobre_mi_activo: true,
      sobre_mi_nombre: 'Mi historia'
    });

    await renderTienda();

    const navegacion = within(await menu());

    expect(
      await navegacion.findByRole('link', { name: 'Mi historia' })
    ).toHaveAttribute('href', '/sobre-mi');

    expect(
      navegacion.getByRole('link', { name: 'Nosotros' })
    ).toHaveAttribute('href', '/#nosotros');
  });

});
