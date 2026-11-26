import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import FormularioProducto from '../components/FormularioProducto';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), put: vi.fn() } }));
vi.mock('../components/GaleriaImagenes', () => ({ default: () => <div /> }));

const INVENTARIO = 'catalogo/productos/?todos=true';
const producto = { id: 'colecciones', nombre: 'Obra', descripcion: 'Prueba', categoria: 'Arte',
  publicado: true, variantes: [{ sku: 'COL', precio: 10000, stock: 2 }] };

function inventario(productos) {
  clienteAxios.get.mockImplementation(() => Promise.resolve({ data: productos }));
}

beforeEach(() => {
  vi.clearAllMocks();
  inventario([producto, { ...producto, publicado: false, colecciones: ['Solo borrador'] },
    { ...producto, activo: false, colecciones: ['Solo inactivo'] },
    { ...producto, colecciones: ['Cyber', 'cyber', 'iPhone', 'iphone'] }]);
  clienteAxios.put.mockResolvedValue({ data: producto });
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function mostrar() {
  return render(<FormularioProducto productoAEditar={producto} alGuardar={vi.fn()} alCancelar={vi.fn()} />);
}

async function abrirOpciones() {
  await waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith(INVENTARIO));
  const input = screen.getByRole('combobox', { name: 'Colecciones (Opcional)' });
  fireEvent.keyDown(input, { key: 'ArrowDown' });
  return input;
}

it('sugiere las colecciones de todo el inventario, borradores incluidos, sin repetir variantes de nombre', async () => {
  mostrar();
  await abrirOpciones();
  const lista = await screen.findByRole('listbox');
  expect(within(lista).getAllByRole('option')).toHaveLength(3);
  expect(screen.getByRole('option', { name: 'Cyber' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'iPhone' })).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Solo borrador' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'cyber' })).not.toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'iphone' })).not.toBeInTheDocument();
  expect(screen.queryByText('Solo inactivo')).not.toBeInTheDocument();
});

it('no pide las colecciones al filtro público, que no ve los borradores', async () => {
  mostrar();
  await abrirOpciones();
  await screen.findByRole('listbox');
  expect(clienteAxios.get).not.toHaveBeenCalledWith('catalogo/filtros/');
});

it('una colección usada solo en borradores no se puede volver a crear con otra escritura', async () => {
  inventario([{ ...producto, publicado: false, colecciones: ['Cyber Day'] }]);
  mostrar();
  const input = await abrirOpciones();
  expect(await screen.findByRole('option', { name: 'Cyber Day' })).toBeInTheDocument();
  fireEvent.change(input, { target: { value: 'cyber day' } });
  expect(screen.queryByText('Crear colección "cyber day"')).not.toBeInTheDocument();
});

it('permite seleccionar una existente y crear una nueva sin duplicar variantes de nombre', async () => {
  const { container } = mostrar();
  const input = await abrirOpciones();
  fireEvent.click(await screen.findByRole('option', { name: 'iPhone' }));
  fireEvent.change(input, { target: { value: ' cyber ' } });
  expect(screen.queryByText('Crear colección " cyber "')).not.toBeInTheDocument();
  fireEvent.change(input, { target: { value: 'Navidad' } });
  fireEvent.click(await screen.findByRole('option', { name: 'Crear colección "Navidad"' }));
  fireEvent.submit(container.querySelector('form'));
  await waitFor(() => expect(clienteAxios.put).toHaveBeenCalledWith('catalogo/productos/colecciones/',
    expect.objectContaining({ colecciones: ['iPhone', 'Navidad'] })));
});

it('reconoce una colección ya seleccionada aunque su escritura difiera de la opción global', async () => {
  render(<FormularioProducto productoAEditar={{ ...producto, colecciones: ['cyber'] }}
    alGuardar={vi.fn()} alCancelar={vi.fn()} />);
  await abrirOpciones();
  expect(await screen.findByRole('option', { name: 'iPhone' })).toBeInTheDocument();
  expect(screen.queryByRole('option', { name: 'Cyber' })).not.toBeInTheDocument();
  expect(screen.getByText('cyber')).toBeInTheDocument();
});

it('si no se puede cargar el inventario, igual deja crear una colección', async () => {
  clienteAxios.get.mockRejectedValue(new Error('sin conexión'));
  vi.spyOn(console, 'error').mockImplementation(() => {});
  mostrar();
  await waitFor(() => expect(clienteAxios.get).toHaveBeenCalledWith(INVENTARIO));
  const input = screen.getByRole('combobox', { name: 'Colecciones (Opcional)' });
  fireEvent.change(input, { target: { value: 'Navidad' } });
  expect(await screen.findByRole('option', { name: 'Crear colección "Navidad"' })).toBeInTheDocument();
});
