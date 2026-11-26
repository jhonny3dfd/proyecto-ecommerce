import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

const { getMock, patchMock } = vi.hoisted(() => ({ getMock: vi.fn(), patchMock: vi.fn() }));
vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock, patch: patchMock } }));

// RF-01.4: el admin elige si el catálogo se ve en grilla de 3, grilla de 4 o lista con descripción
describe('VistaCatalogoSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: { layout_catalogo: 'LISTA' } });
    patchMock.mockResolvedValue({ data: {} });
  });

  afterEach(() => cleanup());

  async function renderSelector() {
    // La configuración se guarda en el módulo: cada test parte limpio
    vi.resetModules();
    const { default: VistaCatalogoSelector } = await import('../components/VistaCatalogoSelector');
    return render(<VistaCatalogoSelector />);
  }

  it('ofrece las tres vistas, marca la guardada y solo deja guardar si se elige otra', async () => {
    await renderSelector();

    expect(await screen.findByRole('button', { name: /Lista con descripción/, pressed: true })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { pressed: false }).map((boton) => boton.textContent))
      .toEqual([expect.stringContaining('Cuadrícula de 3'), expect.stringContaining('Cuadrícula de 4')]);
    expect(screen.getByRole('button', { name: 'Guardar vista del catálogo' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /Cuadrícula de 4/ }));
    expect(screen.getByRole('button', { name: /Cuadrícula de 4/, pressed: true })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar vista del catálogo' })).toBeEnabled();
  });

  it('guarda la elegida en el servidor y avisa que el catálogo ya se ve así', async () => {
    await renderSelector();
    await screen.findByRole('button', { name: /Lista con descripción/, pressed: true });
    getMock.mockResolvedValue({ data: { layout_catalogo: 'GRID_4' } });

    fireEvent.click(screen.getByRole('button', { name: /Cuadrícula de 4/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar vista del catálogo' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledWith('configuracion/negocio/', { layout_catalogo: 'GRID_4' }));
    expect(await screen.findByRole('status')).toHaveTextContent('Vista guardada');
    expect(screen.getByRole('button', { name: 'Guardar vista del catálogo' })).toBeDisabled();
  });

  it('si el servidor falla, avisa sin dar por guardado el cambio', async () => {
    patchMock.mockRejectedValue(new Error('sin conexión'));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    await renderSelector();
    await screen.findByRole('button', { name: /Lista con descripción/, pressed: true });

    fireEvent.click(screen.getByRole('button', { name: /Cuadrícula de 3/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar vista del catálogo' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar');
    expect(screen.getByRole('button', { name: /Cuadrícula de 3/, pressed: true })).toBeInTheDocument();
  });

  it('sin vista guardada (o con una desconocida) marca la cuadrícula de 3, la de siempre', async () => {
    getMock.mockResolvedValue({ data: { layout_catalogo: 'OTRA' } });
    await renderSelector();
    expect(await screen.findByRole('button', { name: /Cuadrícula de 3/, pressed: true })).toBeInTheDocument();
  });
});
