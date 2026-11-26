import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import FormularioProducto from '../components/FormularioProducto';
import clienteAxios from '../components/auth/axiosConfig';

// Video de YouTube opcional en la ficha del producto (pedido de Alan)
vi.mock('../components/auth/axiosConfig', () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn() } }));
vi.mock('../components/GaleriaImagenes', () => ({ default: () => <div>Galería de prueba</div> }));

const producto = { id: 'producto-video', nombre: 'Obra', descripcion: 'Original de prueba', categoria: 'Arte',
  publicado: true, variantes: [{ sku: 'VIDEO-1', precio: 10000, stock: 2 }] };
const campo = () => screen.getByRole('textbox', { name: 'Video de YouTube' });

beforeEach(() => {
  vi.clearAllMocks();
  clienteAxios.get.mockResolvedValue({ data: [producto] });
  clienteAxios.put.mockResolvedValue({ data: producto });
  clienteAxios.post.mockResolvedValue({ data: producto });
  vi.spyOn(window, 'alert').mockImplementation(() => {});
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function mostrar(datos = producto) {
  return render(<FormularioProducto productoAEditar={datos} alCancelar={vi.fn()} alGuardar={vi.fn()} />);
}

describe('Video de YouTube en el formulario del producto', () => {
  it('es opcional, empieza vacío y explica qué pegar', async () => {
    mostrar(null);
    await waitFor(() => expect(clienteAxios.get).toHaveBeenCalled());
    expect(campo()).toHaveValue('');
    expect(campo()).not.toBeRequired();
    expect(campo()).toHaveAccessibleDescription(/Opcional\. Pega el enlace de un video o Short de YouTube/);
  });

  it('muestra el video guardado como enlace y envía el que se escribe', async () => {
    const { container } = mostrar({ ...producto, youtube_id: 'dQw4w9WgXcQ' });
    expect(campo()).toHaveValue('https://www.youtube.com/watch?v=dQw4w9WgXcQ');

    fireEvent.change(campo(), { target: { value: '  https://youtu.be/aBcDeFgHiJk  ' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(clienteAxios.put).toHaveBeenCalledWith('catalogo/productos/producto-video/',
      expect.objectContaining({ youtube: 'https://youtu.be/aBcDeFgHiJk' })));
  });

  it('vacío quita el video', async () => {
    const { container } = mostrar({ ...producto, youtube_id: 'dQw4w9WgXcQ' });
    fireEvent.change(campo(), { target: { value: '' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(clienteAxios.put).toHaveBeenCalledWith('catalogo/productos/producto-video/',
      expect.objectContaining({ youtube: '' })));
  });

  it('muestra el error del backend junto al campo y lo limpia al volver a guardar', async () => {
    clienteAxios.put.mockRejectedValueOnce({ response: { data: {
      youtube: ['El enlace debe ser de YouTube (youtube.com o youtu.be).'] } } });
    const { container } = mostrar();
    fireEvent.change(campo(), { target: { value: 'https://vimeo.com/12345678901' } });
    fireEvent.submit(container.querySelector('form'));

    await waitFor(() => expect(campo()).toHaveAttribute('aria-invalid', 'true'));
    expect(campo()).toHaveAccessibleDescription(/El enlace debe ser de YouTube \(youtube\.com o youtu\.be\)\./);
    expect(screen.getByRole('alert')).toHaveTextContent('youtube: El enlace debe ser de YouTube');

    fireEvent.change(campo(), { target: { value: 'https://youtu.be/dQw4w9WgXcQ' } });
    fireEvent.submit(container.querySelector('form'));
    await waitFor(() => expect(campo()).not.toHaveAttribute('aria-invalid'));
    expect(screen.queryByText('El enlace debe ser de YouTube (youtube.com o youtu.be).')).not.toBeInTheDocument();
  });
});
