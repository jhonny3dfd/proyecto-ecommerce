import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import GestorMediosPago from '../components/GestorMediosPago';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

const mediosMock = [
  {
    codigo: 'TRANSFERENCIA',
    nombre: 'Transferencia bancaria',
    integracion_lista: true,
    disponible: true,
    habilitado: true,
    faltantes: [],
    campos: [
      {
        nombre: 'banco',
        etiqueta: 'Banco',
        obligatorio: true,
        obligatorio_si: null,
        opciones: ['Banco Estado', 'Banco de Chile'],
        formato: '',
        secreto: false,
      },
      {
        nombre: 'cuenta',
        etiqueta: 'Número de cuenta',
        obligatorio: true,
        obligatorio_si: null,
        opciones: [],
        formato: 'numero_cuenta',
        secreto: false,
      },
      {
        nombre: 'api_key',
        etiqueta: 'API Key',
        obligatorio: true,
        obligatorio_si: ['entorno', 'PRODUCCION'],
        opciones: [],
        formato: '',
        secreto: true,
      },
      {
        nombre: 'entorno',
        etiqueta: 'Entorno',
        obligatorio: true,
        obligatorio_si: null,
        opciones: ['INTEGRACION', 'PRODUCCION'],
        formato: '',
        secreto: false,
      },
    ],
    datos: {
      banco: 'Banco Estado',
      cuenta: '123456789',
      api_key: '********abcd',
      entorno: 'INTEGRACION',
    },
  },
];

const renderComponente = () => render(<GestorMediosPago />);

describe('GestorMediosPago', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: mediosMock });
  });

  it('muestra el estado de carga inicialmente', () => {
    clienteAxios.get.mockReturnValue(new Promise(() => {}));

    renderComponente();

    expect(screen.getByText('Cargando medios de pago...')).toBeInTheDocument();
  });

  it('carga y muestra los medios de pago existentes', async () => {
    renderComponente();

    expect(
      await screen.findByText('Transferencia bancaria')
    ).toBeInTheDocument();

    expect(clienteAxios.get).toHaveBeenCalledWith(
      'ventas/admin/medios-pago/'
    );
  });

  it('muestra un error cuando falla la carga de los medios de pago', async () => {
    clienteAxios.get.mockRejectedValue(new Error('Error de conexión'));

    renderComponente();

    expect(
      await screen.findByRole('alert')
    ).toHaveTextContent('No se pudieron cargar los medios de pago.');
  });

  it('muestra el estado disponible cuando el medio está habilitado y completo', async () => {
    renderComponente();

    expect(
      await screen.findByText(
        'Disponible: los compradores lo ven en el checkout.'
      )
    ).toBeInTheDocument();
  });

  it('muestra el estado incompleto cuando faltan datos obligatorios', async () => {
    const medioIncompleto = {
      ...mediosMock[0],
      disponible: false,
      habilitado: true,
      faltantes: ['cuenta'],
    };

    clienteAxios.get.mockResolvedValue({
      data: [medioIncompleto],
    });

    renderComponente();

    expect(
      await screen.findByText(/Habilitado, pero incompleto/)
    ).toHaveTextContent('Número de cuenta');
  });

  it('muestra el estado deshabilitado cuando el medio no está habilitado', async () => {
    const medioDeshabilitado = {
      ...mediosMock[0],
      disponible: false,
      habilitado: false,
    };

    clienteAxios.get.mockResolvedValue({
      data: [medioDeshabilitado],
    });

    renderComponente();

    expect(
      await screen.findByText(
        'Deshabilitado: no se muestra a los compradores.'
      )
    ).toBeInTheDocument();
  });

  it('muestra un aviso cuando la integración todavía está en desarrollo', async () => {
    const medioEnDesarrollo = {
      ...mediosMock[0],
      integracion_lista: false,
    };

    clienteAxios.get.mockResolvedValue({
      data: [medioEnDesarrollo],
    });

    renderComponente();

    expect(
      await screen.findByText(/Integración en desarrollo/)
    ).toBeInTheDocument();

    expect(
      screen.getByRole('checkbox', {
        name: 'Habilitar Transferencia bancaria',
      })
    ).toBeDisabled();
  });

  it('permite modificar un campo de texto', async () => {
    renderComponente();

    const cuenta = await screen.findByLabelText(/Número de cuenta/);

    fireEvent.change(cuenta, {
      target: { value: '987654321' },
    });

    expect(cuenta).toHaveValue('987654321');
  });

  it('permite modificar una opción de selección', async () => {
    renderComponente();

    const banco = await screen.findByLabelText('Banco (obligatorio)');

    fireEvent.change(banco, {
      target: { value: 'Banco de Chile' },
    });

    expect(banco).toHaveValue('Banco de Chile');
  });

  it('permite habilitar y deshabilitar un medio de pago', async () => {
    renderComponente();

    const checkbox = await screen.findByRole('checkbox', {
      name: 'Habilitar Transferencia bancaria',
    });

    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);

    expect(checkbox).not.toBeChecked();
  });

  it('marca la API Key como opcional cuando el entorno es integración', async () => {
    renderComponente();

    expect(
      await screen.findByLabelText('API Key (opcional)')
    ).toBeInTheDocument();
  });

  it('marca la API Key como obligatoria cuando el entorno es producción', async () => {
    renderComponente();

    const entorno = await screen.findByLabelText('Entorno (obligatorio)');

    fireEvent.change(entorno, {
      target: { value: 'PRODUCCION' },
    });

    expect(
      screen.getByLabelText('API Key (obligatorio)')
    ).toBeInTheDocument();
  });

  it('guarda los cambios correctamente mediante PUT', async () => {
    const respuestaActualizada = {
      ...mediosMock[0],
      disponible: true,
      datos: {
        ...mediosMock[0].datos,
        cuenta: '987654321',
      },
    };

    clienteAxios.put.mockResolvedValue({
      data: respuestaActualizada,
    });

    renderComponente();

    const cuenta = await screen.findByLabelText(/Número de cuenta/);

    fireEvent.change(cuenta, {
      target: { value: '987654321' },
    });

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Guardar Transferencia bancaria',
      })
    );

    await waitFor(() => {
      expect(clienteAxios.put).toHaveBeenCalledWith(
        'ventas/admin/medios-pago/transferencia/',
        expect.objectContaining({
          habilitado: true,
          datos: expect.objectContaining({
            cuenta: '987654321',
          }),
        })
      );
    });

    expect(
      await screen.findByRole('status')
    ).toHaveTextContent('Transferencia bancaria: cambios guardados.');
  });

  it('muestra un error cuando falla el guardado', async () => {
    clienteAxios.put.mockRejectedValue({
      response: {
        data: {
          detail: 'No se pudieron guardar los cambios.',
          datos: {},
        },
      },
    });

    renderComponente();

    await screen.findByText('Transferencia bancaria');

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Guardar Transferencia bancaria',
      })
    );

    expect(
      await screen.findByRole('alert')
    ).toHaveTextContent('No se pudieron guardar los cambios.');
  });

  it('muestra los errores específicos devueltos por el backend', async () => {
    clienteAxios.put.mockRejectedValue({
      response: {
        data: {
          detail: 'Revisa los campos.',
          datos: {
            cuenta: 'El número de cuenta no es válido.',
          },
        },
      },
    });

    renderComponente();

    await screen.findByText('Transferencia bancaria');

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Guardar Transferencia bancaria',
      })
    );

    expect(
      await screen.findByText('El número de cuenta no es válido.')
    ).toBeInTheDocument();

    expect(
      screen.getByLabelText(/Número de cuenta/)
    ).toHaveAttribute('aria-invalid', 'true');
  });
});
