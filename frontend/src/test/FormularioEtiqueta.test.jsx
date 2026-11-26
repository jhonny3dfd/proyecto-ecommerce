import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import FormularioProducto from '../components/FormularioProducto';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock('../components/GaleriaImagenes', () => ({ default: () => <div>Galería de prueba</div> }));

const producto = { id: 'producto-198', nombre: 'Obra', descripcion: 'Original de prueba', categoria: 'Arte',
  publicado: true, variantes: [{ sku: '198', precio: 10000, stock: 2 }] };

beforeEach(() => {
  vi.clearAllMocks();
  clienteAxios.get.mockResolvedValue({ data: [producto] });
  clienteAxios.put.mockResolvedValue({ data: producto });
  clienteAxios.post.mockResolvedValue({ data: producto });
  vi.spyOn(window, 'alert').mockImplementation(() => {});
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function mostrar(datos = producto) {
  return render(<FormularioProducto productoAEditar={datos} alCancelar={vi.fn()} alGuardar={vi.fn()} />);
}

describe('Formulario de etiqueta del producto', () => {
  it('los productos antiguos y los nuevos empiezan sin etiqueta y con color principal', async () => {
    const vista = mostrar();
    await waitFor(() => expect(clienteAxios.get).toHaveBeenCalled());
    expect(screen.getByRole('textbox', { name: 'Etiqueta' })).toHaveValue('');
    expect(screen.getByRole('radio', { name: 'Principal' })).toBeChecked();
    expect(screen.getByRole('textbox', { name: 'Etiqueta' })).toHaveAttribute('maxlength', '20');
    vista.unmount();
    mostrar(null);
    await waitFor(() => expect(screen.getByRole('textbox', { name: 'Etiqueta' })).toHaveValue(''));
    expect(screen.getByRole('radio', { name: 'Principal' })).toBeChecked();
  });

  it('permite elegir solo colores de la paleta, previsualizarlos y guardarlos', async () => {
    const { container } = mostrar();
    fireEvent.change(screen.getByRole('textbox', { name: 'Etiqueta' }), { target: { value: 'Edición limitada' } });
    fireEvent.click(screen.getByRole('radio', { name: 'Acento' }));
    expect(screen.getAllByRole('radio')).toHaveLength(4);
    expect(container.querySelector('input[type="color"]')).toBeNull();
    expect(within(screen.getByRole('group', { name: 'Vista previa de la etiqueta' })).getByText('Edición limitada'))
      .toHaveClass('tarjeta-producto-etiqueta--accent');
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(clienteAxios.put).toHaveBeenCalledWith('catalogo/productos/producto-198/',
      expect.objectContaining({ etiqueta: 'Edición limitada', etiqueta_color: 'accent' })));
  });

  it('carga la etiqueta guardada y permite quitarla', async () => {
    const { container } = mostrar({ ...producto, etiqueta: 'Único', etiqueta_color: 'secondary' });
    expect(screen.getByRole('textbox', { name: 'Etiqueta' })).toHaveValue('Único');
    expect(screen.getByRole('radio', { name: 'Secundario' })).toBeChecked();
    fireEvent.change(screen.getByRole('textbox', { name: 'Etiqueta' }), { target: { value: '' } });
    expect(screen.queryByRole('group', { name: 'Vista previa de la etiqueta' })).not.toBeInTheDocument();
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(clienteAxios.put).toHaveBeenCalledWith('catalogo/productos/producto-198/',
      expect.objectContaining({ etiqueta: '', etiqueta_color: 'secondary' })));
  });

  it('crea el producto y actualiza su etiqueta sin volver a crearlo', async () => {
    const { container } = mostrar(null);
    await waitFor(() => expect(clienteAxios.get).toHaveBeenCalled());
    fireEvent.change(screen.getByRole('textbox', { name: 'Nombre del Producto' }), { target: { value: 'Nueva obra' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'SKU' }), { target: { value: 'NUEVA-198' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Precio' }), { target: { value: '10000' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Stock' }), { target: { value: '1' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Etiqueta' }), { target: { value: '  Único  ' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(clienteAxios.post).toHaveBeenCalledWith('catalogo/productos/',
      expect.objectContaining({ etiqueta: 'Único', etiqueta_color: 'primary' })));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Guardar cambios del producto' })).toBeEnabled());
    fireEvent.change(screen.getByRole('textbox', { name: 'Etiqueta' }), { target: { value: 'Nueva edición' } });
    fireEvent.click(screen.getByRole('radio', { name: 'Oscuro' }));
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(clienteAxios.put).toHaveBeenCalledWith('catalogo/productos/producto-198/',
      expect.objectContaining({ etiqueta: 'Nueva edición', etiqueta_color: 'text' })));
    expect(clienteAxios.post).toHaveBeenCalledTimes(1);
  });

  it('muestra el rechazo del servidor sin perder el texto del formulario', async () => {
    clienteAxios.put.mockRejectedValue({ response: { data: { etiqueta: ['El texto supera 20 caracteres.'] } } });
    const { container } = mostrar({ ...producto, etiqueta: 'Últimas unidades' });
    fireEvent.submit(container.querySelector('form'));
    expect(await screen.findByRole('alert')).toHaveTextContent('El texto supera 20 caracteres.');
    expect(screen.getByRole('textbox', { name: 'Etiqueta' })).toHaveValue('Últimas unidades');
  });
});
