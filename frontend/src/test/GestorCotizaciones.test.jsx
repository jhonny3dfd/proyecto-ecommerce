import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));

import clienteAxios from '../components/auth/axiosConfig';
import GestorCotizaciones from '../components/GestorCotizaciones';

const cotizacion = (id) => ({
  id, estado: 'NUEVA', estado_display: 'Nueva', producto_nombre: '', descripcion: `Encargo ${id}`, cantidad: 1,
  nombre: 'Ana', correo: 'ana@example.test', telefono: '+56912345678', fecha_creacion: '2026-10-23T12:00:00Z'
});

describe('GestorCotizaciones', () => {
  beforeEach(() => vi.clearAllMocks());

  afterEach(() => cleanup());

  it('pide las cotizaciones por página y deja avanzar y volver', async () => {
    clienteAxios.get.mockImplementation((_, { params }) => Promise.resolve({ data: {
      count: 25, results: params.pagina === 1 ? [cotizacion(25)] : [cotizacion(5)]
    } }));
    render(<GestorCotizaciones />);

    expect(await screen.findByText('Encargo 25')).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenCalledWith('ventas/admin/cotizaciones/', { params: { pagina: 1 } });
    expect(screen.getByText('Página 1 de 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Anteriores/ })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: /Siguientes/ }));

    expect(await screen.findByText('Encargo 5')).toBeInTheDocument();
    expect(clienteAxios.get).toHaveBeenLastCalledWith('ventas/admin/cotizaciones/', { params: { pagina: 2 } });
    expect(screen.getByText('Página 2 de 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Siguientes/ })).toBeDisabled();
  });

  it('con una sola página no muestra la paginación', async () => {
    clienteAxios.get.mockResolvedValue({ data: { count: 1, results: [cotizacion(1)] } });
    render(<GestorCotizaciones />);

    expect(await screen.findByText('Encargo 1')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Páginas de cotizaciones' })).not.toBeInTheDocument();
  });
});
