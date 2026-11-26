import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

import clienteAxios from '../components/auth/axiosConfig';
import GestorCategorias from '../components/GestorCategorias';

// RF-03.2: renombrar o unir categorías desde Configuración
const CATEGORIAS = [
  { nombre: 'Cafes', productos: 2, publicados: 1 },
  { nombre: 'Packs', productos: 3, publicados: 3 },
  { nombre: 'Promos', productos: 1, publicados: 1 }
];

describe('GestorCategorias', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: { categorias: CATEGORIAS } });
  });

  afterEach(() => cleanup());

  it('lista cada categoría con sus productos', async () => {
    render(<GestorCategorias />);

    expect(await screen.findByText('Cafes')).toBeInTheDocument();
    expect(screen.getByText('2 productos (1 publicados)')).toBeInTheDocument();
    expect(screen.getByText('1 producto')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /^Renombrar o unir/ })).toHaveLength(3);
  });

  it('renombra y avisa cuántos productos cambiaron', async () => {
    const alCambiar = vi.fn();
    clienteAxios.post.mockResolvedValue({ data: { desde: 'Cafes', hacia: 'Cafés', une: false, productos: 2,
      categorias: [{ nombre: 'Cafés', productos: 2, publicados: 1 }, ...CATEGORIAS.slice(1)] } });
    render(<GestorCategorias alCambiar={alCambiar} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Renombrar o unir Cafes' }));
    const campo = screen.getByLabelText('Nuevo nombre para «Cafes»');
    expect(campo).toHaveFocus();
    fireEvent.change(campo, { target: { value: 'Cafés' } });
    expect(screen.getByText('Sus 2 productos pasarán a «Cafés».')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Renombrar' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Renombraste «Cafes» a «Cafés» en 2 productos.');
    expect(clienteAxios.post).toHaveBeenCalledWith('catalogo/categorias/renombrar/', { desde: 'Cafes', hacia: 'Cafés' });
    expect(alCambiar).toHaveBeenCalled();
    expect(screen.getByText('Cafés')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Renombrar o unir Cafés' })).toHaveFocus());
  });

  it('al escribir el nombre de otra avisa que se unirán y pide confirmar', async () => {
    const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<GestorCategorias />);

    fireEvent.click(await screen.findByRole('button', { name: 'Renombrar o unir Promos' }));
    fireEvent.change(screen.getByLabelText('Nuevo nombre para «Promos»'), { target: { value: '  packs ' } });
    expect(screen.getByText(/Se unirá con «Packs» \(3 productos\): quedará una sola categoría con 4 productos/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Unir categorías' }));

    expect(confirmar).toHaveBeenCalled();
    expect(clienteAxios.post).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it('no envía un nombre vacío o igual, y Escape cancela', async () => {
    render(<GestorCategorias />);

    fireEvent.click(await screen.findByRole('button', { name: 'Renombrar o unir Packs' }));
    fireEvent.click(screen.getByRole('button', { name: 'Renombrar' }));
    expect(screen.getByText('Escribe un nombre distinto al actual.')).toBeInTheDocument();
    const campo = screen.getByLabelText('Nuevo nombre para «Packs»');
    expect(campo).toHaveAttribute('aria-invalid', 'true');
    fireEvent.change(campo, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Renombrar' }));
    expect(screen.getByText('Escribe el nombre nuevo de la categoría.')).toBeInTheDocument();
    expect(clienteAxios.post).not.toHaveBeenCalled();

    fireEvent.keyDown(campo, { key: 'Escape' });
    expect(screen.queryByLabelText('Nuevo nombre para «Packs»')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Renombrar o unir Packs' })).toHaveFocus());
  });

  it('muestra el error del servidor', async () => {
    clienteAxios.post.mockRejectedValue({ response: { data: { detail: 'Esa categoría ya no existe. Recarga la página.' } } });
    render(<GestorCategorias />);

    fireEvent.click(await screen.findByRole('button', { name: 'Renombrar o unir Cafes' }));
    fireEvent.change(screen.getByLabelText('Nuevo nombre para «Cafes»'), { target: { value: 'Café' } });
    fireEvent.click(screen.getByRole('button', { name: 'Renombrar' }));

    expect(await screen.findByText('Esa categoría ya no existe. Recarga la página.')).toBeInTheDocument();
  });
});
