import { fireEvent, render, screen, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import CookieBanner from '../components/CookieBanner';

function renderBanner(props = {}, initialPath = '/') {
  const defaultProps = {
    consent: 'pending',
    isOpen: true,
    storageError: '',
    onAccept: vi.fn(),
    onReject: vi.fn(),
    onSave: vi.fn(),
    onClose: vi.fn(),
  };

  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <CookieBanner {...defaultProps} {...props} />
    </MemoryRouter>,
  );
}

describe('CookieBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('muestra el banner cuando está abierto y no es una ruta administrativa', () => {
    renderBanner();

    expect(
      screen.getByRole('region', { name: 'Tus preferencias de cookies' }),
    ).toBeInTheDocument();

    expect(screen.getByText(/análisis \(Google Analytics\) y de publicidad \(Meta Pixel\)/)).toBeInTheDocument();
    expect(screen.getByText(/Te volveremos a preguntar en 12 meses/)).toBeInTheDocument();
  });

  it('Configurar muestra cada categoría desmarcada y guarda solo lo elegido', () => {
    const onSave = vi.fn();
    renderBanner({ onSave });

    fireEvent.click(screen.getByRole('button', { name: 'Configurar' }));
    const analisis = screen.getByRole('checkbox', { name: /Análisis/ });
    const publicidad = screen.getByRole('checkbox', { name: /Publicidad/ });
    expect(analisis).not.toBeChecked();
    expect(publicidad).not.toBeChecked();

    fireEvent.click(analisis);
    fireEvent.click(screen.getByRole('button', { name: 'Guardar mis preferencias' }));

    expect(onSave).toHaveBeenCalledWith({ analitica: true, marketing: false });
  });

  it('Configurar parte de la elección vigente', () => {
    renderBanner({ consent: 'custom', preferences: { analitica: false, marketing: true } });

    fireEvent.click(screen.getByRole('button', { name: 'Configurar' }));

    expect(screen.getByRole('checkbox', { name: /Análisis/ })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: /Publicidad/ })).toBeChecked();
  });

  it('no muestra el banner cuando isOpen es false', () => {
    renderBanner({ isOpen: false });

    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });

  it.each(['/admin', '/admin/', '/admin/productos', '/ADMIN'])(
    'no muestra el banner en la ruta administrativa %s',
    (path) => {
      renderBanner({}, path);

      expect(screen.queryByRole('region')).not.toBeInTheDocument();
    },
  );

  it('muestra el enlace a la política de privacidad', () => {
    renderBanner();

    const link = screen.getByRole('link', {
      name: 'Política de Privacidad',
    });

    expect(link).toHaveAttribute('href', '/legal/privacidad');
  });

  it('llama a onAccept al pulsar Aceptar', () => {
    const onAccept = vi.fn();

    renderBanner({ onAccept });

    fireEvent.click(screen.getByRole('button', { name: 'Aceptar' }));

    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  it('llama a onReject al pulsar Rechazar', () => {
    const onReject = vi.fn();

    renderBanner({ onReject });

    fireEvent.click(screen.getByRole('button', { name: 'Rechazar' }));

    expect(onReject).toHaveBeenCalledTimes(1);
  });

  it('no muestra Cerrar preferencias cuando el consentimiento está pendiente', () => {
    renderBanner({ consent: 'pending' });

    expect(
      screen.queryByRole('button', { name: 'Cerrar preferencias' }),
    ).not.toBeInTheDocument();
  });

  it('muestra Cerrar preferencias cuando ya existe una decisión', () => {
    renderBanner({ consent: 'rejected' });

    expect(
      screen.getByRole('button', { name: 'Cerrar preferencias' }),
    ).toBeInTheDocument();
  });

  it('llama a onClose al pulsar Cerrar preferencias', () => {
    const onClose = vi.fn();

    renderBanner({ consent: 'accepted', onClose });

    fireEvent.click(
      screen.getByRole('button', { name: 'Cerrar preferencias' }),
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('muestra el aviso de recarga cuando el consentimiento está aceptado', () => {
    renderBanner({ consent: 'accepted', preferences: { analitica: true, marketing: true } });

    expect(
      screen.getByText(/esta página se recargará y se reiniciarán los formularios abiertos/i),
    ).toBeInTheDocument();
  });

  it('no muestra el aviso de recarga cuando el consentimiento está rechazado', () => {
    renderBanner({ consent: 'rejected' });

    expect(
      screen.queryByText(/esta página se recargará/i),
    ).not.toBeInTheDocument();
  });

  it('muestra el error de almacenamiento con role alert', () => {
    renderBanner({
      storageError: 'No pudimos guardar tu elección.',
    });

    expect(screen.getByRole('alert')).toHaveTextContent(
      'No pudimos guardar tu elección.',
    );
  });

  it('no muestra el mensaje de error cuando storageError está vacío', () => {
    renderBanner({ storageError: '' });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('cierra las preferencias con Escape cuando la decisión ya no está pendiente', () => {
    const onClose = vi.fn();

    renderBanner({ consent: 'rejected', onClose });

    const banner = screen.getByRole('region', {
      name: 'Tus preferencias de cookies',
    });

    fireEvent.keyDown(banner, { key: 'Escape' });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('no cierra las preferencias con Escape si el consentimiento está pendiente', () => {
    const onClose = vi.fn();

    renderBanner({ consent: 'pending', onClose });

    const banner = screen.getByRole('region', {
      name: 'Tus preferencias de cookies',
    });

    fireEvent.keyDown(banner, { key: 'Escape' });

    expect(onClose).not.toHaveBeenCalled();
  });

  it('no cierra las preferencias con otras teclas', () => {
    const onClose = vi.fn();

    renderBanner({ consent: 'rejected', onClose });

    const banner = screen.getByRole('region', {
      name: 'Tus preferencias de cookies',
    });

    fireEvent.keyDown(banner, { key: 'Enter' });

    expect(onClose).not.toHaveBeenCalled();
  });

  it('enfoca el banner cuando se vuelve visible', () => {
    renderBanner();

    expect(
      screen.getByRole('region', { name: 'Tus preferencias de cookies' }),
    ).toHaveFocus();
  });

  it('no renderiza contenido del banner en rutas administrativas aunque haya error', () => {
    renderBanner(
      {
        storageError: 'Error de almacenamiento',
      },
      '/admin/configuracion',
    );

    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
