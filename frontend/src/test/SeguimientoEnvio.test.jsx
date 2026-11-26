import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SeguimientoEnvio from '../pages/SeguimientoEnvio';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    post: postMock,
  },
}));

vi.mock('../components/header/header', () => ({
  default: () => <header>Header de prueba</header>,
}));

function renderSeguimiento(url = '/seguimiento') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <SeguimientoEnvio />
    </MemoryRouter>
  );
}

function completarFormulario({
  orden = '123',
  email = 'cliente@ejemplo.cl',
} = {}) {
  fireEvent.change(screen.getByLabelText(/número de orden/i), {
    target: { value: orden },
  });

  fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
    target: { value: email },
  });

  fireEvent.click(
    screen.getByRole('button', { name: /consultar seguimiento/i })
  );
}

describe('SeguimientoEnvio', () => {
  beforeEach(() => {
    postMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('muestra el formulario y el encabezado', () => {
    renderSeguimiento();

    expect(screen.getByText('Header de prueba')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Seguimiento de pedido' })
    ).toBeInTheDocument();

    expect(screen.getByLabelText(/número de orden/i)).toBeRequired();
    expect(screen.getByLabelText(/correo electrónico/i)).toBeRequired();
    expect(
      screen.getByRole('button', { name: 'Consultar seguimiento' })
    ).toBeEnabled();
  });

  it('precarga el número de orden desde la URL', () => {
    renderSeguimiento('/seguimiento?orden=456');

    expect(screen.getByLabelText(/número de orden/i)).toHaveValue('456');
  });

  it('consulta la API con el número de orden y correo', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '123',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'En tránsito',
        codigo_seguimiento: 'OT-123',
      },
    });

    renderSeguimiento();
    completarFormulario();

    await screen.findByRole('heading', { name: 'Pedido #123' });

    expect(postMock).toHaveBeenCalledWith('ventas/tracking/', {
      numero_orden: '123',
      email: 'cliente@ejemplo.cl',
    });
  });

  it('muestra el estado de carga mientras espera la API', async () => {
    let resolver;
    postMock.mockReturnValue(
      new Promise((resolve) => {
        resolver = resolve;
      })
    );

    renderSeguimiento();
    completarFormulario();

    expect(
      await screen.findByRole('button', { name: 'Consultando...' })
    ).toBeDisabled();

    resolver({
      data: {
        numero_orden: '123',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'En tránsito',
        codigo_seguimiento: 'OT-123',
      },
    });

    expect(
      await screen.findByRole('heading', { name: 'Pedido #123' })
    ).toBeInTheDocument();
  });

  it('muestra el error devuelto por el servidor', async () => {
    postMock.mockRejectedValue({
      response: { data: { error: 'El pedido no coincide con los datos ingresados.' } },
    });

    renderSeguimiento();
    completarFormulario();

    expect(
      await screen.findByRole('alert')
    ).toHaveTextContent('El pedido no coincide con los datos ingresados.');

    expect(screen.getByLabelText(/número de orden/i))
      .toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText(/correo electrónico/i))
      .toHaveAttribute('aria-describedby', 'seguimiento-error');
  });

  it('muestra un error genérico si la API falla sin mensaje', async () => {
    postMock.mockRejectedValue(new Error('Error de red'));

    renderSeguimiento();
    completarFormulario();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo consultar el seguimiento del pedido.'
    );
  });

  it('muestra el aviso de pedido pendiente de despacho', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '124',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'Pendiente de despacho',
        codigo_seguimiento: '',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '124' });

    expect(await screen.findByRole('heading', { name: 'Pedido #124' })).toBeInTheDocument();
    expect(screen.getByText('Pendiente de despacho', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText(
      'El pedido aún no ha sido entregado al proveedor logístico.'
    )).toBeInTheDocument();
    expect(screen.getByText('Pendiente', { selector: 'dd' })).toBeInTheDocument();
  });

  it('muestra el aviso de retiro local pendiente', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '125',
        entrega_de_la_tienda: true,
        proveedor: 'Retiro en local',
        estado_actual: 'Listo para retirar',
        instrucciones: 'Tu pedido todavía está pendiente de retiro en la tienda.',
        codigo_seguimiento: '',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '125' });

    expect(await screen.findByText('Tu pedido todavía está pendiente de retiro en la tienda.'))
      .toBeInTheDocument();
    expect(screen.queryByText('Proveedor')).not.toBeInTheDocument();
    expect(screen.queryByText('Código de seguimiento')).not.toBeInTheDocument();
  });

  it('muestra el aviso cuando un pedido de retiro local fue entregado', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '126',
        entrega_de_la_tienda: true,
        proveedor: 'Retiro en local',
        estado_actual: 'Retirado',
        instrucciones: 'Tu pedido fue entregado en la tienda.',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '126' });

    expect(await screen.findByText('Retirado')).toBeInTheDocument();
    expect(screen.getByText('Tu pedido fue entregado en la tienda.'))
      .toBeInTheDocument();
  });

  it('muestra el aviso de pedido cancelado sin código de seguimiento', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '127',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'Cancelado',
        codigo_seguimiento: 'OT-127',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '127' });

    expect(await screen.findByText('Pedido cancelado')).toBeInTheDocument();
    expect(screen.getByText('Este pedido fue cancelado.')).toBeInTheDocument();
    expect(screen.queryByText('Código de seguimiento')).not.toBeInTheDocument();
  });

  it('muestra la línea de seguimiento hasta el estado En tránsito', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '128',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'En tránsito',
        codigo_seguimiento: 'OT-128',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '128' });

    await screen.findByRole('heading', { name: 'Pedido #128' });

    expect(screen.getByText('CHILEXPRESS')).toBeInTheDocument();
    expect(screen.getByText('OT-128')).toBeInTheDocument();

    const pasos = screen.getByRole('list').querySelectorAll('li');

    expect(pasos[0]).toHaveClass('seguimiento-paso--hecho');
    expect(pasos[1]).toHaveAttribute('aria-current', 'step');
    expect(pasos[2]).not.toHaveClass('seguimiento-paso--hecho');
    expect(pasos[3]).not.toHaveClass('seguimiento-paso--hecho');
  });

  it('muestra todos los pasos completados cuando el pedido fue entregado por proveedor', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '129',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'Entregado',
        codigo_seguimiento: 'OT-129',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '129' });

    await screen.findByRole('heading', { name: 'Pedido #129' });

    const pasos = screen.getByRole('list').querySelectorAll('li');

    expect(pasos[3]).toHaveAttribute('aria-current', 'step');

    for (const paso of Array.from(pasos).slice(0, 3)) {
    expect(paso).toHaveClass('seguimiento-paso--hecho');
    }
  });

  it('muestra el estado de despacho sin código cuando no está informado', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '130',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'En origen',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '130' });

    await screen.findByRole('heading', { name: 'Pedido #130' });

    expect(screen.getByText('Pendiente', { selector: 'dd' }))
      .toBeInTheDocument();
  });

  it('mueve el foco al título del resultado al terminar la consulta', async () => {
    postMock.mockResolvedValue({
      data: {
        numero_orden: '131',
        proveedor: 'CHILEXPRESS',
        estado_actual: 'En origen',
        codigo_seguimiento: 'OT-131',
      },
    });

    renderSeguimiento();
    completarFormulario({ orden: '131' });

    const titulo = await screen.findByRole('heading', { name: 'Pedido #131' });

    await waitFor(() => {
      expect(titulo).toHaveFocus();
    });
  });

  it('permite realizar otra consulta después de un error', async () => {
    postMock
      .mockRejectedValueOnce({
        response: { data: { error: 'Datos incorrectos.' } },
      })
      .mockResolvedValueOnce({
        data: {
          numero_orden: '132',
          proveedor: 'CHILEXPRESS',
          estado_actual: 'En origen',
          codigo_seguimiento: 'OT-132',
        },
      });

    renderSeguimiento();
    completarFormulario({ orden: '132' });

    expect(await screen.findByRole('alert')).toHaveTextContent('Datos incorrectos.');

    completarFormulario({ orden: '132' });

    expect(await screen.findByRole('heading', { name: 'Pedido #132' }))
      .toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(postMock).toHaveBeenCalledTimes(2);
  });
});
