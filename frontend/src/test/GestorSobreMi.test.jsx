
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({
  default: { get: vi.fn(), patch: vi.fn() }
}));

vi.mock('../hooks/useConfiguracionTienda', () => ({
  recargarConfiguracion: vi.fn()
}));

vi.mock('react-quill-new', () => ({
  default: ({ value, onChange, placeholder }) => (
    <textarea
      aria-label="Editor de biografía"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  )
}));

vi.mock('../components/SelectorProyectosSobreMi', () => ({
  default: () => <div>Selector de proyectos simulado</div>
}));

import clienteAxios from '../components/auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import GestorSobreMi from '../components/GestorSobreMi';

const CONFIGURACION = {
  sobre_mi_activo: false,
  sobre_mi_nombre: 'Sobre mí',
  sobre_mi_biografia: '<p>Mi emprendimiento</p>'
};

describe('GestorSobreMi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: { ...CONFIGURACION } });
    recargarConfiguracion.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('carga la configuración guardada', async () => {
    render(<GestorSobreMi />);

    expect(
      await screen.findByRole('checkbox', {
        name: 'Mostrar la página Sobre mí en mi tienda'
      })
    ).not.toBeChecked();

    expect(screen.getByLabelText('Nombre de la página'))
      .toHaveValue('Sobre mí');

    expect(screen.getByLabelText('Editor de biografía'))
      .toHaveValue('<p>Mi emprendimiento</p>');

    expect(clienteAxios.get)
      .toHaveBeenCalledWith('configuracion/negocio/');
  });

  it('permite activar la página y guardar nombre y biografía', async () => {
    clienteAxios.patch.mockImplementation((_, datos) =>
      Promise.resolve({ data: { ...datos } })
    );

    render(<GestorSobreMi />);

    fireEvent.click(
      await screen.findByRole('checkbox', {
        name: 'Mostrar la página Sobre mí en mi tienda'
      })
    );

    fireEvent.change(screen.getByLabelText('Nombre de la página'), {
      target: { value: 'Mi historia' }
    });

    fireEvent.change(screen.getByLabelText('Editor de biografía'), {
      target: { value: '<h2>Nuestra historia</h2>' }
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar Sobre mí' })
    );

    await waitFor(() => {
      expect(clienteAxios.patch).toHaveBeenCalledWith(
        'configuracion/negocio/',
        {
          sobre_mi_activo: true,
          sobre_mi_nombre: 'Mi historia',
          sobre_mi_biografia: '<h2>Nuestra historia</h2>'
        }
      );
    });

    expect(await screen.findByRole('status'))
      .toHaveTextContent('La página Sobre mí está activada');

    expect(recargarConfiguracion).toHaveBeenCalledOnce();
  });

  it('permite desactivar la página', async () => {
    clienteAxios.get.mockResolvedValue({
      data: { ...CONFIGURACION, sobre_mi_activo: true }
    });

    clienteAxios.patch.mockImplementation((_, datos) =>
      Promise.resolve({ data: { ...datos } })
    );

    render(<GestorSobreMi />);

    fireEvent.click(
      await screen.findByRole('checkbox', {
        name: 'Mostrar la página Sobre mí en mi tienda'
      })
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar Sobre mí' })
    );

    expect(await screen.findByRole('status'))
      .toHaveTextContent('La página Sobre mí está desactivada.');

    expect(clienteAxios.patch).toHaveBeenCalledWith(
      'configuracion/negocio/',
      expect.objectContaining({ sobre_mi_activo: false })
    );
  });

  it('muestra los errores de validación del servidor', async () => {
    clienteAxios.patch.mockRejectedValue({
      response: {
        data: {
          sobre_mi_nombre: ['El nombre puede tener hasta 30 caracteres.']
        }
      }
    });

    render(<GestorSobreMi />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Guardar Sobre mí' })
    );

    expect(await screen.findByRole('alert'))
      .toHaveTextContent('Revisa los datos marcados.');

    expect(recargarConfiguracion).not.toHaveBeenCalled();
  });

  it('informa cuando falla la carga inicial', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    clienteAxios.get.mockRejectedValue(new Error('Sin conexión'));

    render(<GestorSobreMi />);

    expect(await screen.findByRole('alert'))
      .toHaveTextContent(
        'No se pudo cargar la configuración de Sobre mí.'
      );
  });
});
