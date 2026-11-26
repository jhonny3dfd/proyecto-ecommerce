import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({ default: { post: vi.fn(), delete: vi.fn() } }));

import clienteAxios from '../components/auth/axiosConfig';
import GaleriaImagenes from '../components/GaleriaImagenes';

const png = (nombre = 'foto.png', tipo = 'image/png') => new File(['png'], nombre, { type: tipo });

function renderGaleria() {
  return render(
    <GaleriaImagenes productoId="p1" imagenes={[]} archivosGestionados={[]}
      onImagenesChange={vi.fn()} onArchivosChange={vi.fn()} />
  );
}

describe('GaleriaImagenes (RF-03.2)', () => {
  beforeEach(() => {
    // jsdom no implementa las vistas previas de archivos
    URL.createObjectURL = vi.fn(() => 'blob:vista-previa');
  });

  afterEach(() => cleanup());

  it('un clic en la zona abre el selector de archivos una sola vez', () => {
    renderGaleria();
    const input = screen.getByLabelText('Seleccionar imágenes para la galería');
    const clics = vi.fn();
    input.addEventListener('click', (e) => {
      clics();
      // Sin esto, jsdom intentaría abrir el selector
      e.preventDefault();
    });

    fireEvent.click(screen.getByText('Arrastra tus imágenes aquí'));

    // Antes el input estaba dentro de la zona y su clic volvía a ella: el selector se abría en bucle
    expect(clics).toHaveBeenCalledTimes(1);
  });

  it('el selector es un campo de archivos que acepta solo JPEG, PNG y WebP', () => {
    renderGaleria();
    const input = screen.getByLabelText('Seleccionar imágenes para la galería');

    expect(input).toHaveAttribute('type', 'file');
    expect(input).toHaveAttribute('accept', 'image/jpeg,image/png,image/webp');
    expect(input).toHaveAccessibleDescription('Formatos permitidos: JPG, PNG y WebP');
  });

  it('las imágenes elegidas o arrastradas quedan listas para subir y se descartan las de otro formato', () => {
    renderGaleria();

    fireEvent.change(screen.getByLabelText('Seleccionar imágenes para la galería'),
      { target: { files: [png('uno.png'), png('nota.gif', 'image/gif')] } });
    fireEvent.drop(screen.getByText('Arrastra tus imágenes aquí'),
      { dataTransfer: { files: [png('dos.webp', 'image/webp')] } });

    expect(screen.getByRole('img', { name: 'uno.png' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'dos.webp' })).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'nota.gif' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Subir imágenes' })).toBeInTheDocument();
  });
});

describe('GaleriaImagenes: eliminar imágenes de la galería (RF-03.2)', () => {
  const ENLACE = 'https://mi-tienda.com/img/camisa-azul.jpg';
  const ID_SUBIDA = '0123456789abcdef0123456789abcdef';
  const SUBIDA = `http://localhost:8000/media/catalogo/productos/6a9c4857840a5322b7c5a3df/${ID_SUBIDA}.webp`;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    clienteAxios.delete.mockResolvedValue({ status: 204 });
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  function renderConImagenes(imagenes, archivosGestionados = []) {
    const props = { onImagenesChange: vi.fn(), onArchivosChange: vi.fn() };
    render(<GaleriaImagenes productoId="p1" imagenes={imagenes} archivosGestionados={archivosGestionados} {...props} />);
    return props;
  }

  const eliminar = (posicion) => fireEvent.click(screen.getAllByRole('button', { name: /^Eliminar imagen/ })[posicion]);

  it('una imagen cargada como enlace solo se quita de la galería', async () => {
    const { onImagenesChange } = renderConImagenes([ENLACE]);

    eliminar(0);

    await vi.waitFor(() => expect(onImagenesChange).toHaveBeenCalledWith([]));
    expect(clienteAxios.delete).toHaveBeenCalledWith('catalogo/productos/p1/imagenes/enlace/', { params: { url: ENLACE } });
  });

  it('una foto subida se borra por su ID, también al editar un producto sin archivos cargados', async () => {
    const { onImagenesChange } = renderConImagenes([SUBIDA]);

    eliminar(0);

    await vi.waitFor(() => expect(onImagenesChange).toHaveBeenCalledWith([]));
    expect(clienteAxios.delete).toHaveBeenCalledWith(`catalogo/productos/p1/imagenes/${ID_SUBIDA}/`);
  });

  it('en una galería con enlaces y fotos subidas, quitar el enlace no borra la foto que está en su posición', async () => {
    const archivos = [{ id: ID_SUBIDA, url: SUBIDA }];
    const { onImagenesChange, onArchivosChange } = renderConImagenes([ENLACE, SUBIDA], archivos);

    eliminar(0);

    await vi.waitFor(() => expect(onImagenesChange).toHaveBeenCalledWith([SUBIDA]));
    expect(clienteAxios.delete).toHaveBeenCalledTimes(1);
    expect(clienteAxios.delete).toHaveBeenCalledWith('catalogo/productos/p1/imagenes/enlace/', { params: { url: ENLACE } });
    expect(onArchivosChange).toHaveBeenCalledWith(archivos);
  });

  it('si el servidor rechaza el borrado, lo avisa y la imagen sigue en la galería', async () => {
    clienteAxios.delete.mockRejectedValue({ response: { data: { detail: 'Enlace no encontrado en este producto.' } } });
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { onImagenesChange } = renderConImagenes([ENLACE]);

    eliminar(0);

    expect(await screen.findByRole('alert')).toHaveTextContent('Enlace no encontrado en este producto.');
    expect(onImagenesChange).not.toHaveBeenCalled();
  });
});
