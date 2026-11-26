import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
const { getMock, patchMock } = vi.hoisted(() => ({ getMock: vi.fn(), patchMock: vi.fn() }));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock, patch: patchMock } }));
vi.mock('../components/MenuUsuario', () => ({ default: () => null }));
vi.mock('../components/CarritoCompras', () => ({ default: () => null }));

// SCRUM-194: en el modo edición de la landing se pasa de una foto a otra y se editan sus textos y su botón
const FOTOS = [
  { id: 1, imagen: '/media/a.webp', orden: 0, antetitulo: 'Hecho a mano', titulo: 'Murales', texto: 'Para tu casa',
    destino: 'CATALOGO' },
  { id: 2, imagen: '/media/b.webp', orden: 1, antetitulo: '', titulo: 'Encargos', texto: '', destino: 'COTIZAR' },
];
const CONFIGURACION = {
  nombre_tienda: 'Taller', subtitulo_bienvenida: 'Hecho a mano', texto_bienvenida: 'Murales',
  texto_landing: 'Para tu casa', cotizaciones_activas: true, banners: FOTOS,
};

function responder(configuracion = CONFIGURACION) {
  getMock.mockImplementation((url) => Promise.resolve({
    data: url === 'configuracion/' ? configuracion : url === 'catalogo/vitrina/' ? { mas_vendidos: [], recientes: [] } : [],
  }));
}

async function editarLanding() {
  vi.resetModules();
  const { default: LandingPage } = await import('../pages/LandingPage');
  render(<MemoryRouter><LandingPage /></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button', { name: 'Editar página' }));
}

const posicion = () => document.querySelector('.portada-editor-posicion').textContent;
const ordenEnviado = () => JSON.parse(patchMock.mock.calls.at(-1)[1].banner_orden);

describe('Carrusel en el modo edición', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('rol', 'ADMIN');
    patchMock.mockResolvedValue({ data: {} });
    responder();
  });
  afterEach(cleanup);

  it('pasa de una foto a otra y muestra los textos y el botón de cada una', async () => {
    await editarLanding();
    expect(screen.getByLabelText('Título')).toHaveValue('Murales');
    expect(screen.getByLabelText('Antetítulo')).toHaveValue('Hecho a mano');
    expect(posicion()).toBe('Foto 1 de 2');
    expect(screen.getByRole('button', { name: '← Foto anterior' })).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Foto siguiente →' }));
    expect(screen.getByLabelText('Título')).toHaveValue('Encargos');
    expect(screen.getByLabelText('El botón lleva a')).toHaveValue('COTIZAR');
    expect(posicion()).toBe('Foto 2 de 2');
    // En el extremo, el foco pasa al botón que sigue activo
    await waitFor(() => expect(screen.getByRole('button', { name: '← Foto anterior' })).toHaveFocus());
  });

  it('la miniatura también elige qué foto se edita', async () => {
    await editarLanding();
    const segunda = screen.getByRole('button', { name: 'Editar textos de la foto 2' });
    fireEvent.click(segunda);
    expect(segunda).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Título')).toHaveValue('Encargos');
  });

  it('solo ofrece Blog y Cotizar con su módulo activo, con los nombres del menú', async () => {
    responder({ ...CONFIGURACION, cotizaciones_activas: false, menu_principal: { nombres: { catalogo: 'Productos' } } });
    await editarLanding();
    const opciones = () => within(screen.getByLabelText('El botón lleva a')).getAllByRole('option').map((o) => o.textContent);
    expect(opciones()).toEqual(['Inicio', 'Productos']);
    expect(screen.getByText('El botón dirá "Ver productos".')).toBeInTheDocument();

    // La foto que ya apuntaba a Cotizar lo conserva, avisando que no se muestra
    fireEvent.click(screen.getByRole('button', { name: 'Foto siguiente →' }));
    expect(opciones()).toEqual(['Inicio', 'Productos', 'Cotizar (apagado: no se muestra)']);
    expect(screen.getByText('Con ese módulo apagado, esta foto no muestra botón.')).toBeInTheDocument();
  });

  it('guarda los textos y el destino de cada foto, y los textos viajan con su foto al reordenar', async () => {
    await editarLanding();
    fireEvent.click(screen.getByRole('button', { name: 'Foto siguiente →' }));
    fireEvent.change(screen.getByLabelText('Título'), { target: { value: 'Cyber' } });
    fireEvent.change(screen.getByLabelText('El botón lleva a'), { target: { value: 'INICIO' } });
    fireEvent.click(screen.getByRole('button', { name: 'Mover foto 2 hacia la izquierda' }));
    // La foto movida sigue a la vista, ahora como la primera
    expect(posicion()).toBe('Foto 1 de 2');
    expect(screen.getByLabelText('Título')).toHaveValue('Cyber');

    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));
    await waitFor(() => expect(patchMock).toHaveBeenCalled());
    expect(ordenEnviado()).toEqual([
      { ref: 'id:2', antetitulo: '', titulo: 'Cyber', texto: '', destino: 'INICIO' },
      { ref: 'id:1', antetitulo: 'Hecho a mano', titulo: 'Murales', texto: 'Para tu casa', destino: 'CATALOGO' },
    ]);
  });

  it('no guarda si una foto queda sin título y muestra esa foto con el aviso', async () => {
    await editarLanding();
    fireEvent.click(screen.getByRole('button', { name: 'Foto siguiente →' }));
    fireEvent.change(screen.getByLabelText('Título'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: '← Foto anterior' }));
    fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }));

    expect(await screen.findByText('La foto 2 necesita un título.')).toBeInTheDocument();
    expect(posicion()).toBe('Foto 2 de 2');
    expect(screen.getByLabelText('Título')).toHaveAttribute('aria-invalid', 'true');
    expect(patchMock).not.toHaveBeenCalled();
  });

  it('sin fotos propias, el modo edición muestra los textos de la portada como antes', async () => {
    responder({ ...CONFIGURACION, banners: [] });
    await editarLanding();
    expect(screen.getByLabelText('Título')).toHaveValue('Murales');
    expect(screen.getByLabelText('Texto de la portada')).toHaveValue('Para tu casa');
    expect(screen.queryByLabelText('El botón lleva a')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Foto siguiente →' })).not.toBeInTheDocument();
  });

  it('muestra los campos de video solo cuando está activado', async () => {
    await editarLanding();

    const checkbox = screen.getByRole('checkbox', {
      name: 'Activar video en el banner',
    });

    // Inicialmente está desactivado.
    expect(checkbox).not.toBeChecked();
    expect(screen.queryByLabelText('Video MP4 del banner')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Imagen de portada del video')).not.toBeInTheDocument();

    // Al activarlo, aparecen los campos.
    fireEvent.click(checkbox);

    expect(checkbox).toBeChecked();
    expect(screen.getByLabelText('Video MP4 del banner')).toBeInTheDocument();
    expect(screen.getByLabelText('Imagen de portada del video')).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'Agregar video al carrusel',
    })).toBeDisabled();

    // Al desactivarlo, los campos desaparecen.
    fireEvent.click(checkbox);

    expect(checkbox).not.toBeChecked();
    expect(screen.queryByLabelText('Video MP4 del banner')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Imagen de portada del video')).not.toBeInTheDocument();

    // El checkbox sigue disponible.
    expect(checkbox).toBeInTheDocument();
  });

  it('no permite agregar un segundo video al carrusel', async () => {
    responder({
      ...CONFIGURACION,
      video_banner_activo: true,
      banners: [
        {
          ...FOTOS[0],
          video: '/media/banner.mp4',
        },
        FOTOS[1],
      ],
    });

    await editarLanding();

    const checkbox = screen.getByRole('checkbox', {
      name: 'Activar video en el banner',
    });

    expect(checkbox).toBeChecked();

    // Ya existe un video, por lo que no se ofrecen campos para otro.
    expect(screen.queryByLabelText('Video MP4 del banner')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Imagen de portada del video')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'Agregar video al carrusel',
    })).not.toBeInTheDocument();

    // El video existente sigue representado en el editor.
    expect(screen.getByText(/Video/)).toBeInTheDocument();
  });
});
