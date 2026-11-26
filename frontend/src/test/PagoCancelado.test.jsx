import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, it, expect, vi, afterEach } from 'vitest';
import PagoCancelado from '../components/PagoCancelado';

afterEach(() => {
  cleanup();
});

vi.mock('./header/header', () => ({
  default: () => <header>Header de prueba</header>
}));

function LocationDisplay() {
  const location = useLocation();

  return <div data-testid="location">{location.pathname}</div>;
}

function renderComponent(initialEntry = '/pago-cancelado') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PagoCancelado />
      <LocationDisplay />
    </MemoryRouter>
  );
}

describe('PagoCancelado', () => {

  it('debe mostrar el título de pago cancelado', () => {
    renderComponent();

    expect(
      screen.getByRole('heading', { name: 'Pago cancelado' })
    ).toBeInTheDocument();
  });

  it('debe mostrar el mensaje de que no se realizó ningún cargo', () => {
    renderComponent();

    expect(
        screen.getByText(/no se ha realizado ningún cargo en tu cuenta/i)
    ).toBeInTheDocument();
  });

  it('debe mostrar el número de orden cuando existe', () => {
    renderComponent('/pago-cancelado?orden=12345');

    expect(
      screen.getByText('Orden #12345')
    ).toBeInTheDocument();
  });

  it('no debe mostrar el número de orden cuando no existe', () => {
    renderComponent();

    expect(
      screen.queryByText(/Orden #/)
    ).not.toBeInTheDocument();
  });

  it('debe navegar al checkout al presionar el botón', () => {
    renderComponent();

    fireEvent.click(
      screen.getByRole('button', { name: /volver al checkout/i })
    );

    expect(screen.getByTestId('location')).toHaveTextContent('/checkout');
  });

  it('debe navegar al catálogo al presionar el botón', () => {
    renderComponent();

    fireEvent.click(
      screen.getByRole('button', { name: /ir al catálogo/i })
    );

    expect(screen.getByTestId('location')).toHaveTextContent('/catalogo');
  });

});
