import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Portada from '../components/landing/Portada';

const configuracion = (activo = true) => ({
  nombre_tienda: 'Tienda', video_banner_activo: activo,
  banners: [
    { id: 1, imagen: '/portada.jpg', video: '/presentacion.mp4', titulo: 'Video', destino: 'CATALOGO' },
    { id: 2, imagen: '/foto.jpg', titulo: 'Foto', destino: 'CATALOGO' },
  ],
});

const mostrar = (activo) => render(<MemoryRouter><Portada configuracion={configuracion(activo)} /></MemoryRouter>);

const simularVideo = () => { const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockImplementation(() => Promise.resolve());
  const pause = vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
  return { play, pause };
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('Video opcional de la portada', () => {
  it('no descarga ni crea el elemento de video cuando está desactivado', () => {
    const { container } = mostrar(false);
    expect(container.querySelector('video')).toBeNull();
  });

  it('incluye video silenciado y sin controles cuando está activo; con más diapositivas no va en bucle', () => {
    const { container } = mostrar(true);
    const video = container.querySelector('video');
    expect(video).not.toBeNull();
    expect(video.muted).toBe(true);
    expect(video.loop).toBe(false);
    expect(video.controls).toBe(false);
  });

  it('si el video es la única diapositiva, se repite en bucle', () => {
    const [soloVideo] = configuracion(true).banners;
    const { container } = render(<MemoryRouter>
      <Portada configuracion={{ ...configuracion(true), banners: [soloVideo] }} />
    </MemoryRouter>);
    expect(container.querySelector('video').loop).toBe(true);
  });

  describe('el carrusel espera a que termine el video', () => {
    beforeEach(() => { vi.useFakeTimers(); });
    afterEach(() => { vi.useRealTimers(); });

    const titulo = () => screen.getByRole('heading', { level: 1 }).textContent;
    const pasar = (ms) => act(() => { vi.advanceTimersByTime(ms); });

    it('no cambia de diapositiva a los 5 segundos y pasa a la siguiente cuando el video termina', () => {
      simularVideo();
      const { container } = mostrar(true);
      expect(titulo()).toBe('Video');
      pasar(20000);
      expect(titulo()).toBe('Video');

      fireEvent.ended(container.querySelector('video'));
      expect(titulo()).toBe('Foto');
      // En la foto vuelve el reloj de 5 segundos
      pasar(5000);
      expect(titulo()).toBe('Video');
    });

    it('si el video termina con el mouse sobre los textos, vuelve a empezar y no cambia (WCAG 2.2.2)', () => {
      const { play } = simularVideo();
      const { container } = mostrar(true);
      fireEvent.mouseEnter(screen.getByRole('heading', { level: 1 }).parentElement);
      const video = container.querySelector('video');
      play.mockClear();

      fireEvent.ended(video);
      expect(titulo()).toBe('Video');
      expect(play.mock.contexts).toContain(video);
    });

    it('si el video no se puede reproducir, el carrusel vuelve a cambiar cada 5 segundos', () => {
      simularVideo();
      const { container } = mostrar(true);
      fireEvent.error(container.querySelector('video'));
      pasar(5000);
      expect(titulo()).toBe('Foto');
    });
  });

  it('el botón de pausa alterna entre pausar y reanudar el carrusel', () => {
    mostrar(true);
    fireEvent.click(screen.getByRole('button', { name: 'Pausar carrusel' }));
    expect(screen.getByRole('button', { name: 'Reanudar carrusel' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Reanudar carrusel' }));
    expect(screen.getByRole('button', { name: 'Pausar carrusel' })).toBeTruthy();
  });

  it('respeta la preferencia de movimiento reducido', () => {
    const { play } = simularVideo();

    vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));

    const { container } = mostrar(true);

    expect(container.querySelector('video')).toBeNull();
    expect(play).not.toHaveBeenCalled();
  });

  it('no carga ni reproduce videos cuando está activado el ahorro de datos', () => {
    const { play } = simularVideo();

    vi.stubGlobal('navigator', Object.create(navigator, {
      connection: {
        value: { saveData: true },
        configurable: true,
      },
    }));

    const { container } = mostrar(true);

    expect(container.querySelector('video')).toBeNull();
    expect(play).not.toHaveBeenCalled();
  });

  it('ejecuta video.pause() al pausar el carrusel', () => {
    const { play, pause } = simularVideo();

    const { container } = mostrar(true);

    const video = container.querySelector('video');
    expect(video).not.toBeNull();
    expect(play).toHaveBeenCalled();

    pause.mockClear();

    fireEvent.click(
      screen.getByRole('button', { name: 'Pausar carrusel' })
    );

    expect(pause).toHaveBeenCalled();
    expect(
      screen.getByRole('button', { name: 'Reanudar carrusel' })
    ).toBeInTheDocument();
  });

  // Al llegar al video con una flecha, el foco queda en ella: eso frena el cambio de diapositiva, no el video
  it('el video parte solo aunque el foco quede en la flecha con la que se llegó a él', () => {
    const { play, pause } = simularVideo();
    const [video, foto] = configuracion(true).banners;
    const { container } = render(<MemoryRouter>
      <Portada configuracion={{ ...configuracion(true), banners: [foto, video] }} />
    </MemoryRouter>);

    const siguiente = screen.getByRole('button', { name: 'Foto siguiente' });
    act(() => { siguiente.focus(); });
    play.mockClear();
    pause.mockClear();
    fireEvent.click(siguiente);

    const elemento = container.querySelector('video');
    expect(siguiente).toHaveFocus();
    expect(play.mock.contexts).toContain(elemento);
    expect(pause.mock.contexts).not.toContain(elemento);
  });
});

// Con el video en pantalla, el velo se aclara hacia la derecha (landing.css, desde 1024 px)
describe('Velo más claro mientras se ve el video', () => {
  const portada = (container) => container.querySelector('section.portada');

  it('marca la portada mientras la diapositiva activa muestra el video', () => {
    simularVideo();
    const { container } = mostrar(true);
    expect(portada(container)).toHaveClass('portada--con-video');
  });

  it('no la marca con el video desactivado', () => {
    const { container } = mostrar(false);
    expect(portada(container)).not.toHaveClass('portada--con-video');
  });

  it('vuelve al velo completo al pasar a una foto', () => {
    simularVideo();
    const { container } = mostrar(true);
    fireEvent.ended(container.querySelector('video'));
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Foto');
    expect(portada(container)).not.toHaveClass('portada--con-video');
  });

  it('vuelve al velo completo si el video no se puede reproducir', () => {
    simularVideo();
    const { container } = mostrar(true);
    fireEvent.error(container.querySelector('video'));
    expect(portada(container)).not.toHaveClass('portada--con-video');
  });

  it('no la marca si el visitante pidió reducir el movimiento', () => {
    vi.stubGlobal('matchMedia', (consulta) => ({ matches: consulta.includes('reduced-motion'),
      addEventListener: () => {}, removeEventListener: () => {} }));
    const { container } = mostrar(true);
    expect(portada(container)).not.toHaveClass('portada--con-video');
  });
});
