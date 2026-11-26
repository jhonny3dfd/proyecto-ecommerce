import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useState } from 'react';
const { getMock, patchMock } = vi.hoisted(() => ({ getMock: vi.fn(), patchMock: vi.fn() }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock, patch: patchMock } }));
vi.mock('../components/MenuUsuario', () => ({ default: () => null }));
vi.mock('../components/CarritoCompras', () => ({ default: () => null }));

beforeAll(async () => {
  await Promise.all([
    import('../pages/LandingPage'),
    import('../components/footer')
  ]);
});

const producto = (id, nombre, extra = {}) => ({
  id, nombre, categoria: 'Arte', imagenes: [],
  variantes: [{ sku: `${id}-1`, precio: 20000, stock: 3 }], ...extra,
});

const CONFIGURACION = {
  nombre_tienda: 'Taller Maché',
  subtitulo_bienvenida: 'Hecho a mano',
  texto_bienvenida: 'Objetos con alma',
  texto_landing: 'Piezas únicas de papel maché.',
  texto_boton_ingreso: 'Ver piezas',
  nosotros_titulo: 'Un taller familiar',
  nosotros_texto: 'Desde 2015 en Valparaíso.',
};

function responder({ configuracion = CONFIGURACION, vitrina } = {}) {
  getMock.mockImplementation((url) => {
    if (url === 'configuracion/') return Promise.resolve({ data: configuracion });
    if (url === 'catalogo/vitrina/') {
      return Promise.resolve({ data: vitrina || {
        mas_vendidos: [producto('a', 'Jarrón'), producto('b', 'Lámpara', {
          variantes: [{ sku: 'b-1', precio: 30000, precio_oferta: 25000, stock: 2 }] })],
        recientes: [producto('c', 'Móvil', { variantes: [{ sku: 'c-1', precio: 9000, stock: 0 }] })],
      } });
    }
    return Promise.resolve({ data: [] });
  });
}

async function renderLanding() {
  // La configuración se guarda entre montajes: cada test parte con el módulo limpio
  vi.resetModules();
  const { default: LandingPage } = await import('../pages/LandingPage');
  return render(<MemoryRouter><LandingPage /></MemoryRouter>);
}

function LandingConFooter({ LandingPage, Footer }) {
  const [marcaTemporal, setMarcaTemporal] = useState(null);

  return (
    <MemoryRouter>
      <LandingPage onMarcaTemporal={setMarcaTemporal} />
      <Footer marcaTemporal={marcaTemporal} />
    </MemoryRouter>
  );
}

async function renderLandingConFooter() {
  vi.resetModules();

  const [{ default: LandingPage }, { default: Footer }] = await Promise.all([
    import('../pages/LandingPage'),
    import('../components/footer')
  ]);

  return render(
    <LandingConFooter LandingPage={LandingPage} Footer={Footer} />
  );
}
describe('LandingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => cleanup());

  it('muestra los textos de la portada que edita el admin y el botón lleva al catálogo', async () => {
    responder();
    await renderLanding();

    expect(await screen.findByRole('heading', { level: 1, name: 'Objetos con alma' })).toBeInTheDocument();
    expect(screen.getByText('Hecho a mano')).toBeInTheDocument();
    expect(screen.getByText('Piezas únicas de papel maché.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /ver catálogo/i })).toHaveAttribute('href', '/catalogo');
  });

  it('muestra los más vendidos y los últimos agregados con precio, oferta y agotado', async () => {
    responder();
    await renderLanding();

    const vendidos = await screen.findByRole('region', { name: 'Más vendidos' });
    expect(within(vendidos).getByRole('link', { name: /jarrón/i })).toHaveAttribute('href', '/catalogo/producto/a');
    expect(within(vendidos).getByText('$25.000')).toBeInTheDocument();
    expect(within(vendidos).getByText('$30.000')).toBeInTheDocument();

    const recientes = screen.getByRole('region', { name: 'Últimos agregados' });
    expect(within(recientes).getByText('Agotado')).toBeInTheDocument();
  });

  it('muestra la sección Nosotros solo si tiene texto', async () => {
    responder();
    await renderLanding();
    expect(await screen.findByRole('region', { name: 'Un taller familiar' })).toBeInTheDocument();

    cleanup();
    responder({ configuracion: { ...CONFIGURACION, nosotros_texto: '' } });
    await renderLanding();
    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('region', { name: 'Un taller familiar' })).not.toBeInTheDocument();
  });

  it('muestra el botón de Sobre mí cuando la página está activada', async () => {
    responder({
      configuracion: {
        ...CONFIGURACION,
        sobre_mi_activo: true,
        sobre_mi_nombre: 'Mi historia'
      }
    });

    await renderLanding();

    const seccion = await screen.findByRole('region', {
      name: 'Un taller familiar'
    });

    expect(
      within(seccion).getByRole('link', {
        name: 'Conoce más: Mi historia'
      })
    ).toHaveAttribute('href', '/sobre-mi');
  });

  it.each([
    [{ sobre_mi_nombre: 'Nosotros' }, 'Nosotros'],
    [{ sobre_mi_nombre: 'Mi historia', menu_principal: { nombres: { sobre_mi: 'Nosotros' } } }, 'Mi historia'],
    [{ menu_principal: { nombres: { sobre_mi: '   ' } } }, 'Sobre mí'],
    [{ sobre_mi_nombre: '', menu_principal: { nombres: { sobre_mi: '' } } }, 'Sobre mí'],
    [{}, 'Sobre mí']
  ])('el botón comparte el nombre del menú y conserva su destino: %j', async (config, nombre) => {
    responder({ configuracion: { ...CONFIGURACION, sobre_mi_activo: true, ...config } });
    await renderLanding();
    const seccion = await screen.findByRole('region', { name: 'Un taller familiar' });
    expect(within(seccion).getByRole('link', { name: 'Conoce más: ' + nombre })).toHaveAttribute('href', '/sobre-mi');
    const menu = screen.getByRole('navigation', { name: 'Navegación de la tienda' });
    expect(within(menu).getAllByRole('link', { name: nombre })
      .filter(enlace => enlace.getAttribute('href') === '/sobre-mi')).toHaveLength(1);
  });

  it('oculta el botón de Sobre mí cuando la página está desactivada', async () => {
    responder({
      configuracion: {
        ...CONFIGURACION,
        sobre_mi_activo: false
      }
    });

    await renderLanding();

    const seccion = await screen.findByRole('region', {
      name: 'Un taller familiar'
    });

    expect(
      within(seccion).queryByRole('link', {
        name: /Conoce más:/
      })
    ).not.toBeInTheDocument();
  });

  it('muestra el botón de Sobre mí aunque la sección Nosotros no tenga texto', async () => {
    responder({
      configuracion: {
        ...CONFIGURACION,
        nosotros_texto: '',
        sobre_mi_activo: true,
        sobre_mi_nombre: 'Mi historia'
      }
    });

    await renderLanding();

    const seccion = await screen.findByRole('region', {
      name: 'Un taller familiar'
    });

    expect(
      within(seccion).getByRole('link', {
        name: 'Conoce más: Mi historia'
      })
    ).toHaveAttribute('href', '/sobre-mi');
  });

  it('muestra la sección de Instagram solo con usuario, con sus fotos y el botón al perfil', async () => {
    responder({ configuracion: { ...CONFIGURACION, instagram_usuario: 'taller.mache',
      instagram_foto_1: 'http://localhost:8000/media/negocio/instagram/uno.jpg', instagram_foto_2: null } });
    const { container } = await renderLanding();

    const seccion = await screen.findByRole('region', { name: '@taller.mache' });
    const boton = within(seccion).getByRole('link', { name: /Seguir en Instagram/ });
    expect(boton).toHaveAttribute('href', 'https://www.instagram.com/taller.mache/');
    expect(boton).toHaveAttribute('rel', 'noopener noreferrer');
    // Solo las fotos cargadas, fuera del árbol accesible: el enlace accesible es el botón
    const fotos = container.querySelectorAll('#instagram img');
    expect(fotos).toHaveLength(1);
    expect(fotos[0].closest('[aria-hidden="true"]')).not.toBeNull();

    cleanup();
    responder();
    await renderLanding();
    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('region', { name: /Instagram|@/ })).not.toBeInTheDocument();
  });

  it('sin productos no muestra las secciones de productos', async () => {
    responder({ vitrina: { mas_vendidos: [], recientes: [] } });
    await renderLanding();

    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('region', { name: 'Más vendidos' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Últimos agregados' })).not.toBeInTheDocument();
  });

  it('muestra los destacados elegidos en lugar de "Más vendidos", con su enlace y el precio de los productos', async () => {
    responder({
      configuracion: { ...CONFIGURACION, vitrina_modo: 'DESTACADOS', blog_activo: true, blog_nombre: 'Portafolio' },
      vitrina: {
        mas_vendidos: [], recientes: [producto('c', 'Móvil')], destacados_titulo: 'Obras elegidas',
        destacados: [
          { tipo: 'PUBLICACION', id: '7', nombre: 'Mural en Cerro Alegre', imagen: 'http://localhost/mural.jpg',
            enlace: '/blog/mural-cerro-alegre' },
          { tipo: 'PRODUCTO', id: 'a', nombre: 'Retrato', categoria: 'Óleos', imagen: null, enlace: '/catalogo/producto/a',
            variantes: [{ sku: 'a-1', precio: 30000, precio_oferta: 25000, stock: 1 }] },
        ],
      },
    });
    const { container } = await renderLanding();

    const seccion = await screen.findByRole('region', { name: 'Obras elegidas' });
    expect(screen.queryByRole('region', { name: 'Más vendidos' })).not.toBeInTheDocument();
    const tarjetas = within(seccion).getAllByRole('listitem');
    expect(tarjetas).toHaveLength(2);
    // En el orden que eligió el admin, cada una lleva a la publicación o a la ficha del producto
    expect(within(tarjetas[0]).getByRole('link', { name: /Mural en Cerro Alegre/ }))
      .toHaveAttribute('href', '/blog/mural-cerro-alegre');
    expect(within(tarjetas[0]).getByText('Portafolio')).toBeInTheDocument();
    expect(within(tarjetas[1]).getByRole('link', { name: /Retrato/ })).toHaveAttribute('href', '/catalogo/producto/a');
    expect(within(tarjetas[1]).getByText('Óleos')).toBeInTheDocument();
    expect(within(tarjetas[1]).getByText('$25.000')).toBeInTheDocument();
    expect(within(tarjetas[1]).getByText('$30.000')).toBeInTheDocument();
    // La foto es decorativa (el nombre está en la tarjeta) y reserva su lugar
    const foto = container.querySelector('#destacados img');
    expect(foto).toHaveAttribute('alt', '');
    expect(foto).toHaveAttribute('loading', 'lazy');
    // "Últimos agregados" no cambia
    expect(screen.getByRole('region', { name: 'Últimos agregados' })).toBeInTheDocument();
  });

  it('si no queda ningún destacado visible muestra "Más vendidos", para que la landing no quede con un hueco', async () => {
    responder({ configuracion: { ...CONFIGURACION, vitrina_modo: 'DESTACADOS', destacados_titulo: 'Obras' } });
    await renderLanding();

    expect(await screen.findByRole('region', { name: 'Más vendidos' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Obras' })).not.toBeInTheDocument();
  });

  it('mientras llega la vitrina usa el título guardado de los destacados', async () => {
    responder({ configuracion: { ...CONFIGURACION, vitrina_modo: 'DESTACADOS', destacados_titulo: 'Obras' } });
    const respuesta = getMock.getMockImplementation();
    getMock.mockImplementation((url) => (url === 'catalogo/vitrina/' ? new Promise(() => {}) : respuesta(url)));
    await renderLanding();

    const seccion = await screen.findByRole('region', { name: 'Obras' });
    expect(within(seccion).getByText('Cargando destacados...')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Más vendidos' })).not.toBeInTheDocument();
  });

  it('el header muestra el logo de la Universidad junto al nombre del negocio (RN-01)', async () => {
    responder();
    await renderLanding();

    expect(await screen.findByText('Taller Maché')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Logo de la Universidad Autónoma' })).toBeInTheDocument();
  });

  it('con el logo en el footer se ve ahí más grande y el header queda con el de la tienda (RN-01)', async () => {
    responder({ configuracion: { ...CONFIGURACION, ubicacion_logo_universidad: 'FOOTER' } });
    await renderLandingConFooter();

    const footer = await screen.findByRole('contentinfo');
    await waitFor(() => expect(within(footer).getByRole('img', { name: 'Logo de la Universidad Autónoma' }))
      .toHaveClass('footer-logo-universidad'));
    expect(within(footer).getByText('Taller Maché')).toBeInTheDocument();
    expect(within(screen.getByRole('banner')).queryByRole('img', { name: 'Logo de la Universidad Autónoma' }))
      .not.toBeInTheDocument();
    // Nunca desaparece: está en un solo lugar
    expect(screen.getAllByRole('img', { name: 'Logo de la Universidad Autónoma' })).toHaveLength(1);
  });

  it('mientras carga la configuración no muestra el logo de la Universidad en ningún lado, para no ponerlo arriba en una tienda que lo tiene abajo (RN-01)', async () => {
    let entregar;
    responder();
    const respuestaNormal = getMock.getMockImplementation();
    getMock.mockImplementation((url) => (url === 'configuracion/'
      ? new Promise((resolver) => { entregar = resolver; })
      : respuestaNormal(url)));
    await renderLandingConFooter();

    expect(screen.queryByRole('img', { name: 'Logo de la Universidad Autónoma' })).not.toBeInTheDocument();

    entregar({ data: { ...CONFIGURACION, ubicacion_logo_universidad: 'FOOTER' } });
    const footer = await screen.findByRole('contentinfo');
    await waitFor(() => expect(within(footer).getByRole('img', { name: 'Logo de la Universidad Autónoma' }))
      .toBeInTheDocument());
    expect(screen.getAllByRole('img', { name: 'Logo de la Universidad Autónoma' })).toHaveLength(1);
  });

  it('si la configuración no responde, el logo de la Universidad igual aparece en el header (RN-01)', async () => {
    responder();
    const respuestaNormal = getMock.getMockImplementation();
    getMock.mockImplementation((url) => (url === 'configuracion/'
      ? Promise.reject(new Error('sin conexión')) : respuestaNormal(url)));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await renderLanding();

    expect(await within(screen.getByRole('banner')).findByRole('img', { name: 'Logo de la Universidad Autónoma' }))
      .toBeInTheDocument();
  });
});

describe('LandingPage en modo edición (RF-01.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    patchMock.mockResolvedValue({ data: {} });
    // jsdom no implementa las vistas previas de archivos
    URL.createObjectURL = vi.fn(() => 'blob:vista-previa');
    URL.revokeObjectURL = vi.fn();

  });

  afterEach(() => cleanup());

  it('actualiza el nombre y el copyright del footer al editar y los restaura al descartar', 
  async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder();

    await renderLandingConFooter();

    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));

    const footer = await screen.findByRole('contentinfo');
    const campoNombre = screen.getByLabelText('Nombre de la tienda');
    const anio = new Date().getFullYear();

    fireEvent.change(campoNombre, {
      target: { value: 'Mi nueva tienda' }
    });

    await waitFor(() => {
      expect(footer).toHaveTextContent('Mi nueva tienda');
      expect(footer).toHaveTextContent(
        `© ${anio} Mi nueva tienda. Todos los derechos reservados.`
      );
    });

    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));

    await waitFor(() => {
      expect(footer).toHaveTextContent('Taller Maché');
      expect(footer).toHaveTextContent(
        `© ${anio} Taller Maché. Todos los derechos reservados.`
      );
    });
  });

  it('edita Catálogo en el header, sincroniza portada y footer y descarta sin guardar', async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder();
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    const campo = screen.getByLabelText('Nombre de Catálogo');
    const menu = screen.getByRole('navigation', { name: 'Navegación de la tienda' });
    const footer = screen.getByRole('navigation', { name: 'Tienda' });
    expect(within(menu).getAllByRole('textbox')).toHaveLength(1);
    expect(screen.queryByLabelText('Texto del botón')).not.toBeInTheDocument();
    expect(campo).toHaveAttribute('maxLength', '20');
    expect(within(menu).getByText('8/20')).toHaveAttribute('id', campo.getAttribute('aria-describedby'));
    expect(menu.querySelectorAll('.campo-editable-ayuda')).toHaveLength(1);
    expect([...menu.querySelectorAll('.menu-edicion-item')].filter(item => !item.contains(campo))
      .every(item => item.querySelector('.campo-editable-ayuda') === null)).toBe(true);
    fireEvent.click(campo);
    fireEvent.change(campo, { target: { value: 'Nuestra colección' } });
    expect(screen.getByText('Ver nuestra colección')).toBeInTheDocument();
    expect(within(menu).getByText('17/20')).toBeInTheDocument();
    await waitFor(() => expect(within(footer).getByRole('link', { name: 'Nuestra colección' })).toHaveAttribute('href', '/catalogo'));
    expect(patchMock).not.toHaveBeenCalled();
    fireEvent.change(campo, { target: { value: '   ' } });
    expect(screen.getByText('Ver catálogo')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));
    expect(campo).toHaveValue('Catálogo');
    await waitFor(() => expect(within(footer).getByRole('link', { name: 'Catálogo' })).toBeInTheDocument());
    expect(screen.getByText('Sin cambios')).toBeInTheDocument();
  });

  it('mueve enlaces habilitados sin controles de visibilidad ni recuperación', async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder({ configuracion: { ...CONFIGURACION, blog_activo: true, blog_nombre: 'Blog', sobre_mi_activo: true, sobre_mi_nombre: 'Historia',
      menu_principal: { nombres: { nosotros: 'Blog antiguo', sobre_mi: 'Historia antigua' }, ocultos: ['nosotros', 'sobre_mi', 'cotizar'] } } });
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    expect(within(screen.getByRole('banner')).queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Mover Cotizar a la derecha' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mover Inicio a la izquierda' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Mover Historia a la derecha' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Mover Catálogo a la izquierda' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Mover Catálogo a la derecha' })).toHaveFocus());
    const footer = screen.getByRole('navigation', { name: 'Tienda' });
    await waitFor(() => expect(within(footer).getAllByRole('link')[0]).toHaveTextContent('Catálogo'));
    expect(within(footer).getByRole('link', { name: 'Blog' })).toHaveAttribute('href', '/blog');
    expect(within(footer).getByRole('link', { name: 'Historia' })).toHaveAttribute('href', '/sobre-mi');
    expect(within(footer).queryByRole('link', { name: 'Cotizar' })).not.toBeInTheDocument();
    expect(screen.queryByText('Blog antiguo')).not.toBeInTheDocument();
    expect(screen.queryByText('Historia antigua')).not.toBeInTheDocument();
    expect(patchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));
    await waitFor(() => expect(within(footer).getAllByRole('link')[0]).toHaveTextContent('Inicio'));
  });

  it('guarda nombre y orden conservando la visibilidad antigua sin aplicarla', async () => {
    localStorage.setItem('rol', 'ADMIN');
    const config = { ...CONFIGURACION, sobre_mi_activo: true, sobre_mi_nombre: 'Historia', menu_principal: { ocultos: ['sobre_mi'] } };
    responder({ configuracion: config });
    patchMock.mockImplementation(async (_, datos) => { Object.assign(config, datos); return { data: config }; });
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    fireEvent.change(screen.getByLabelText('Nombre de Catálogo'), { target: { value: 'Productos' } });
    fireEvent.click(screen.getByRole('button', { name: 'Mover Productos a la izquierda' }));
    expect(patchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await screen.findByText(/Cambios guardados/);
    expect(patchMock).toHaveBeenCalledTimes(1);
    expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', { menu_principal: {
      nombres: { catalogo: 'Productos' }, orden: ['catalogo', 'inicio', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion'], ocultos: ['sobre_mi']
    } });
    expect(config.texto_boton_ingreso).toBe('Ver piezas');
    cleanup();
    await renderLandingConFooter();
    const menu = await screen.findByRole('navigation', { name: 'Navegación de la tienda' });
    await waitFor(() => expect(within(menu).getAllByRole('link')[0]).toHaveTextContent('Productos'));
    expect(within(menu).getByRole('link', { name: 'Historia' })).toHaveAttribute('href', '/sobre-mi');
    expect(screen.getByRole('link', { name: /Ver productos/ })).toHaveAttribute('href', '/catalogo');
  });

  it('Salir conserva la confirmación de cambios pendientes y revierte el borrador', async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder();
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    fireEvent.change(screen.getByLabelText('Nombre de Catálogo'), { target: { value: 'Artículos' } });
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false);
    fireEvent.click(screen.getByRole('button', { name: 'Salir' }));
    expect(screen.getByLabelText('Nombre de Catálogo')).toHaveValue('Artículos');
    confirmar.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: 'Salir' }));
    expect(screen.queryByLabelText('Nombre de Catálogo')).not.toBeInTheDocument();
    expect(await screen.findByRole('link', { name: /Ver catálogo/ })).toHaveAttribute('href', '/catalogo');
    expect(patchMock).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it('mantiene el borrador y permite descartar cuando falla el guardado del menú', async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder();
    patchMock.mockRejectedValue({ response: { data: { menu_principal: ['El menú no es válido.'] } } });
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    fireEvent.change(screen.getByLabelText('Nombre de Catálogo'), { target: { value: 'Artículos' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(screen.getAllByText(/El menú no es válido/).length).toBeGreaterThan(0));
    expect(screen.getByLabelText('Nombre de Catálogo')).toHaveValue('Artículos');
    expect(screen.getByText('Ver artículos')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));
    expect(screen.getByLabelText('Nombre de Catálogo')).toHaveValue('Catálogo');
    expect(screen.getByText('Ver catálogo')).toBeInTheDocument();
  });

  it('reordena solo los enlaces visibles sin perder la posición de módulos deshabilitados', async () => {
    localStorage.setItem('rol', 'ADMIN');
    const config = { ...CONFIGURACION, menu_principal: {
      orden: ['inicio', 'sobre_mi', 'catalogo', 'cotizar', 'nosotros'], ocultos: ['nosotros']
    } };
    responder({ configuracion: config });
    patchMock.mockImplementation(async (_, datos) => { Object.assign(config, datos); return { data: config }; });
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    expect(screen.queryByRole('button', { name: /Mover Sobre mí/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Mover Cotizar/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Mover Catálogo a la izquierda' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Mover Catálogo a la derecha' })).toHaveFocus());
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await screen.findByText(/Cambios guardados/);
    expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', { menu_principal: {
      orden: ['catalogo', 'sobre_mi', 'inicio', 'cotizar', 'nosotros', 'suscripcion'], ocultos: ['nosotros']
    } });
  });

  it('conserva nombres antiguos largos y permite reemplazarlos sin truncarlos', async () => {
    localStorage.setItem('rol', 'ADMIN');
    const anterior = 'Nuestra colección especial';
    const config = { ...CONFIGURACION, menu_principal: { nombres: { catalogo: anterior } } };
    responder({ configuracion: config });
    patchMock.mockImplementation(async (_, datos) => { Object.assign(config, datos); return { data: config }; });
    await renderLandingConFooter();
    const header = await screen.findByRole('banner');
    await waitFor(() => expect(within(header).getByRole('link', { name: anterior })).toHaveAttribute('href', '/catalogo'));
    expect(header.querySelectorAll('.campo-editable-ayuda')).toHaveLength(0);
    fireEvent.click(screen.getByRole('button', { name: 'Editar página' }));
    const campo = screen.getByLabelText('Nombre de Catálogo');
    expect(campo).toHaveValue(anterior);
    expect(campo).toHaveAttribute('maxLength', '20');
    expect(within(header).getByText(anterior.length + '/20')).toBeInTheDocument();
    fireEvent.change(campo, { target: { value: 'Artículos' } });
    expect(within(header).getByText('9/20')).toBeInTheDocument();
    expect(screen.getByText('Ver artículos')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));
    expect(campo).toHaveValue(anterior);
    expect(patchMock).not.toHaveBeenCalled();
    fireEvent.change(campo, { target: { value: 'Productos' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await screen.findByText(/Cambios guardados/);
    expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', { menu_principal: { nombres: { catalogo: 'Productos' } } });
    fireEvent.click(screen.getByRole('button', { name: 'Salir' }));
    expect(header.querySelectorAll('.campo-editable-ayuda')).toHaveLength(0);
    expect(within(header).getByRole('link', { name: 'Productos' })).toHaveAttribute('href', '/catalogo');
  });

  async function entrarComoAdmin() {
    localStorage.setItem('rol', 'ADMIN');
    responder();
    await renderLanding();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
  }

  it('el admin elige dónde va el logo de la Universidad, lo ve antes de guardar y se publica (RN-01)', async () => {
    localStorage.setItem('rol', 'ADMIN');
    responder();
    await renderLandingConFooter();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));

    const ubicacion = screen.getByLabelText('Logo de la Universidad');
    expect(ubicacion).toHaveValue('HEADER');
    // Solo dos lugares: no existe una opción para ocultarlo
    expect([...ubicacion.options].map(opcion => opcion.value)).toEqual(['HEADER', 'FOOTER']);

    fireEvent.change(ubicacion, { target: { value: 'FOOTER' } });
    const footer = screen.getByRole('contentinfo');
    await waitFor(() => expect(within(footer).getByRole('img', { name: 'Logo de la Universidad Autónoma' })).toBeInTheDocument());
    expect(within(screen.getByRole('banner')).queryByRole('img', { name: 'Logo de la Universidad Autónoma' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', { ubicacion_logo_universidad: 'FOOTER' }));
  });

  it('si la configuración no carga no deja editar: el borrador partiría vacío y pisaría la tienda', async () => {
    // Pasó con una migración sin aplicar: el servidor respondía 500 y el editor abría con todo vacío
    const errorConsola = vi.spyOn(console, 'error').mockImplementation(() => {});
    localStorage.setItem('rol', 'ADMIN');
    getMock.mockImplementation((url) => (url === 'configuracion/'
      ? Promise.reject({ response: { status: 500 } })
      : Promise.resolve({ data: [] })));
    await renderLanding();

    expect(await screen.findByRole('alert')).toHaveTextContent('no se puede editar la página');
    expect(screen.queryByRole('button', { name: 'Editar página' })).not.toBeInTheDocument();
    errorConsola.mockRestore();
  });

  it('solo el admin ve el botón para editar la página', async () => {
    localStorage.setItem('rol', 'COMPRADOR');
    responder();
    await renderLanding();

    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('button', { name: 'Editar página' })).not.toBeInTheDocument();
  });

  it('guarda solo los textos que cambiaron y avisa que están publicados', async () => {
    await entrarComoAdmin();

    fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Arte para tus paredes' } });
    expect(screen.getByText('Tienes cambios sin guardar')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(
      'configuracion/negocio/', { texto_bienvenida: 'Arte para tus paredes' }));
    expect(await screen.findByText(/Cambios guardados/)).toBeInTheDocument();
  });

  it('una imagen nueva viaja en multipart junto con los textos; quitar una imagen es un null', async () => {
    await entrarComoAdmin();
    const archivo = new File(['png'], 'portada.png', { type: 'image/png' });

    fireEvent.change(screen.getByLabelText('Nombre de Catálogo'), { target: { value: 'Obras' } });
    fireEvent.change(screen.getByLabelText('Subir imagen de portada'), { target: { files: [archivo] } });
    fireEvent.change(screen.getByLabelText('Subir logo'), { target: { files: [archivo] } });
    fireEvent.click(screen.getByRole('button', { name: 'Quitar logo' }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(2));
    const [, formulario, opciones] = patchMock.mock.calls[0];
    expect(formulario).toBeInstanceOf(FormData);
    expect(formulario.get('banner_fotos')).toBe(archivo);
    expect(JSON.parse(formulario.get('menu_principal'))).toEqual({ nombres: { catalogo: 'Obras' } });
    // El navegador pone el multipart con su boundary (axios fija JSON por defecto)
    expect(opciones).toEqual({ headers: { 'Content-Type': undefined } });
    expect(patchMock.mock.calls[1]).toEqual(['configuracion/negocio/', { logo: null }]);
  });

  it('las fotos de Instagram se suben desde el modo edición en el mismo multipart', async () => {
    await entrarComoAdmin();
    const archivo = new File(['png'], 'instagram.png', { type: 'image/png' });

    // Sin usuario la sección igual aparece en modo edición, con el aviso de dónde configurarlo
    expect(screen.getByText(/Configuración > Contacto y Redes/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Subir foto 3'), { target: { files: [archivo] } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1));
    expect(patchMock.mock.calls[0][1].get('instagram_foto_3')).toBe(archivo);
  });

  it('no guarda si un campo obligatorio queda vacío', async () => {
    await entrarComoAdmin();

    fireEvent.change(screen.getByLabelText('Título'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findAllByText(/No puede quedar vacío/)).not.toHaveLength(0);
    expect(patchMock).not.toHaveBeenCalled();
  });

  it('rechaza archivos que no son JPEG, PNG o WebP antes de enviarlos', async () => {
    await entrarComoAdmin();
    const svg = new File(['<svg/>'], 'logo.svg', { type: 'image/svg+xml' });

    fireEvent.change(screen.getByLabelText('Subir logo'), { target: { files: [svg] } });

    expect(await screen.findAllByText('Solo se admiten imágenes JPEG, PNG o WebP.')).not.toHaveLength(0);
    expect(screen.getByText('Sin cambios')).toBeInTheDocument();
  });

  it('descartar vuelve a los textos publicados', async () => {
    await entrarComoAdmin();

    fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Otro título' } });
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));

    expect(screen.getByLabelText('Título')).toHaveValue('Objetos con alma');
    expect(screen.getByText('Sin cambios')).toBeInTheDocument();
  });

  it('con dos o más fotos, el banner tiene carrusel y botón para pausar y reanudar (WCAG 2.2.2)', async () => {
    responder({
      configuracion: {
        ...CONFIGURACION,
        banners: [
          { id: 1, imagen: 'http://localhost:8000/media/negocio/banners/obra1.webp', orden: 0 },
          { id: 2, imagen: 'http://localhost:8000/media/negocio/banners/obra2.webp', orden: 1 },
        ],
      },
    });
    await renderLanding();

    const botonPausa = await screen.findByRole('button', { name: /pausar carrusel/i });
    expect(botonPausa).toBeInTheDocument();

    fireEvent.click(botonPausa);
    const botonReanudar = await screen.findByRole('button', { name: /reanudar carrusel/i });
    expect(botonReanudar).toBeInTheDocument();

    fireEvent.click(botonReanudar);
    expect(await screen.findByRole('button', { name: /pausar carrusel/i })).toBeInTheDocument();
  });

  it('con una sola foto o por defecto, el banner queda fijo y no muestra botón de pausa', async () => {
    responder({
      configuracion: {
        ...CONFIGURACION,
        banner: 'http://localhost:8000/media/negocio/banners/unica.webp',
      },
    });
    await renderLanding();

    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('button', { name: /pausar carrusel/i })).not.toBeInTheDocument();
  });

  it('el admin sube varias fotos al banner en modo edición, las reordena, las borra y las guarda', async () => {
    await entrarComoAdmin();
    const foto1 = new File(['1'], 'foto1.png', { type: 'image/png' });
    const foto2 = new File(['2'], 'foto2.png', { type: 'image/png' });

    // Sube dos fotos al banner
    fireEvent.change(screen.getByLabelText('Subir imagen de portada'), { target: { files: [foto1, foto2] } });

    // Espera que aparezcan en la lista del editor
    expect(await screen.findByRole('button', { name: /mover foto 2 hacia la izquierda/i })).toBeInTheDocument();

    // Reordena: mueve la segunda foto a la izquierda (primera posición)
    fireEvent.click(screen.getByRole('button', { name: /mover foto 2 hacia la izquierda/i }));

    // Borra la foto que ahora quedó en la segunda posición
    fireEvent.click(screen.getByRole('button', { name: /quitar foto 2 del banner/i }));

    // Guarda los cambios
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalled());
    const [, formulario] = patchMock.mock.calls[0];
    expect(formulario).toBeInstanceOf(FormData);
    expect(formulario.getAll('banner_fotos')).toHaveLength(1);
    expect(formulario.get('banner_orden')).toBeDefined();
  });
});

describe('LandingPage: el admin elige los destacados de la vitrina (RF-01.1)', () => {
  const PRODUCTOS_PANEL = [
    { id: 'p1', nombre: 'Retrato', publicado: true, imagenes: ['http://localhost/retrato.jpg'],
      variantes: [{ sku: 'p1-1', precio: 30000, stock: 1 }] },
    { id: 'p2', nombre: 'Boceto', publicado: false, imagenes: [], variantes: [] },
    { id: 'p3', nombre: 'Mural chico', publicado: true, imagenes: [], variantes: [{ sku: 'p3-1', precio: 9000, stock: 2 }] },
    // Para llenar los 8 destacados
    ...['Acuarela', 'Grabado', 'Collage', 'Escultura'].map((nombre, i) => ({
      id: `p${i + 4}`, nombre, publicado: true, imagenes: [], variantes: [{ sku: `p${i + 4}-1`, precio: 5000, stock: 1 }] })),
  ];
  const PUBLICACIONES_PANEL = [
    { id: 7, titulo: 'Mural en Cerro Alegre', slug: 'mural-cerro-alegre', estado: 'PUBLICADA', portada: null },
    { id: 8, titulo: 'Idea', slug: 'idea', estado: 'BORRADOR', portada: null },
    { id: 9, titulo: 'Taller abierto', slug: 'taller-abierto', estado: 'PUBLICADA', portada: null },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    patchMock.mockResolvedValue({ data: {} });
  });

  afterEach(() => cleanup());

  async function editarVitrina(configuracion = {}) {
    localStorage.setItem('rol', 'ADMIN');
    responder({ configuracion: { ...CONFIGURACION, blog_activo: true, blog_nombre: 'Portafolio', ...configuracion } });
    const respuesta = getMock.getMockImplementation();
    getMock.mockImplementation((url) => {
      if (url === 'catalogo/productos/?todos=true') return Promise.resolve({ data: PRODUCTOS_PANEL });
      if (url === 'ventas/admin/blog/') return Promise.resolve({ data: PUBLICACIONES_PANEL });
      return respuesta(url);
    });
    await renderLanding();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
  }

  function agregar(nombre) {
    const opcion = screen.getByRole('option', { name: nombre });
    fireEvent.change(screen.getByLabelText('Agregar un producto o una publicación'), { target: { value: opcion.value } });
    fireEvent.click(screen.getByRole('button', { name: 'Agregar' }));
  }

  const nombresElegidos = () => within(screen.getByRole('list', { name: /Tus destacados/ }))
    .getAllByRole('listitem').map((fila) => within(fila).getByText((_, el) => el.tagName === 'STRONG').textContent);

  it('por defecto la vitrina sigue en "Más vendidos" y no pide los productos ni las publicaciones', async () => {
    await editarVitrina();

    expect(screen.getByRole('radio', { name: /Más vendidos/ })).toBeChecked();
    expect(screen.getByRole('region', { name: 'Más vendidos' })).toBeInTheDocument();
    expect(getMock).not.toHaveBeenCalledWith('ventas/admin/blog/');
  });

  it('elige "Destacados", agrega hasta 8 productos y publicaciones, cambia el título y lo guarda', async () => {
    await editarVitrina();

    fireEvent.click(screen.getByRole('radio', { name: /Destacados/ }));
    expect(await screen.findByText('Tus destacados (0 de 8)')).toBeInTheDocument();
    // Solo se ofrecen los publicados
    expect(screen.queryByRole('option', { name: 'Boceto' })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'Idea' })).not.toBeInTheDocument();

    const ocho = ['Retrato', 'Mural en Cerro Alegre', 'Mural chico', 'Acuarela', 'Grabado', 'Collage', 'Escultura',
      'Taller abierto'];
    ocho.forEach(agregar);
    expect(nombresElegidos()).toEqual(ocho);
    expect(screen.getByLabelText('Agregar un producto o una publicación')).toBeDisabled();
    expect(screen.getByText(/Ya elegiste 8: quita uno para agregar otro/)).toBeInTheDocument();
    expect(screen.getByText('Taller abierto agregado a los destacados: 8 de 8.')).toHaveAttribute('role', 'status');

    fireEvent.change(screen.getByLabelText('Título de la sección'), { target: { value: 'Obras elegidas' } });
    // La vista previa ya muestra las 8 tarjetas con el título nuevo
    const seccion = screen.getByRole('region', { name: 'Obras elegidas' });
    expect(within(seccion).getByRole('link', { name: /Mural en Cerro Alegre/ }))
      .toHaveAttribute('href', '/blog/mural-cerro-alegre');
    expect(screen.queryByRole('region', { name: 'Más vendidos' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', {
      vitrina_modo: 'DESTACADOS',
      destacados_titulo: 'Obras elegidas',
      destacados: [{ tipo: 'PRODUCTO', id: 'p1' }, { tipo: 'PUBLICACION', id: '7' }, { tipo: 'PRODUCTO', id: 'p3' },
        ...['p4', 'p5', 'p6', 'p7'].map((id) => ({ tipo: 'PRODUCTO', id })), { tipo: 'PUBLICACION', id: '9' }],
    }));
  });

  it('al guardar el cambio de "Más vendidos" a Destacados, la landing los muestra sin recargar la página', async () => {
    localStorage.setItem('rol', 'ADMIN');
    // El servidor guarda lo que llega y la vitrina responde según el modo guardado
    let config = { ...CONFIGURACION, vitrina_modo: 'MAS_VENDIDOS', destacados: [] };
    const vitrina = () => (config.vitrina_modo === 'DESTACADOS'
      ? { mas_vendidos: [], recientes: [], destacados_titulo: 'Destacados', destacados: [
        { tipo: 'PRODUCTO', id: 'p1', nombre: 'Retrato', categoria: 'Arte', imagen: null,
          enlace: '/catalogo/producto/p1', variantes: [{ sku: 'p1-1', precio: 30000, stock: 1 }] }] }
      : { mas_vendidos: [producto('a', 'Jarrón')], recientes: [] });
    getMock.mockImplementation((url) => Promise.resolve({ data: {
      'configuracion/': config, 'catalogo/vitrina/': vitrina(), 'catalogo/productos/?todos=true': PRODUCTOS_PANEL,
      'ventas/admin/blog/': PUBLICACIONES_PANEL,
    }[url] ?? [] }));
    patchMock.mockImplementation(async (_, datos) => { config = { ...config, ...datos }; return { data: config }; });

    await renderLanding();
    expect(await screen.findByRole('region', { name: 'Más vendidos' })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
    fireEvent.click(screen.getByRole('radio', { name: /Destacados/ }));
    await screen.findByText('Tus destacados (0 de 8)');
    agregar('Retrato');
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await screen.findByText(/Cambios guardados/);
    fireEvent.click(screen.getByRole('button', { name: 'Salir' }));

    const seccion = await screen.findByRole('region', { name: 'Destacados' });
    expect(within(seccion).getByRole('link', { name: /Retrato/ })).toHaveAttribute('href', '/catalogo/producto/p1');
    expect(screen.queryByRole('region', { name: 'Más vendidos' })).not.toBeInTheDocument();
    // Una vez al abrir y otra al guardar: no se pide de nuevo por cada recarga de la configuración
    expect(getMock.mock.calls.filter(([url]) => url === 'catalogo/vitrina/')).toHaveLength(2);
  });

  it('ordena con Subir y Bajar sin perder el foco, quita y guarda el nuevo orden', async () => {
    await editarVitrina({ vitrina_modo: 'DESTACADOS', destacados: [
      { tipo: 'PRODUCTO', id: 'p1' }, { tipo: 'PUBLICACION', id: '7' }, { tipo: 'PRODUCTO', id: 'p3' }] });
    await screen.findByText('Tus destacados (3 de 8)');

    fireEvent.click(screen.getByRole('button', { name: 'Bajar Retrato' }));
    expect(nombresElegidos()).toEqual(['Mural en Cerro Alegre', 'Retrato', 'Mural chico']);
    expect(screen.getByText('Retrato: posición 2 de 3.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Bajar Retrato' })).toHaveFocus());

    // Al llegar al final, "Bajar" se desactiva y el foco pasa a "Subir"
    fireEvent.click(screen.getByRole('button', { name: 'Bajar Retrato' }));
    expect(screen.getByRole('button', { name: 'Bajar Retrato' })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Subir Retrato' })).toHaveFocus());

    fireEvent.click(screen.getByRole('button', { name: 'Quitar Mural en Cerro Alegre' }));
    expect(nombresElegidos()).toEqual(['Mural chico', 'Retrato']);
    await waitFor(() => expect(screen.getByLabelText('Agregar un producto o una publicación')).toHaveFocus());

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', {
      destacados: [{ tipo: 'PRODUCTO', id: 'p3' }, { tipo: 'PRODUCTO', id: 'p1' }],
    }));
  });

  it('avisa cuáles no se verán y que, sin ninguno visible, la página muestra "Más vendidos"', async () => {
    await editarVitrina({ vitrina_modo: 'DESTACADOS', blog_activo: false, destacados: [
      { tipo: 'PRODUCTO', id: 'p2' }, { tipo: 'PUBLICACION', id: '7' }, { tipo: 'PRODUCTO', id: 'borrado' }] });

    expect(await screen.findByText('Sin publicar: no se mostrará.')).toBeInTheDocument();
    expect(screen.getByText('El blog está apagado: no se mostrará.')).toBeInTheDocument();
    expect(screen.getByText('Ya no existe: quítalo de la lista.')).toBeInTheDocument();
    expect(screen.getByText(/la página muestra «Más vendidos»/)).toBeInTheDocument();
    expect(screen.getByText(/no se mostrarán mientras el blog esté apagado/)).toBeInTheDocument();
    expect(document.querySelector('#destacados .grilla-destacados')).toBeNull();
  });

  it('descartar vuelve a la selección publicada', async () => {
    await editarVitrina({ vitrina_modo: 'DESTACADOS', destacados: [{ tipo: 'PRODUCTO', id: 'p1' }] });
    await screen.findByText('Tus destacados (1 de 8)');

    fireEvent.click(screen.getByRole('button', { name: 'Quitar Retrato' }));
    expect(screen.getByText('Tienes cambios sin guardar')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Descartar' }));

    expect(nombresElegidos()).toEqual(['Retrato']);
    expect(screen.getByText('Sin cambios')).toBeInTheDocument();
  });

  it('muestra el error del backend junto a la selección', async () => {
    await editarVitrina({ vitrina_modo: 'DESTACADOS', destacados: [{ tipo: 'PRODUCTO', id: 'p1' }] });
    await screen.findByText('Tus destacados (1 de 8)');
    patchMock.mockRejectedValue({ response: { data: { destacados: ['Uno de los destacados ya no existe.'] } } });

    agregar('Mural chico');
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    // La barra lo anuncia y el editor lo deja a la vista junto a la selección
    expect(await screen.findByRole('alert')).toHaveTextContent('Uno de los destacados ya no existe.');
    expect(document.querySelector('.editor-destacados-error')).toHaveTextContent('Uno de los destacados ya no existe.');
  });
});

