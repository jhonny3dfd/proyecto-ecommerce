import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PORTADA_POR_DEFECTO } from '../components/landing/textosPorDefecto';
const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock } }));
vi.mock('../components/MenuUsuario', () => ({ default: () => null }));
vi.mock('../components/CarritoCompras', () => ({ default: () => null }));

// Login, registro y recuperar contraseña muestran la misma foto que se ve primero en la portada
async function fotoDelInicioDeSesion(configuracion) {
  getMock.mockImplementation((url) => Promise.resolve({ data: url === 'configuracion/' ? configuracion : [] }));
  // La configuración se guarda en el módulo: cada test parte limpio
  vi.resetModules();
  const { default: AuthLayout } = await import('../components/auth/AuthLayout');
  const { container } = render(<MemoryRouter><AuthLayout><p>Formulario</p></AuthLayout></MemoryRouter>);
  // El nombre sobre la foto aparece cuando la configuración ya cargó
  await waitFor(() => expect(container.querySelector('.auth-imagen-nombre')).not.toBeNull());
  return container.querySelector('.auth-imagen').style.backgroundImage;
}

describe('AuthLayout', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(cleanup);

  it('con carrusel, usa la primera foto (la foto antigua ya pasó al carrusel)', async () => {
    const foto = await fotoDelInicioDeSesion({
      nombre_tienda: 'Tienda QA', banner: null,
      banners: [{ id: 3, imagen: '/media/primera.webp' }, { id: 4, imagen: '/media/segunda.webp' }],
    });
    expect(foto).toBe('url("/media/primera.webp")');
  });

  it('sin carrusel, usa la foto antigua de la portada', async () => {
    expect(await fotoDelInicioDeSesion({ nombre_tienda: 'Tienda QA', banner: '/media/antigua.webp' }))
      .toBe('url("/media/antigua.webp")');
  });

  it('sin ninguna foto, usa la de ejemplo', async () => {
    expect(await fotoDelInicioDeSesion({ nombre_tienda: 'Tienda QA', banners: [] }))
      .toBe(`url("${PORTADA_POR_DEFECTO}")`);
  });
});
