import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import Catalogo from '../pages/Catalogo';
const { get, configuracion } = vi.hoisted(() => ({ get: vi.fn(), configuracion: vi.fn() }));
vi.mock('../components/auth/axiosConfig', () => ({ default: { get } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: configuracion }));
vi.mock('../components/header/header', () => ({ default: () => null }));
vi.mock('../components/ProductCardGrid', () => ({ default: ({ producto }) => <h3>{producto.nombre}</h3> }));
afterEach(cleanup);

it('espera configuración, respeta la elección explícita y no ordena localmente una página', async () => {
  configuracion.mockReturnValue(null);
  get.mockResolvedValue({ data: { count: 2, total_pages: 1, results: [
    { id: '1', nombre: 'Zeta', categoria: 'Beta' }, { id: '2', nombre: 'Alfa', categoria: 'Alfa' }
  ], filtros: { categorias: ['Beta', 'Alfa'], atributos: {} } } });
  const { rerender } = render(<Catalogo />);
  expect(get).not.toHaveBeenCalled();
  configuracion.mockReturnValue({ orden_catalogo: 'precio-desc' });
  rerender(<Catalogo />);
  await screen.findByText('Zeta');
  expect(get).toHaveBeenCalledTimes(1);
  expect(get).toHaveBeenLastCalledWith('catalogo/productos/', expect.objectContaining({ params: { page: 1, page_size: 24, orden: 'precio-desc' } }));
  fireEvent.change(screen.getByLabelText('Ordenar por'), { target: { value: 'nombre' } });
  await waitFor(() => expect(get).toHaveBeenLastCalledWith('catalogo/productos/', expect.objectContaining({ params: { page: 1, page_size: 24, orden: 'nombre' } })));
  await waitFor(() => expect(screen.getAllByRole('heading', { level: 3 }).map(n => n.textContent)).toEqual(['Zeta', 'Alfa']));
  configuracion.mockReturnValue({ orden_catalogo: 'recientes' });
  rerender(<Catalogo />);
  expect(screen.getByLabelText('Ordenar por')).toHaveValue('nombre');
  expect(Array.from(screen.getByLabelText('Categoría').options).map(o => o.text)).toEqual(['Todas', 'Beta', 'Alfa']);
});
