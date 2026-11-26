import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import PedidoRecibido from '../components/PedidoRecibido';

vi.mock('../components/header/header', () => ({
  default: () => <header>Header de prueba</header>
}));

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  localStorage.clear();
});

function LocationDisplay() {
  const location = useLocation();

  return (
    <div data-testid="location">
      {location.pathname + location.search}
    </div>
  );
}

const instruccionesPrueba = {
  monto: 25000,
  referencia: 'ORD-12345',
  vence: '2026-12-30T18:00:00',
  datos: [
    {
      etiqueta: 'Banco',
      valor: 'Banco de Chile'
    },
    {
      etiqueta: 'Tipo de cuenta',
      valor: 'Cuenta corriente'
    },
    {
      etiqueta: 'Número de cuenta',
      valor: '123456789'
    },
    {
      etiqueta: 'Titular',
      valor: 'Tienda de prueba'
    }
  ]
};

function renderComponent(
  initialEntry = '/pedido-recibido',
  state = null
) {
  return render(
    <MemoryRouter
      initialEntries={[
        {
          pathname: initialEntry.split('?')[0],
          search: initialEntry.includes('?')
            ? `?${initialEntry.split('?')[1]}`
            : '',
          state
        }
      ]}
    >
      <PedidoRecibido />
      <LocationDisplay />
    </MemoryRouter>
  );
}

describe('PedidoRecibido', () => {

  it('debe mostrar el título de pedido recibido', () => {
    renderComponent();

    expect(
      screen.getByRole('heading', { name: '¡Pedido recibido!' })
    ).toBeInTheDocument();
  });

  it('debe mostrar que el pedido está pendiente de pago', () => {
    renderComponent();

    expect(
      screen.getByText('Pendiente de pago', { selector: 'span' })
    ).toBeInTheDocument();
  });

  it('debe mostrar el número de orden cuando existe', () => {
    renderComponent('/pedido-recibido?orden=12345');

    expect(
      screen.getByText('#12345')
    ).toBeInTheDocument();

    expect(
      screen.getByText('Número de orden')
    ).toBeInTheDocument();
  });

  it('no debe mostrar el bloque de orden cuando no existe', () => {
    renderComponent();

    expect(
      screen.queryByText('Número de orden')
    ).not.toBeInTheDocument();
  });

  it('debe mostrar los datos para transferir', () => {
    renderComponent(
      '/pedido-recibido?orden=12345',
      { instrucciones: instruccionesPrueba }
    );

    expect(
      screen.getByRole('heading', { name: 'Datos para transferir' })
    ).toBeInTheDocument();

    expect(
      screen.getByText('Banco de Chile')
    ).toBeInTheDocument();

    expect(
      screen.getByText('Cuenta corriente')
    ).toBeInTheDocument();

    expect(
      screen.getByText('123456789')
    ).toBeInTheDocument();
  });

  it('debe mostrar el monto y la referencia de transferencia', () => {
    renderComponent(
      '/pedido-recibido',
      { instrucciones: instruccionesPrueba }
    );

    expect(
      screen.getByText(/25\.000/)
    ).toBeInTheDocument();

    expect(
      screen.getByText('ORD-12345')
    ).toBeInTheDocument();
  });

  it('debe mostrar la fecha de vencimiento', () => {
    renderComponent(
      '/pedido-recibido',
      { instrucciones: instruccionesPrueba }
    );

    expect(
      screen.getByText(/Tienes hasta el/i)
    ).toBeInTheDocument();
  });

  it('no debe mostrar el plazo cuando no existe vencimiento', () => {
    const instrucciones = {
      ...instruccionesPrueba,
      vence: null
    };

    renderComponent(
      '/pedido-recibido',
      { instrucciones }
    );

    expect(
      screen.queryByText(/Tienes hasta el/i)
    ).not.toBeInTheDocument();
  });

  it('debe mostrar el mensaje de correo correspondiente a transferencia', () => {
    renderComponent(
      '/pedido-recibido',
      { instrucciones: instruccionesPrueba }
    );

    expect(
      screen.getByText(/También te enviamos estos datos/i)
    ).toBeInTheDocument();
  });

  it('debe mostrar el mensaje de correo cuando no hay instrucciones', () => {
    renderComponent();

    expect(
      screen.getByText(/Te enviamos el resumen de tu compra/i)
    ).toBeInTheDocument();
  });

  it('debe navegar al catálogo al presionar seguir comprando', () => {
    renderComponent();

    fireEvent.click(
      screen.getByRole('button', { name: /seguir comprando/i })
    );

    expect(
      screen.getByTestId('location')
    ).toHaveTextContent('/catalogo');
  });

  it('debe llevar al invitado al seguimiento de su pedido', () => {
    renderComponent('/pedido-recibido?orden=12345');

    fireEvent.click(
      screen.getByRole('button', { name: /seguir mi pedido/i })
    );

    expect(
      screen.getByTestId('location')
    ).toHaveTextContent('/seguimiento?orden=12345');
  });

  it('debe llevar al usuario autenticado a sus pedidos', () => {
    localStorage.setItem('access_token', 'token-prueba');

    renderComponent('/pedido-recibido?orden=12345');

    fireEvent.click(
      screen.getByRole('button', { name: /ver mis pedidos/i })
    );

    expect(
      screen.getByTestId('location')
    ).toHaveTextContent('/mis-pedidos');
  });

});
