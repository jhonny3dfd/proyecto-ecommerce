import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn() } }));

let useConfiguracionTienda;
let recargarConfiguracion;

beforeEach(async () => {
  vi.resetModules();
  vi.clearAllMocks();
  ({ default: useConfiguracionTienda, recargarConfiguracion } = await import('../hooks/useConfiguracionTienda'));
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('consumo compartido de configuración', () => {
  it('comparte una sola lectura en curso entre los consumidores iniciales', async () => {
    clienteAxios.get.mockResolvedValue({ data: { nombre_tienda: 'Inicial', layout_catalogo: 'GRID_3' } });
    const app = renderHook(() => useConfiguracionTienda());
    const catalogo = renderHook(() => useConfiguracionTienda({ refrescar: true }));
    const header = renderHook(() => useConfiguracionTienda());
    await waitFor(() => expect(catalogo.result.current?.nombre_tienda).toBe('Inicial'));
    expect(app.result.current).toEqual(header.result.current);
    expect(clienteAxios.get).toHaveBeenCalledTimes(1);
  });

  it('consulta nuevamente al volver al catálogo y avisa a los consumidores montados', async () => {
    clienteAxios.get.mockResolvedValueOnce({ data: { nombre_tienda: 'Inicial' } })
      .mockResolvedValueOnce({ data: { nombre_tienda: 'Editada', layout_catalogo: 'LISTA' } });
    const app = renderHook(() => useConfiguracionTienda());
    await waitFor(() => expect(app.result.current?.nombre_tienda).toBe('Inicial'));
    const catalogo = renderHook(() => useConfiguracionTienda({ refrescar: true }));
    await waitFor(() => expect(catalogo.result.current?.layout_catalogo).toBe('LISTA'));
    expect(app.result.current.nombre_tienda).toBe('Editada');
    expect(clienteAxios.get).toHaveBeenCalledTimes(2);
  });

  it('conserva la recarga explícita tras guardar desde el administrador', async () => {
    clienteAxios.get.mockResolvedValueOnce({ data: { nombre_tienda: 'Inicial' } })
      .mockResolvedValueOnce({ data: { nombre_tienda: 'Guardada', tema_seleccionado: 2 } });
    const app = renderHook(() => useConfiguracionTienda());
    await waitFor(() => expect(app.result.current?.nombre_tienda).toBe('Inicial'));
    await act(async () => { await recargarConfiguracion(); });
    expect(app.result.current.nombre_tienda).toBe('Guardada');
    expect(app.result.current.tema_seleccionado).toBe(2);
    expect(clienteAxios.get).toHaveBeenCalledTimes(2);
  });

  it('permite reintentar después de una lectura fallida', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.get.mockRejectedValueOnce(new Error('Fallo QA'))
      .mockResolvedValueOnce({ data: { nombre_tienda: 'Recuperada' } });
    const first = renderHook(() => useConfiguracionTienda());
    await waitFor(() => expect(first.result.current).toEqual({}));
    first.unmount();
    const retry = renderHook(() => useConfiguracionTienda({ refrescar: true }));
    await waitFor(() => expect(retry.result.current?.nombre_tienda).toBe('Recuperada'));
    expect(clienteAxios.get).toHaveBeenCalledTimes(2);
  });
});

describe('presentación que elige el admin (fotos, ficha y logo)', () => {
  const marcas = () => ({ ...document.documentElement.dataset });

  it('marca <html> con las opciones activas y las quita al apagarlas', async () => {
    clienteAxios.get.mockResolvedValueOnce({ data: { nombre_tienda: 'Taller', fotos_completas: true,
      ficha_horizontal: true, logo_grande: true } })
      .mockResolvedValueOnce({ data: { nombre_tienda: 'Taller', fotos_completas: false, ficha_horizontal: true,
        logo_grande: false } });
    const tienda = renderHook(() => useConfiguracionTienda());
    await waitFor(() => expect(tienda.result.current?.nombre_tienda).toBe('Taller'));
    expect(marcas()).toMatchObject({ fotos: 'completas', ficha: 'horizontal', logo: 'grande' });

    await act(async () => { await recargarConfiguracion(); });
    expect(marcas()).toEqual(expect.objectContaining({ ficha: 'horizontal' }));
    expect(marcas()).not.toHaveProperty('fotos');
    expect(marcas()).not.toHaveProperty('logo');
  });

  it('por defecto no marca nada: la tienda se ve como antes', async () => {
    clienteAxios.get.mockResolvedValue({ data: { nombre_tienda: 'Otra tienda' } });
    const tienda = renderHook(() => useConfiguracionTienda());
    await waitFor(() => expect(tienda.result.current?.nombre_tienda).toBe('Otra tienda'));
    expect(marcas()).not.toHaveProperty('fotos');
    expect(marcas()).not.toHaveProperty('ficha');
    expect(marcas()).not.toHaveProperty('logo');
  });
});
