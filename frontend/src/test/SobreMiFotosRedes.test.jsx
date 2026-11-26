import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Pedido de un cliente: fotos en Sobre mí, ícono del correo en el pie y el usuario de las redes
const { getMock, patchMock, configuracion } = vi.hoisted(() => ({
  getMock: vi.fn(), patchMock: vi.fn(), configuracion: { actual: null }
}));

vi.mock('../components/auth/axiosConfig', () => ({ default: { get: getMock, patch: patchMock } }));
vi.mock('../hooks/useConfiguracionTienda', () => ({
  default: () => configuracion.actual,
  recargarConfiguracion: vi.fn(() => Promise.resolve())
}));
vi.mock('../components/header/header', () => ({ default: () => null }));
vi.mock('react-quill-new', () => ({
  default: ({ value, onChange }) => (
    <textarea aria-label="Editor de biografía" value={value} onChange={(e) => onChange(e.target.value)} />
  )
}));
vi.mock('../components/SelectorProyectosSobreMi', () => ({ default: () => null }));

import Footer from '../components/footer';
import SobreMi from '../pages/SobreMi';
import GestorSobreMi from '../components/GestorSobreMi';
import { usuarioDeRed } from '../utils/redesSociales';

const TIENDA = {
  nombre_tienda: 'Alan Zárate', correo_contacto: 'hola@example.test', telefono_comercial: '+56911112222',
  instagram_usuario: 'alan_kode', tiktok_url: 'https://www.tiktok.com/@alan_kode?lang=es',
  facebook_url: 'https://www.facebook.com/profile.php?id=123'
};

beforeEach(() => {
  vi.clearAllMocks();
  configuracion.actual = TIENDA;
});

afterEach(() => cleanup());

describe('usuarioDeRed', () => {
  it('saca el usuario del enlace cuando lo trae', () => {
    expect(usuarioDeRed('tiktok_url', 'https://www.tiktok.com/@alan_kode?lang=es')).toBe('@alan_kode');
    expect(usuarioDeRed('youtube_url', 'https://youtube.com/@CanalQA/videos')).toBe('@CanalQA');
    expect(usuarioDeRed('x_url', 'https://x.com/tienda_qa')).toBe('@tienda_qa');
  });

  it('sin usuario en el enlace devuelve null', () => {
    expect(usuarioDeRed('tiktok_url', 'https://vm.tiktok.com/ZMabc123/')).toBeNull();
    expect(usuarioDeRed('youtube_url', 'https://www.youtube.com/channel/UC123')).toBeNull();
    expect(usuarioDeRed('x_url', 'https://x.com/intent/follow')).toBeNull();
    expect(usuarioDeRed('facebook_url', 'https://facebook.com/tienda')).toBeNull();
    expect(usuarioDeRed('tiktok_url', 'no es un enlace')).toBeNull();
  });
});

describe('Pie de página', () => {
  beforeEach(() => getMock.mockResolvedValue({ data: [] }));

  it('el correo lleva su ícono y TikTok muestra el usuario', async () => {
    render(<MemoryRouter><Footer /></MemoryRouter>);

    const correo = await screen.findByRole('link', { name: 'hola@example.test' });
    expect(correo).toHaveAttribute('href', 'mailto:hola@example.test');
    expect(correo.querySelector('svg[aria-hidden="true"]')).not.toBeNull();

    const tiktok = screen.getByRole('link', { name: '@alan_kode en TikTok (se abre en una pestaña nueva)' });
    expect(tiktok).toHaveTextContent('@alan_kode');
    // Sin usuario en el enlace, el nombre de la red
    expect(screen.getByRole('link', { name: 'Facebook de Alan Zárate (se abre en una pestaña nueva)' }))
      .toHaveTextContent('Facebook');
  });
});

describe('Página Sobre mí', () => {
  it('muestra las fotos con su descripción y todas las redes en el contacto', async () => {
    getMock.mockResolvedValue({ data: {
      nombre: 'Sobre mí', biografia: '<p>Soy muralista.</p>', proyectos: [],
      contacto: { correo: 'hola@example.test', instagram: 'alan_kode' },
      fotos: [{ url: 'http://tienda.test/media/negocio/sobre_mi/a.jpg', alt: 'Pintando un mural' },
        { url: 'http://tienda.test/media/negocio/sobre_mi/b.jpg', alt: '' }]
    } });
    const { container } = render(<MemoryRouter><SobreMi /></MemoryRouter>);

    expect(await screen.findByRole('img', { name: 'Pintando un mural' })).toHaveAttribute('src', expect.stringContaining('a.jpg'));
    // Sin descripción, la foto es decorativa
    expect(container.querySelectorAll('.sobre-mi-foto img')).toHaveLength(2);
    const contacto = screen.getByRole('region', { name: 'Contacto' });
    expect(within(contacto).getByRole('link', { name: '@alan_kode' })).toHaveAttribute('href', 'https://www.instagram.com/alan_kode/');
    expect(within(contacto).getByText('TikTok:')).toBeInTheDocument();
    expect(within(contacto).getByRole('link', { name: '@alan_kode en TikTok (se abre en una pestaña nueva)' })).toHaveAttribute('href', TIENDA.tiktok_url);
    expect(within(contacto).getByRole('link', { name: 'Ver perfil en Facebook (se abre en una pestaña nueva)' })).toHaveAttribute('href', TIENDA.facebook_url);
  });

  it('sin fotos se ve como antes', async () => {
    getMock.mockResolvedValue({ data: { nombre: 'Sobre mí', biografia: '<p>Hola</p>', proyectos: [], contacto: {}, fotos: [] } });
    const { container } = render(<MemoryRouter><SobreMi /></MemoryRouter>);

    expect(await screen.findByText('Hola')).toBeInTheDocument();
    expect(container.querySelector('.sobre-mi-biografia--con-fotos')).toBeNull();
  });
});

describe('Fotos en el panel de Sobre mí', () => {
  const CONFIG = {
    sobre_mi_activo: true, sobre_mi_nombre: 'Sobre mí', sobre_mi_biografia: '<p>Hola</p>',
    sobre_mi_foto_1: 'http://tienda.test/media/negocio/sobre_mi/vieja.jpg', sobre_mi_foto_1_alt: 'Foto vieja',
    sobre_mi_foto_2: null, sobre_mi_foto_2_alt: ''
  };

  beforeEach(() => {
    getMock.mockResolvedValue({ data: CONFIG });
    patchMock.mockImplementation((_, datos) => Promise.resolve({ data: datos instanceof FormData ? CONFIG : { ...CONFIG, ...datos } }));
    URL.createObjectURL = vi.fn(() => 'blob:vista-previa');
    URL.revokeObjectURL = vi.fn();
  });

  it('sube una foto nueva con su descripción y quita la guardada', async () => {
    render(<GestorSobreMi />);

    fireEvent.click(await screen.findByRole('button', { name: 'Quitar la foto 1' }));
    const archivo = new File(['foto'], 'taller.png', { type: 'image/png' });
    fireEvent.change(screen.getByLabelText(/Foto 2/), { target: { files: [archivo] } });
    expect(screen.getByRole('img', { name: 'Vista previa de la foto 2' })).toHaveAttribute('src', 'blob:vista-previa');
    fireEvent.change(screen.getByLabelText('Descripción de la foto 2'), { target: { value: 'En el taller' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar Sobre mí' }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(2));
    expect(patchMock.mock.calls[0][1]).toMatchObject({ sobre_mi_foto_1: null, sobre_mi_foto_1_alt: '', sobre_mi_foto_2_alt: 'En el taller' });
    const subida = patchMock.mock.calls[1][1];
    expect(subida).toBeInstanceOf(FormData);
    expect(subida.get('sobre_mi_foto_2')).toBe(archivo);
    expect(patchMock.mock.calls[1][2]).toEqual({ headers: { 'Content-Type': undefined } });
    expect(await screen.findByRole('status')).toHaveTextContent('está activada');
  });

  it('rechaza un archivo que no es imagen', async () => {
    render(<GestorSobreMi />);

    fireEvent.change(await screen.findByLabelText(/Foto 2/), { target: { files: [new File(['x'], 'a.pdf', { type: 'application/pdf' })] } });

    expect(screen.getByText('Solo se permiten imágenes JPG, PNG o WebP.')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: 'Vista previa de la foto 2' })).not.toBeInTheDocument();
  });
});
