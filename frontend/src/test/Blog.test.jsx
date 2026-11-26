import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock } }));
vi.mock('../components/MenuUsuario', () => ({ default: () => null }));
vi.mock('../components/CarritoCompras', () => ({ default: () => null }));

const CONFIGURACION = { nombre_tienda: 'Taller Maché', blog_activo: true, blog_nombre: 'Portafolio' };
const TARJETA = {
  titulo: 'Nuestro taller', slug: 'nuestro-taller', resumen: 'Cómo trabajamos',
  portada: 'http://localhost:8000/media/blog/portadas/a.png', fecha_publicacion: '2026-10-23T12:00:00Z'
};
const PUBLICACION = {
  ...TARJETA, contenido: '<p>Desde 2015 en Valparaíso.</p>',
  fotos: [1, 2, 3].map((id) => ({ id, imagen: `http://localhost:8000/media/blog/fotos/${id}.png` }))
};

const noEncontrada = () => Promise.reject({ response: { status: 404, data: { detail: 'Esta página no está disponible.' } } });

function responder({ configuracion = CONFIGURACION, blog, publicacion } = {}) {
  getMock.mockImplementation((url) => {
    if (url === 'configuracion/') return Promise.resolve({ data: configuracion });
    if (url === 'ventas/blog/') return blog ? blog() : Promise.resolve({ data: { resultados: [TARJETA], total: 1, pagina: 1, paginas: 1 } });
    if (url.startsWith('ventas/blog/')) return publicacion ? publicacion() : Promise.resolve({ data: PUBLICACION });
    return Promise.resolve({ data: [] });
  });
}

async function renderEn(ruta) {
  // La configuración se guarda entre montajes: cada test parte con el módulo limpio
  vi.resetModules();
  const [{ default: Blog }, { default: PublicacionBlog }] = await Promise.all([
    import('../pages/Blog'), import('../pages/PublicacionBlog')
  ]);
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/blog" element={<Blog />} />
        <Route path="/blog/:slug" element={<PublicacionBlog />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Página del blog', () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => {
    cleanup();
    // Los tests del video guardan un consentimiento de cookies: no debe pasar al siguiente
    localStorage.clear();
  });

  it('lista las publicaciones con el nombre que eligió el admin', async () => {
    responder();
    await renderEn('/blog');

    expect(await screen.findByRole('heading', { level: 1, name: 'Portafolio' })).toBeInTheDocument();
    const tarjeta = screen.getByRole('article');
    expect(within(tarjeta).getByRole('link', { name: 'Nuestro taller' })).toHaveAttribute('href', '/blog/nuestro-taller');
    expect(within(tarjeta).getByText('Cómo trabajamos')).toBeInTheDocument();
    expect(within(tarjeta).getByText('23 de octubre de 2026')).toBeInTheDocument();
  });

  it('pide la página de la URL y ofrece ir a la anterior y la siguiente', async () => {
    responder({ blog: () => Promise.resolve({ data: { resultados: [TARJETA], total: 25, pagina: 2, paginas: 3 } }) });
    await renderEn('/blog?pagina=2');

    const paginacion = await screen.findByRole('navigation', { name: 'Páginas de Portafolio' });
    expect(getMock).toHaveBeenCalledWith('ventas/blog/', { params: { pagina: 2 } });
    expect(within(paginacion).getByText('Página 2 de 3')).toBeInTheDocument();
    expect(within(paginacion).getByRole('link', { name: /Anteriores/ })).toHaveAttribute('href', '/blog?pagina=1');
    expect(within(paginacion).getByRole('link', { name: /Siguientes/ })).toHaveAttribute('href', '/blog?pagina=3');
  });

  it('sin publicaciones lo dice', async () => {
    responder({ blog: () => Promise.resolve({ data: { resultados: [], total: 0, pagina: 1, paginas: 0 } }) });
    await renderEn('/blog');

    expect(await screen.findByText('Aún no hay publicaciones. Vuelve pronto.')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: /Páginas/ })).not.toBeInTheDocument();
  });

  it('con el blog apagado avisa que la página no está disponible', async () => {
    responder({ configuracion: { ...CONFIGURACION, blog_activo: false }, blog: noEncontrada });
    await renderEn('/blog');

    expect(await screen.findByRole('heading', { name: 'Esta página no está disponible' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ir al inicio' })).toHaveAttribute('href', '/');
  });

  it('un error de conexión se distingue de un blog apagado', async () => {
    responder({ blog: () => Promise.reject(new Error('sin red')) });
    await renderEn('/blog');

    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos cargar esta página');
  });
});

describe('Página de una publicación', () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => {
    cleanup();
    document.body.style.overflow = '';
  });

  it('muestra el título, la portada, el texto y la galería', async () => {
    responder();
    await renderEn('/blog/nuestro-taller');

    expect(await screen.findByRole('heading', { level: 1, name: 'Nuestro taller' })).toBeInTheDocument();
    expect(getMock).toHaveBeenCalledWith('ventas/blog/nuestro-taller/');
    expect(screen.getByRole('img', { name: 'Portada de "Nuestro taller"' })).toBeInTheDocument();
    expect(screen.getByText('Desde 2015 en Valparaíso.')).toBeInTheDocument();
    // El header también enlaza el blog: se busca el "volver" dentro del contenido
    expect(within(screen.getByRole('main')).getByRole('link', { name: /Portafolio/ })).toHaveAttribute('href', '/blog');
    const galeria = screen.getByRole('region', { name: 'Galería' });
    expect(within(galeria).getAllByRole('button', { name: /^Ver en grande/ })).toHaveLength(3);
  });

  it('el visor se recorre con el teclado y al cerrarlo el foco vuelve a la miniatura', async () => {
    responder();
    await renderEn('/blog/nuestro-taller');

    const segunda = await screen.findByRole('button', { name: 'Ver en grande: Foto 2 de 3 de "Nuestro taller"' });
    fireEvent.click(segunda);

    const visor = screen.getByRole('dialog', { name: 'Galería de "Nuestro taller"' });
    expect(within(visor).getByRole('img')).toHaveAccessibleName('Foto 2 de 3 de "Nuestro taller"');
    expect(within(visor).getByRole('button', { name: 'Cerrar' })).toHaveFocus();
    expect(document.body.style.overflow).toBe('hidden');

    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(within(visor).getByRole('img')).toHaveAccessibleName('Foto 3 de 3 de "Nuestro taller"');
    fireEvent.keyDown(document, { key: 'ArrowRight' });
    expect(within(visor).getByText('1 de 3')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'ArrowLeft' });
    expect(within(visor).getByText('3 de 3')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(segunda).toHaveFocus();
    expect(document.body.style.overflow).toBe('');
  });

  it('con Tab el foco no sale del visor', async () => {
    responder();
    await renderEn('/blog/nuestro-taller');

    fireEvent.click(await screen.findByRole('button', { name: /Foto 1 de 3/ }));
    const visor = screen.getByRole('dialog');
    const anterior = within(visor).getByRole('button', { name: /Anterior/ });
    const cerrar = within(visor).getByRole('button', { name: 'Cerrar' });

    fireEvent.keyDown(document, { key: 'Tab' });
    expect(anterior).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(cerrar).toHaveFocus();
  });

  it('una publicación que no existe ofrece volver al blog', async () => {
    responder({ publicacion: noEncontrada });
    await renderEn('/blog/no-existe');

    expect(await screen.findByRole('heading', { name: 'Publicación no encontrada' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver Portafolio' })).toHaveAttribute('href', '/blog');
  });

  it('muestra la miniatura del video de YouTube y carga el reproductor de youtube-nocookie al hacer click (RF-04.4, SCRUM-195)', async () => {
    responder({
      publicacion: () => Promise.resolve({ data: { ...PUBLICACION, youtube_id: 'dQw4w9WgXcQ' } })
    });
    await renderEn('/blog/nuestro-taller');

    // Hasta el clic, no se carga ningún iframe de YouTube ni conexión a img.youtube.com (RF-04.4)
    expect(screen.queryByTitle(/Reproductor de video/i)).not.toBeInTheDocument();
    expect(document.querySelector('img[src*="ytimg.com"], img[src*="youtube.com"]')).toBeNull();
    const botonPlay = await screen.findByRole('button', { name: 'Reproducir video: Nuestro taller' });
    expect(botonPlay).toBeInTheDocument();

    // Al hacer clic, se monta el iframe desde youtube-nocookie.com
    fireEvent.click(botonPlay);
    const iframe = screen.getByTitle('Reproductor de video: Nuestro taller');
    expect(iframe).toHaveAttribute('src', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1');
  });

  it('sin aceptar las cookies de marketing no pide la miniatura a YouTube: muestra la portada (RF-04.4, SCRUM-195)', async () => {
    localStorage.setItem('ecode_cookie_consent', JSON.stringify({
      analitica: true, marketing: false, fecha: new Date().toISOString() }));
    responder({ publicacion: () => Promise.resolve({ data: { ...PUBLICACION, youtube_id: 'dQw4w9WgXcQ' } }) });
    await renderEn('/blog/nuestro-taller');

    const boton = await screen.findByRole('button', { name: 'Reproducir video: Nuestro taller' });
    expect(boton.parentElement.querySelector('.video-youtube-miniatura')).toHaveAttribute('src', PUBLICACION.portada);
    expect(document.querySelector('img[src*="ytimg.com"], img[src*="youtube.com"]')).toBeNull();
  });

  it('con las cookies de marketing aceptadas muestra la miniatura del video (RF-04.4, SCRUM-195)', async () => {
    localStorage.setItem('ecode_cookie_consent', JSON.stringify({
      analitica: false, marketing: true, fecha: new Date().toISOString() }));
    responder({ publicacion: () => Promise.resolve({ data: { ...PUBLICACION, youtube_id: 'dQw4w9WgXcQ' } }) });
    await renderEn('/blog/nuestro-taller');

    const boton = await screen.findByRole('button', { name: 'Reproducir video: Nuestro taller' });
    expect(boton.parentElement.querySelector('.video-youtube-miniatura'))
      .toHaveAttribute('src', 'https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg');
    // El reproductor sigue cargándose solo al hacer clic
    expect(screen.queryByTitle(/Reproductor de video/i)).not.toBeInTheDocument();
  });

  it('con el blog apagado avisa que la página no está disponible', async () => {
    responder({ configuracion: { ...CONFIGURACION, blog_activo: false }, publicacion: noEncontrada });
    await renderEn('/blog/nuestro-taller');

    expect(await screen.findByRole('heading', { name: 'Esta página no está disponible' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ir al inicio' })).toHaveAttribute('href', '/');
  });
});
