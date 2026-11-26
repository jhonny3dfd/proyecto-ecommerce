import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../components/auth/axiosConfig', () => ({
  default: { 
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}));

import clienteAxios from '../components/auth/axiosConfig';
import GestorPromociones from '../components/GestorPromociones';

describe('GestorPromociones', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clienteAxios.get.mockResolvedValue({ data: [] });
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  afterEach(() => cleanup());

  it('el código queda en mayúsculas y sin espacios mientras se escribe', () => {
    render(<GestorPromociones />);
    const codigo = screen.getByLabelText('Código de Descuento');

    fireEvent.change(codigo, { target: { value: 'verano 20' } });

    expect(codigo).toHaveValue('VERANO20');
    expect(codigo).toHaveAttribute('maxLength', '50');
  });

  it('un porcentaje se limita a 100 y el umbral de envío gratis a montos positivos', () => {
    render(<GestorPromociones />);

    expect(screen.getByLabelText('Valor del Descuento')).toHaveAttribute('max', '100');
    expect(screen.getByLabelText('Umbral Envío Gratis ($)')).toHaveAttribute('min', '1');
    fireEvent.change(screen.getByLabelText('Tipo de Descuento'), { target: { value: 'MONTO_FIJO' } });
    expect(screen.getByLabelText('Valor del Descuento')).not.toHaveAttribute('max');
  });

  it('un código automático con compra mínima se envía con sus campos y sin límite de usos', async () => {
    clienteAxios.post.mockImplementation((_, datos) => Promise.resolve({ data: { id: 1, usos: 0, ...datos } }));
    render(<GestorPromociones />);

    fireEvent.change(screen.getByLabelText('Código de Descuento'), { target: { value: 'sobre30' } });
    fireEvent.change(screen.getByLabelText('Valor del Descuento'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Aplicar automáticamente' }));
    expect(screen.getByLabelText('Compra mínima ($)')).toBeRequired();
    fireEvent.change(screen.getByLabelText('Compra mínima ($)'), { target: { value: '30000' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar Promoción' }));

    await waitFor(() => expect(clienteAxios.post).toHaveBeenCalledWith('ventas/promociones/', expect.objectContaining({
      codigo: 'SOBRE30', automatica: true, monto_minimo: '30000', usos_maximos: null })));
    expect(await screen.findByText('0 (sin límite)')).toBeInTheDocument();
  });

  it('si el servidor rechaza el código, dice por qué', async () => {
    clienteAxios.post.mockRejectedValue({ response: { status: 400, data: {
      valor_descuento: ['Un descuento en porcentaje puede ser de hasta 100.'] } } });
    render(<GestorPromociones />);

    fireEvent.change(screen.getByLabelText('Código de Descuento'), { target: { value: 'TODO' } });
    fireEvent.change(screen.getByLabelText('Valor del Descuento'), { target: { value: '100' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar Promoción' }));

    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(
      'No se pudo guardar el código:\nUn descuento en porcentaje puede ser de hasta 100.'));
  });

  it('muestra las promociones cargadas desde el servidor', async () => {
    clienteAxios.get.mockResolvedValue({
      data: [
        {
          id: 1,
          codigo: 'VERANO20',
          tipo_descuento: 'PORCENTAJE',
          valor_descuento: '20',
          umbral_envio_gratis: '30000',
          monto_minimo: '10000',
          usos: 2,
          usos_maximos: 10,
          automatica: false,
          fecha_expiracion: null
        }
      ]
    });

    render(<GestorPromociones />);

    expect(await screen.findByText('VERANO20')).toBeInTheDocument();
    expect(screen.getByText('Porcentaje')).toBeInTheDocument();
    expect(screen.getByText('20%')).toBeInTheDocument();
    expect(screen.getByText('$30.000')).toBeInTheDocument();
    expect(screen.getByText('$10.000')).toBeInTheDocument();
    expect(screen.getByText('2 de 10')).toBeInTheDocument();
    expect(screen.getByText('Sin vencimiento')).toBeInTheDocument();
  });

  it('maneja errores al cargar las promociones', async () => {
    const error = new Error('Error de conexión');
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    clienteAxios.get.mockRejectedValue(error);

    render(<GestorPromociones />);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Error cargando promociones:',
        error
      );
    });

    consoleSpy.mockRestore();
  });

  it('envía los campos opcionales vacíos como null', async () => {
    clienteAxios.post.mockResolvedValue({
      data: {
        id: 2,
        codigo: 'OFERTA',
        tipo_descuento: 'PORCENTAJE',
        valor_descuento: '15',
        usos: 0,
        usos_maximos: null,
        fecha_expiracion: null
      }
    });

    render(<GestorPromociones />);

    fireEvent.change(screen.getByLabelText('Código de Descuento'), {
      target: { value: 'oferta' }
    });

    fireEvent.change(screen.getByLabelText('Valor del Descuento'), {
      target: { value: '15' }
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar Promoción' })
    );

    await waitFor(() => {
      expect(clienteAxios.post).toHaveBeenCalledWith(
        'ventas/promociones/',
        expect.objectContaining({
          codigo: 'OFERTA',
          umbral_envio_gratis: null,
          monto_minimo: null,
          usos_maximos: null,
          fecha_expiracion: null
        })
      );
    });
  });

  it('envía la fecha de expiración hasta el final del día', async () => {
    clienteAxios.post.mockResolvedValue({
      data: { id: 3 }
    });

    render(<GestorPromociones />);

    fireEvent.change(screen.getByLabelText('Código de Descuento'), {
      target: { value: 'FECHA' }
    });

    fireEvent.change(screen.getByLabelText('Valor del Descuento'), {
      target: { value: '20' }
    });

    fireEvent.change(screen.getByLabelText('Válido hasta (opcional)'), {
      target: { value: '2026-12-31' }
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar Promoción' })
    );

    await waitFor(() => {
      expect(clienteAxios.post).toHaveBeenCalledWith(
        'ventas/promociones/',
        expect.objectContaining({
          fecha_expiracion: '2026-12-31T23:59:59'
        })
      );
    });
  });

  it('carga los datos de una promoción al presionar editar', async () => {
    clienteAxios.get.mockResolvedValue({
      data: [{
        id: 5,
        codigo: 'INVIERNO',
        tipo_descuento: 'MONTO_FIJO',
        valor_descuento: '5000',
        umbral_envio_gratis: '30000',
        monto_minimo: '20000',
        usos_maximos: 5,
        usos: 1,
        automatica: true,
        fecha_expiracion: null
      }]
    });

    render(<GestorPromociones />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Editar' })
    );

    expect(screen.getByLabelText('Código de Descuento'))
      .toHaveValue('INVIERNO');

    expect(screen.getByLabelText('Tipo de Descuento'))
      .toHaveValue('MONTO_FIJO');

    expect(screen.getByLabelText('Valor del Descuento'))
      .toHaveValue(5000);

    expect(screen.getByLabelText('Umbral Envío Gratis ($)'))
      .toHaveValue(30000);

    expect(screen.getByLabelText('Compra mínima ($)'))
      .toHaveValue(20000);

    expect(screen.getByLabelText('Usos máximos'))
      .toHaveValue(5);

    expect(screen.getByRole('checkbox', {
      name: 'Aplicar automáticamente'
    })).toBeChecked();
  });

  it('actualiza una promoción mediante PUT', async () => {
    clienteAxios.get.mockResolvedValue({
      data: [{
        id: 7,
        codigo: 'ANTIGUO',
        tipo_descuento: 'PORCENTAJE',
        valor_descuento: '10',
        umbral_envio_gratis: null,
        monto_minimo: null,
        usos_maximos: null,
        usos: 0,
        automatica: false,
        fecha_expiracion: null
      }]
    });

    clienteAxios.put.mockResolvedValue({
      data: {
        id: 7,
        codigo: 'NUEVO',
        tipo_descuento: 'PORCENTAJE',
        valor_descuento: '25',
        umbral_envio_gratis: null,
        monto_minimo: null,
        usos_maximos: null,
        usos: 0,
        automatica: false,
        fecha_expiracion: null
      }
    });

    render(<GestorPromociones />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Editar' })
    );

    fireEvent.change(screen.getByLabelText('Código de Descuento'), {
      target: { value: 'nuevo' }
    });

    fireEvent.change(screen.getByLabelText('Valor del Descuento'), {
      target: { value: '25' }
    });

    fireEvent.click(
      screen.getByRole('button', { name: 'Guardar Promoción' })
    );

    await waitFor(() => {
      expect(clienteAxios.put).toHaveBeenCalledWith(
        'ventas/promociones/7/',
        expect.objectContaining({
          codigo: 'NUEVO',
          valor_descuento: '25'
        })
      );
    });

    expect(await screen.findByText('NUEVO')).toBeInTheDocument();
    expect(screen.queryByText('ANTIGUO')).not.toBeInTheDocument();
  });

  it('elimina una promoción correctamente', async () => {
    clienteAxios.get.mockResolvedValue({
      data: [{
        id: 8,
        codigo: 'ELIMINAR',
        tipo_descuento: 'PORCENTAJE',
        valor_descuento: '10',
        usos: 0,
        usos_maximos: null,
        automatica: false,
        fecha_expiracion: null
      }]
    });

    clienteAxios.delete = vi.fn().mockResolvedValue({});

    render(<GestorPromociones />);

    expect(await screen.findByText('ELIMINAR')).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', { name: 'Eliminar' })
    );

    await waitFor(() => {
      expect(clienteAxios.delete).toHaveBeenCalledWith(
        'ventas/promociones/8/'
      );
    });

    await waitFor(() => {
      expect(screen.queryByText('ELIMINAR')).not.toBeInTheDocument();
    });
  });

  it('maneja errores al eliminar promociones', async () => {
    const error = new Error('Error al eliminar');
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    clienteAxios.get.mockResolvedValue({
      data: [{
        id: 9,
        codigo: 'NOELIMINAR',
        tipo_descuento: 'PORCENTAJE',
        valor_descuento: '10',
        usos: 0,
        usos_maximos: null,
        automatica: false,
        fecha_expiracion: null
      }]
    });

    clienteAxios.delete = vi.fn().mockRejectedValue(error);

    render(<GestorPromociones />);

    fireEvent.click(
      await screen.findByRole('button', { name: 'Eliminar' })
    );

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Error al eliminar:',
        error
      );
    });

    expect(screen.getByText('NOELIMINAR')).toBeInTheDocument();

    consoleSpy.mockRestore();
  });

  it('muestra una promoción vencida', async () => {
    clienteAxios.get.mockResolvedValue({
      data: [{
        id: 10,
        codigo: 'VENCIDA',
        tipo_descuento: 'MONTO_FIJO',
        valor_descuento: '5000',
        usos: 3,
        usos_maximos: 5,
        automatica: false,
        fecha_expiracion: '2020-01-01T23:59:59'
      }]
    });

    render(<GestorPromociones />);

    expect(await screen.findByText(/vencido/)).toBeInTheDocument();
  });

  it('muestra una promoción automática sin límite de usos', async () => {
    clienteAxios.get.mockResolvedValue({
      data: [{
        id: 11,
        codigo: 'AUTOMATICA',
        tipo_descuento: 'MONTO_FIJO',
        valor_descuento: '5000',
        monto_minimo: '20000',
        usos: 4,
        usos_maximos: null,
        automatica: true,
        fecha_expiracion: null
      }]
    });

    render(<GestorPromociones />);

    expect(await screen.findByText('AUTOMATICA')).toBeInTheDocument();
    expect(screen.getByText('4 (sin límite)')).toBeInTheDocument();
    expect(screen.getByText('Automático')).toBeInTheDocument();
  });
});
