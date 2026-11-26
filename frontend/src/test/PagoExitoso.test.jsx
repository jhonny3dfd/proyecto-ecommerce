import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import PagoExitoso from '../components/PagoExitoso';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/header/header', () => ({
  default: () => <header>Header de prueba</header>
}));

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    post: vi.fn().mockResolvedValue({})
  }
}));

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
});

function LocationDisplay() {
  const location = useLocation();

  return (
    <div data-testid="location">
      {location.pathname + location.search}
    </div>
  );
}

function renderComponent(initialEntry = '/pago-exitoso') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PagoExitoso />
      <LocationDisplay />
    </MemoryRouter>
  );
}

describe('PagoExitoso', () => {

  it('debe mostrar el título de pago exitoso', () => {
    renderComponent();

    expect(
      screen.getByRole('heading', { name: '¡Pago exitoso!' })
    ).toBeInTheDocument();
  });

  it('debe mostrar el mensaje de compra procesada correctamente', () => {
    renderComponent();

    expect(
      screen.getByText('Tu compra se ha procesado correctamente.')
    ).toBeInTheDocument();
  });

  it('debe mostrar el número de orden cuando existe', () => {
    renderComponent('/pago-exitoso?orden=12345');

    expect(screen.getByText('#12345')).toBeInTheDocument();

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

  it('debe mostrar el mensaje correspondiente cuando el pago está en revisión', () => {
    renderComponent('/pago-exitoso?orden=12345&revision=1');

    expect(
      screen.getByRole('heading', { name: '¡Pago recibido!' })
    ).toBeInTheDocument();

    expect(
      screen.getByText(/la tienda revisará tu pedido/i)
    ).toBeInTheDocument();
  });

  it('debe limpiar el carrito local y la orden pendiente', () => {
    localStorage.setItem('carrito_local', JSON.stringify([
      { id: 1, cantidad: 2 }
    ]));

    localStorage.setItem('orden_pendiente_pago', '12345');

    renderComponent();

    expect(localStorage.getItem('carrito_local')).toBeNull();

    expect(
      localStorage.getItem('orden_pendiente_pago')
    ).toBeNull();
  });

  it('debe navegar al catálogo al presionar seguir comprando', () => {
    renderComponent();

    fireEvent.click(
      screen.getByRole('button', { name: /seguir comprando/i })
    );

    expect(screen.getByTestId('location'))
      .toHaveTextContent('/catalogo');
  });

  it('debe llevar al invitado al seguimiento de su pedido', () => {
    renderComponent('/pago-exitoso?orden=12345');

    fireEvent.click(
      screen.getByRole('button', { name: /seguir mi pedido/i })
    );

    expect(screen.getByTestId('location'))
      .toHaveTextContent('/seguimiento?orden=12345');
  });

  it('debe llevar al usuario autenticado a sus pedidos', () => {
    localStorage.setItem('access_token', 'token-prueba');

    renderComponent('/pago-exitoso?orden=12345');

    fireEvent.click(
      screen.getByRole('button', { name: /ver mis pedidos/i })
    );

    expect(screen.getByTestId('location'))
      .toHaveTextContent('/mis-pedidos');
  });

  it('debe limpiar el carrito del servidor cuando el usuario está autenticado', () => {
    localStorage.setItem('access_token', 'token-prueba');

    renderComponent();

    expect(clienteAxios.post).toHaveBeenCalledWith(
      'ventas/carrito/',
      { items: [] }
    );
  });

  it('no debe llamar al backend cuando el usuario es invitado', () => {
    renderComponent();

    expect(clienteAxios.post).not.toHaveBeenCalled();
  });

});
