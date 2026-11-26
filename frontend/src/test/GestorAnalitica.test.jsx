
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import GestorAnalitica from '../components/GestorAnalitica';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn(),
  },
}));

describe('GestorAnalitica', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    clienteAxios.get.mockResolvedValue({
      data: {
        google_analytics_id: 'G-ABC1234567',
        meta_pixel_id: '123456789012345',
      },
    });

    clienteAxios.patch.mockResolvedValue({
      data: {
        google_analytics_id: 'G-ABC1234567',
        meta_pixel_id: '123456789012345',
      },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('carga los IDs guardados en los campos del formulario', async () => {
    render(<GestorAnalitica />);

    expect(
      await screen.findByLabelText('ID de Google Analytics')
    ).toHaveValue('G-ABC1234567');

    expect(
      screen.getByLabelText('ID de Meta Pixel')
    ).toHaveValue('123456789012345');

    expect(clienteAxios.get).toHaveBeenCalledWith(
      'configuracion/negocio/'
    );
  });

  it('guarda los IDs y muestra un mensaje de éxito', async () => {
    render(<GestorAnalitica />);

    const googleInput = await screen.findByLabelText(
      'ID de Google Analytics'
    );
    const metaInput = screen.getByLabelText('ID de Meta Pixel');

    fireEvent.change(googleInput, {
      target: { value: ' G-XYZ1234567 ' },
    });
    fireEvent.change(metaInput, {
      target: { value: ' 987654321 ' },
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar configuración' })
    );

    await waitFor(() => {
      expect(clienteAxios.patch).toHaveBeenCalledWith(
        'configuracion/negocio/',
        {
          google_analytics_id: 'G-XYZ1234567',
          meta_pixel_id: '987654321',
        }
      );
    });

    expect(
      await screen.findByText(
        'La configuración de analítica se guardó correctamente.'
      )
    ).toBeInTheDocument();
  });

  it('muestra los errores de validación que devuelve el backend', async () => {
    clienteAxios.patch.mockRejectedValue({
      response: {
        data: {
          google_analytics_id: [
            'Ingresa un ID de Google Analytics válido.',
          ],
          meta_pixel_id: [
            'El ID de Meta Pixel debe contener solo números.',
          ],
        },
      },
    });

    render(<GestorAnalitica />);

    await screen.findByLabelText('ID de Google Analytics');

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar configuración' })
    );

    expect(
      await screen.findByText(
        'Ingresa un ID de Google Analytics válido.'
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'El ID de Meta Pixel debe contener solo números.'
      )
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        'No se pudo guardar la configuración. Revisa los campos marcados.'
      )
    ).toBeInTheDocument();
  });

  it('muestra un aviso si falla la carga de la configuración', async () => {
    const error = new Error('Error de conexión');
    clienteAxios.get.mockRejectedValue(error);
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});

    render(<GestorAnalitica />);

    expect(
      await screen.findByText(
        'No se pudo cargar la configuración de analítica.'
      )
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText('ID de Google Analytics')
    ).toBeInTheDocument();

    consoleError.mockRestore();
  });

  it('muestra un aviso si falla el guardado por un error del servidor', async () => {
    clienteAxios.patch.mockRejectedValue({
      response: {
        data: {
          detail: 'Error interno del servidor.',
        },
      },
    });

    render(<GestorAnalitica />);

    await screen.findByLabelText('ID de Google Analytics');

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar configuración' })
    );

    expect(
      await screen.findByText('Error interno del servidor.')
    ).toBeInTheDocument();
  });
});
