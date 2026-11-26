import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import TablaInventario from '../components/TablaInventario';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), patch: vi.fn() } }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('expone las variantes mediante un botón y distingue las acciones de cada producto', async () => {
  const producto = { id: '148', nombre: 'Jarrón QA', variantes: [{ sku: 'QA148', stock: 3, precio: 1000 }], imagenes: [] };
  clienteAxios.get.mockResolvedValue({ data: { results: [producto] } });
  const editar = vi.fn();
  render(<TablaInventario onEditarProducto={editar} />);
  const expandir = await screen.findByRole('button', { name: 'Mostrar variantes de Jarrón QA' });
  expect(clienteAxios.get).toHaveBeenCalledWith('catalogo/productos/?todos=true');
  expect(expandir).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(expandir);
  expect(screen.getByText('QA148')).toBeInTheDocument();
  expect(expandir).toHaveAttribute('aria-expanded', 'true');
  fireEvent.click(screen.getByRole('button', { name: 'Editar Jarrón QA' }));
  expect(editar).toHaveBeenCalledWith(producto);
  expect(expandir).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('button', { name: 'Borrar Jarrón QA' })).toBeInTheDocument();
  fireEvent.click(expandir);
  expect(screen.queryByText('QA148')).not.toBeInTheDocument();
});

describe('mensajes de inventario', () => {
  it('anuncia la carga y el error de la consulta', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.get.mockRejectedValue(new Error('Indisponible'));
    render(<TablaInventario />);
    expect(screen.getByRole('status')).toHaveTextContent('Cargando inventario');
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo cargar');
    vi.restoreAllMocks();
  });
});
