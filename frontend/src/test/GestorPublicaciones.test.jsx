import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

const { configuracion } = vi.hoisted(() => ({ configuracion: { actual: { blog_activo: true } } }));

vi.mock('../components/auth/axiosConfig', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }
}));
vi.mock('../hooks/useConfiguracionTienda', () => ({ default: () => configuracion.actual }));
// Quill necesita APIs del navegador que jsdom no tiene: en los tests el editor es un textarea
vi.mock('react-quill-new', () => ({
  default: ({ value, onChange }) => (
    <textarea aria-label="Texto" value={value} onChange={(e) => onChange(e.target.value, null, 'user')} />
  )
}));

import clienteAxios from '../components/auth/axiosConfig';
import GestorPublicaciones from '../components/GestorPublicaciones';

const BORRADOR = {
  id: 1, titulo: 'Idea a medias', slug: 'idea-a-medias', resumen: '', contenido: '', portada: null, fotos: [],
  estado: 'BORRADOR', fecha_publicacion: null
};
const PUBLICADA = {
  id: 2, titulo: 'Nuestro taller', slug: 'nuestro-taller', resumen: 'Cómo trabajamos', contenido: '<p>Desde 2015.</p>',
  portada: 'http://localhost:8000/media/blog/portadas/a.png', estado: 'PUBLICADA',
  fecha_publicacion: '2026-10-23T12:00:00Z',
  fotos: [{ id: 7, imagen: 'http://localhost:8000/media/blog/fotos/7.png' }]
};

const imagen = (nombre = 'foto.png') => new File(['png'], nombre, { type: 'image/png' });

describe('GestorPublicaciones', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    configuracion.actual = { blog_activo: true };
    clienteAxios.get.mockResolvedValue({ data: [BORRADOR, PUBLICADA] });
    URL.createObjectURL = vi.fn(() => 'blob:vista-previa');
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('lista las publicaciones con su estado', async () => {
    render(<GestorPublicaciones />);

    const items = await screen.findAllByRole('listitem');
    expect(within(items[0]).getByText('Borrador')).toBeInTheDocument();
    expect(within(items[1]).getByText('Publicada')).toBeInTheDocument();
    expect(within(items[1]).getByText(/23 de octubre de 2026/)).toBeInTheDocument();
    expect(within(items[1]).getByText(/1 foto$/)).toBeInTheDocument();
    expect(screen.queryByText(/El blog está desactivado/)).not.toBeInTheDocument();
  });

  it('con el blog apagado avisa que los clientes no lo ven', async () => {
    configuracion.actual = { blog_activo: false };
    render(<GestorPublicaciones />);

    expect(await screen.findByText(/El blog está desactivado/)).toBeInTheDocument();
  });

  it('crea una publicación, la publica y después deja agregar fotos', async () => {
    clienteAxios.post.mockResolvedValueOnce({ data: { ...PUBLICADA, id: 3, titulo: 'Feria', portada: null, fotos: [] } });
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: '+ Nueva publicación' }));
    expect(screen.getByText(/Guarda la publicación .* para agregarle fotos/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Feria' } });
    fireEvent.change(screen.getByLabelText('Texto'), { target: { value: '<p>Fuimos a la feria.</p>' } });
    fireEvent.change(screen.getByLabelText('Elegir portada'), { target: { files: [imagen('portada.png')] } });
    expect(screen.getByRole('img', { name: 'Vista previa de la portada' })).toHaveAttribute('src', 'blob:vista-previa');
    fireEvent.click(screen.getByRole('button', { name: 'Publicar' }));

    expect(await screen.findByRole('status')).toHaveTextContent('"Feria" está publicada');
    const [url, datos] = clienteAxios.post.mock.calls[0];
    expect(url).toBe('ventas/admin/blog/');
    expect(datos.get('titulo')).toBe('Feria');
    expect(datos.get('contenido')).toBe('<p>Fuimos a la feria.</p>');
    expect(datos.get('estado')).toBe('PUBLICADA');
    expect(datos.get('portada').name).toBe('portada.png');
    expect(screen.getByRole('heading', { name: 'Editar publicación' })).toBeInTheDocument();
    expect(screen.getByLabelText('Agregar fotos')).toBeInTheDocument();
  });

  it('muestra junto al campo el error que devuelve el servidor', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 400, data: { titulo: ['Este dato es obligatorio.'] } } });
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: '+ Nueva publicación' }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Revisa los datos marcados.');
    const titulo = screen.getByLabelText('Título');
    expect(titulo).toHaveAttribute('aria-invalid', 'true');
    expect(titulo).toHaveAccessibleDescription('Este dato es obligatorio.');
  });

  it('permite ingresar un video de YouTube y lo envía al guardar (SCRUM-195)', async () => {
    clienteAxios.post.mockResolvedValueOnce({
      data: { ...PUBLICADA, id: 4, titulo: 'Video demo', youtube_id: 'dQw4w9WgXcQ' }
    });
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: '+ Nueva publicación' }));
    fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Video demo' } });
    fireEvent.change(screen.getByLabelText('Video de YouTube'), {
      target: { value: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' }
    });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));

    await waitFor(() => expect(clienteAxios.post).toHaveBeenCalled());
    const [, datos] = clienteAxios.post.mock.calls[0];
    expect(datos.get('youtube')).toBe('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  });

  it('una publicada se puede quitar la portada y pasar a borrador', async () => {
    clienteAxios.put.mockResolvedValue({ data: { ...PUBLICADA, portada: null, estado: 'BORRADOR' } });
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar "Nuestro taller"' }));
    expect(screen.getByRole('link', { name: /Ver en la tienda/ })).toHaveAttribute('href', '/blog/nuestro-taller');
    fireEvent.click(screen.getByRole('button', { name: 'Quitar portada' }));
    fireEvent.click(screen.getByRole('button', { name: 'Pasar a borrador' }));

    expect(await screen.findByRole('status')).toHaveTextContent('quedó como borrador');
    const [url, datos] = clienteAxios.put.mock.calls[0];
    expect(url).toBe('ventas/admin/blog/2/');
    expect(datos.get('quitar_portada')).toBe('true');
    expect(datos.get('estado')).toBe('BORRADOR');
    expect(datos.has('portada')).toBe(false);
  });

  it('sube fotos a la galería y respeta el máximo de 10', async () => {
    clienteAxios.post.mockResolvedValue({ data: { ...PUBLICADA, fotos: [...PUBLICADA.fotos, { id: 8, imagen: 'b.png' }] } });
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar "Nuestro taller"' }));
    fireEvent.change(screen.getByLabelText('Agregar fotos'),
      { target: { files: Array.from({ length: 10 }, (_, n) => imagen(`${n}.png`)) } });
    expect(screen.getByText('Puedes agregar 9 fotos más (máximo 10).')).toBeInTheDocument();
    expect(clienteAxios.post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Agregar fotos'), { target: { files: [imagen('b.png')] } });

    expect(await screen.findByRole('status')).toHaveTextContent('Foto agregada.');
    const [url, datos] = clienteAxios.post.mock.calls[0];
    expect(url).toBe('ventas/admin/blog/2/fotos/');
    expect(datos.getAll('fotos')).toHaveLength(1);
    expect(screen.getByRole('heading', { name: 'Galería (2 de 10)' })).toBeInTheDocument();
  });

  it('rechaza archivos que no son imágenes sin subirlos', async () => {
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar "Nuestro taller"' }));
    fireEvent.change(screen.getByLabelText('Agregar fotos'),
      { target: { files: [new File(['x'], 'doc.pdf', { type: 'application/pdf' })] } });

    expect(screen.getByText('Solo se permiten imágenes JPG, PNG o WebP.')).toBeInTheDocument();
    expect(clienteAxios.post).not.toHaveBeenCalled();
  });

  it('quita una foto después de confirmar', async () => {
    clienteAxios.delete.mockResolvedValue({ data: { ...PUBLICADA, fotos: [] } });
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar "Nuestro taller"' }));
    fireEvent.click(screen.getByRole('button', { name: 'Quitar foto 1' }));

    expect(await screen.findByRole('status')).toHaveTextContent('Foto quitada.');
    expect(clienteAxios.delete).toHaveBeenCalledWith('ventas/admin/blog/2/fotos/7/');
    expect(screen.getByRole('heading', { name: 'Galería (0 de 10)' })).toBeInTheDocument();
  });

  it('elimina una publicación después de confirmar', async () => {
    clienteAxios.delete.mockResolvedValue({});
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar "Idea a medias"' }));

    expect(await screen.findByRole('status')).toHaveTextContent('"Idea a medias" se eliminó.');
    expect(clienteAxios.delete).toHaveBeenCalledWith('ventas/admin/blog/1/');
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
  });

  it('no elimina si el admin cancela', async () => {
    window.confirm.mockReturnValue(false);
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Eliminar "Idea a medias"' }));

    expect(clienteAxios.delete).not.toHaveBeenCalled();
  });

  it('pide confirmar antes de volver con cambios sin guardar', async () => {
    window.confirm.mockReturnValue(false);
    render(<GestorPublicaciones />);

    fireEvent.click(await screen.findByRole('button', { name: 'Editar "Idea a medias"' }));
    fireEvent.click(screen.getByRole('button', { name: 'Volver a la lista' }));
    // Sin cambios vuelve directo
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Blog' })).toBeInTheDocument());
    expect(window.confirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Editar "Idea a medias"' }));
    fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Idea terminada' } });
    fireEvent.click(screen.getByRole('button', { name: 'Volver a la lista' }));

    expect(window.confirm).toHaveBeenCalledWith('Hay cambios sin guardar en esta publicación. ¿Descartarlos?');
    expect(screen.getByRole('heading', { name: 'Editar publicación' })).toBeInTheDocument();
  });
});
