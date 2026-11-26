import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import GestorContacto from '../components/GestorContacto';
import clienteAxios from '../components/auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
    patch: vi.fn()
  }
}));

vi.mock('../hooks/useConfiguracionTienda', () => ({
  recargarConfiguracion: vi.fn()
}));

vi.mock('../components/carga/Esqueleto', () => ({
  Cargando: ({ texto, children }) => (
    <div data-testid="cargando">
      <span>{texto}</span>
      {children}
    </div>
  )
}));

vi.mock('../components/carga/EsqueletosPanel', () => ({
  EsqueletoFormulario: ({ campos }) => (
    <div data-testid="esqueleto-formulario">
      Campos: {campos}
    </div>
  )
}));

vi.mock('../components/carga/Spinner', () => ({
  default: () => <span data-testid="spinner" />
}));

const datosIniciales = {
  correo_contacto: 'contacto@mitienda.cl',
  horario_atencion: 'Lunes a viernes, 10:00 a 19:00',
  instagram_usuario: 'mitienda',
  telefono_comercial: "",
  facebook_url: "",
  x_url: "",
  youtube_url: "",
  tiktok_url: "",
  mostrar_direccion_pie: true
};

const renderizar = async (datos = datosIniciales) => {
  clienteAxios.get.mockResolvedValueOnce({ data: datos });

  const resultado = render(<GestorContacto />);

  await waitFor(() => {
    expect(screen.queryByTestId('cargando')).not.toBeInTheDocument();
  });

  return resultado;
};

afterEach(() => {
  cleanup();
});

describe('GestorContacto', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('debe mostrar el esqueleto mientras carga los datos', () => {
    clienteAxios.get.mockReturnValue(new Promise(() => {}));

    render(<GestorContacto />);

    expect(screen.getByTestId('cargando')).toBeInTheDocument();
    expect(screen.getByText('Cargando datos de contacto...')).toBeInTheDocument();
    expect(screen.getByTestId('esqueleto-formulario')).toBeInTheDocument();
  });

  it('debe solicitar la configuración del negocio', async () => {
    await renderizar();

    expect(clienteAxios.get).toHaveBeenCalledWith('configuracion/negocio/');
  });

  it('debe mostrar los datos de contacto recibidos del servidor', async () => {
    await renderizar();

    expect(screen.getByLabelText('Correo de contacto')).toHaveValue(
      'contacto@mitienda.cl'
    );

    expect(screen.getByLabelText('Horario de atención')).toHaveValue(
      'Lunes a viernes, 10:00 a 19:00'
    );

    expect(screen.getByLabelText('Instagram')).toHaveValue('mitienda');
  });

  it('debe inicializar los campos vacíos cuando el servidor no devuelve datos', async () => {
    await renderizar({});

    expect(screen.getByLabelText('Correo de contacto')).toHaveValue('');
    expect(screen.getByLabelText('Horario de atención')).toHaveValue('');
    expect(screen.getByLabelText('Instagram')).toHaveValue('');
    expect(
      screen.getByRole('checkbox', {
        name: /mostrar la dirección del local/i
      })
    ).not.toBeChecked();
  });

  it('debe reflejar el estado de mostrar_direccion_pie', async () => {
    await renderizar();

    expect(
      screen.getByRole('checkbox', {
        name: /mostrar la dirección del local/i
      })
    ).toBeChecked();
  });

  it('debe permitir modificar los campos del formulario', async () => {
    await renderizar();

    fireEvent.change(screen.getByLabelText('Correo de contacto'), {
      target: { value: 'nuevo@mitienda.cl' }
    });

    fireEvent.change(screen.getByLabelText('Horario de atención'), {
      target: { value: 'Lunes a sábado' }
    });

    fireEvent.change(screen.getByLabelText('Instagram'), {
      target: { value: '@nuevatienda' }
    });

    expect(screen.getByLabelText('Correo de contacto')).toHaveValue(
      'nuevo@mitienda.cl'
    );

    expect(screen.getByLabelText('Horario de atención')).toHaveValue(
      'Lunes a sábado'
    );

    expect(screen.getByLabelText('Instagram')).toHaveValue('@nuevatienda');
  });

  it('debe enviar los datos mediante PATCH al guardar', async () => {
    await renderizar();

    clienteAxios.patch.mockResolvedValueOnce({
      data: datosIniciales
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    await waitFor(() => {
      expect(clienteAxios.patch).toHaveBeenCalledWith(
        'configuracion/negocio/',
        datosIniciales
      );
    });
  });

  it('debe actualizar los campos con la respuesta normalizada del servidor', async () => {
    await renderizar();

    clienteAxios.patch.mockResolvedValueOnce({
      data: {
        ...datosIniciales,
        instagram_usuario: 'mitienda'
      }
    });

    fireEvent.change(screen.getByLabelText('Instagram'), {
      target: { value: '@MiTienda' }
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Instagram')).toHaveValue('mitienda');
    });
  });

  it('debe recargar la configuración de la tienda después de guardar', async () => {
    await renderizar();

    clienteAxios.patch.mockResolvedValueOnce({
      data: datosIniciales
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    await waitFor(() => {
      expect(recargarConfiguracion).toHaveBeenCalledTimes(1);
    });
  });

  it('debe mostrar el mensaje de éxito después de guardar', async () => {
    await renderizar();

    clienteAxios.patch.mockResolvedValueOnce({
      data: datosIniciales
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    expect(
      await screen.findByRole('status')
    ).toHaveTextContent(
      'Datos de contacto guardados: ya se ven en tu tienda.'
    );
  });

  it('debe mostrar un error cuando falla la carga de los datos', async () => {
    const error = new Error('Error de conexión');

    vi.spyOn(console, 'error').mockImplementation(() => {});

    clienteAxios.get.mockRejectedValueOnce(error);

    render(<GestorContacto />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudieron cargar los datos de contacto.'
    );
  });

  it('debe mostrar un mensaje general cuando falla el guardado', async () => {
    await renderizar();

    clienteAxios.patch.mockRejectedValueOnce({
      response: {
        data: {
          general: ['Error del servidor']
        }
      }
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Revisa los datos marcados.'
    );
  });

  it('debe mostrar los errores del backend junto a sus respectivos campos', async () => {
    await renderizar();

    clienteAxios.patch.mockRejectedValueOnce({
      response: {
        data: {
          correo_contacto: ['Correo inválido'],
          instagram_usuario: ['Usuario no válido']
        }
      }
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    expect(await screen.findByText('Correo inválido')).toBeInTheDocument();
    expect(screen.getByText('Usuario no válido')).toBeInTheDocument();

    expect(screen.getByLabelText('Correo de contacto')).toHaveAttribute(
      'aria-invalid',
      'true'
    );

    expect(screen.getByLabelText('Instagram')).toHaveAttribute(
      'aria-invalid',
      'true'
    );
  });

  it('debe limpiar el error de un campo cuando se modifica', async () => {
    await renderizar();

    clienteAxios.patch.mockRejectedValueOnce({
      response: {
        data: {
          correo_contacto: ['Correo inválido']
        }
      }
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    expect(await screen.findByText('Correo inválido')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Correo de contacto'), {
      target: { value: 'nuevo@mitienda.cl' }
    });

    expect(screen.queryByText('Correo inválido')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Correo de contacto')).not.toHaveAttribute(
      'aria-invalid'
    );
  });

  it('debe deshabilitar el botón mientras se guardan los datos', async () => {
    await renderizar();

    let resolver;

    clienteAxios.patch.mockReturnValueOnce(
      new Promise((resolve) => {
        resolver = resolve;
      })
    );

    fireEvent.click(
      screen.getByRole('button', {
        name: /guardar contacto y redes/i
      })
    );

    expect(
      screen.getByRole('button', {
        name: /guardando/i
      })
    ).toBeDisabled();

    resolver({ data: datosIniciales });

    await waitFor(() => {
      expect(
        screen.getByRole('button', {
          name: /guardar contacto y redes/i
        })
      ).toBeEnabled();
    });
  });

  it('debe permitir volver a guardar después de un error', async () => {
    await renderizar();

    clienteAxios.patch
      .mockRejectedValueOnce(new Error('Error de conexión'))
      .mockResolvedValueOnce({ data: datosIniciales });

    const boton = screen.getByRole('button', {
      name: /guardar contacto y redes/i
    });

    fireEvent.click(boton);

    expect(await screen.findByRole('alert')).toBeInTheDocument();

    fireEvent.click(boton);

    await waitFor(() => {
      expect(clienteAxios.patch).toHaveBeenCalledTimes(2);
    });

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Datos de contacto guardados'
    );
  });
});
