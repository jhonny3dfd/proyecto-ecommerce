import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// La revisión de stock llama al servidor: en estas pruebas se controla cuándo responde
vi.mock('../components/carrito', async (original) => ({ ...(await original()), validarCarrito: vi.fn() }));

import { validarCarrito } from '../components/carrito';
import CarritoCompras from '../components/CarritoCompras';

const productosEjemplo = [
  {
    sku: 'SKU-001',
    nombre: 'Teclado mecánico',
    precio: 15000,
    cantidad: 2,
  },
  {
    sku: 'SKU-002',
    nombre: 'Mouse gamer',
    precio: 10000,
    cantidad: 1,
  },
];

function renderCarrito() {
  return render(
    <MemoryRouter>
      <CarritoCompras />
    </MemoryRouter>
  );
}

describe('CarritoCompras', () => {
  beforeEach(() => {
    cleanup();
    localStorage.clear();
  });

  it('muestra cero productos cuando el carrito está vacío', () => {
    renderCarrito();

    expect(
      screen.getByRole('button', {
        name: 'Carrito de compras, 0 productos',
      })
    ).toBeInTheDocument();

    expect(
      screen.queryByText('Tu carrito está vacío')
    ).not.toBeInTheDocument();
  });

  it('muestra el mensaje cuando se abre un carrito vacío', () => {
    renderCarrito();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Carrito de compras, 0 productos',
      })
    );

    expect(screen.getByText('Mi Carrito')).toBeInTheDocument();
    expect(screen.getByText('Tu carrito está vacío')).toBeInTheDocument();
  });

  it('carga los productos guardados en localStorage', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify(productosEjemplo)
    );

    renderCarrito();

    expect(
      screen.getByRole('button', {
        name: 'Carrito de compras, 3 productos',
      })
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Carrito de compras, 3 productos',
      })
    );

    expect(screen.getByText('Teclado mecánico')).toBeInTheDocument();
    expect(screen.getByText('Mouse gamer')).toBeInTheDocument();
    expect(screen.getByLabelText('Cantidad: 2')).toBeInTheDocument();
    expect(screen.getByLabelText('Cantidad: 1')).toBeInTheDocument();
  });

  it('calcula los subtotales y el total correctamente', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify(productosEjemplo)
    );

    renderCarrito();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Carrito de compras, 3 productos',
      })
    );

    const subtotalTeclado =
      `$${(15000 * 2).toLocaleString('es-CL')}`;
    const subtotalMouse =
      `$${(10000).toLocaleString('es-CL')}`;
    const total =
      `$${(40000).toLocaleString('es-CL')}`;

    expect(screen.getByText(subtotalTeclado)).toBeInTheDocument();
    expect(screen.getByText(subtotalMouse)).toBeInTheDocument();
    expect(screen.getByText('Total:')).toBeInTheDocument();
    expect(screen.getByText(total)).toBeInTheDocument();
  });

  it('actualiza el contador al recibir carritoActualizado', () => {
    renderCarrito();

    localStorage.setItem(
      'carrito_local',
      JSON.stringify(productosEjemplo)
    );

    fireEvent(
      window,
      new Event('carritoActualizado')
    );

    expect(
      screen.getByRole('button', {
        name: 'Carrito de compras, 3 productos',
      })
    ).toBeInTheDocument();
  });

  it('permite abrir y cerrar el carrito con el botón', () => {
    renderCarrito();

    const boton = screen.getByRole('button', {
      name: 'Carrito de compras, 0 productos',
    });

    fireEvent.click(boton);
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument();
    expect(boton).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(boton);
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument();
    expect(boton).toHaveAttribute('aria-expanded', 'false');
  });

  it('el carrito sigue abierto al cambiar la cantidad y el foco queda en el botón', async () => {
    localStorage.setItem('carrito_local', JSON.stringify([{ ...productosEjemplo[0], id: 'teclado' }]));
    let responder;
    validarCarrito.mockReturnValue(new Promise((resolve) => { responder = resolve; }));
    renderCarrito();
    fireEvent.click(screen.getByRole('button', { name: /Carrito de compras/ }));

    const mas = screen.getByRole('button', { name: 'Aumentar cantidad de Teclado mecánico' });
    mas.focus();
    fireEvent.click(mas);
    // Mientras revisa el stock el botón queda inactivo, pero enfocado: un blur sin destino no cierra el carrito
    expect(mas).toHaveAttribute('aria-disabled', 'true');
    fireEvent.focusOut(mas, { relatedTarget: null });
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument();

    responder({ items: [{ producto_mongo_id: 'teclado', variante_sku: 'SKU-001', disponible: 10, precio: 15000, problema: null }] });
    expect(await screen.findByLabelText('Cantidad: 3')).toBeInTheDocument();
    await waitFor(() => expect(mas).toHaveAttribute('aria-disabled', 'false'));
    expect(mas).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'Disminuir cantidad de Teclado mecánico' }));
    expect(await screen.findByLabelText('Cantidad: 2')).toBeInTheDocument();
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument();
  });

  it('se cierra cuando el foco sale del carrito, por ejemplo con Tab', () => {
    render(<MemoryRouter><CarritoCompras /><button type="button">Afuera</button></MemoryRouter>);
    const boton = screen.getByRole('button', { name: /Carrito de compras/ });
    fireEvent.click(boton);

    fireEvent.focusOut(boton, { relatedTarget: screen.getByRole('button', { name: 'Afuera' }) });

    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument();
  });

  it('cierra el carrito al hacer clic fuera de él', () => {
    renderCarrito();

    const boton = screen.getByRole('button', {
      name: 'Carrito de compras, 0 productos',
    });

    fireEvent.click(boton);
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument();

    fireEvent.mouseDown(document.body);

    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument();
  });

  it('enlaza al checkout y cierra el carrito al pulsar Ir a Pagar', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify(productosEjemplo)
    );

    renderCarrito();

    fireEvent.click(
      screen.getByRole('button', {
        name: 'Carrito de compras, 3 productos',
      })
    );

    const enlacePago = screen.getByRole('link', {
      name: 'Ir a Pagar',
    });

    expect(enlacePago).toHaveAttribute('href', '/checkout');

    fireEvent.click(enlacePago);

    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument();
  });

  it('se actualiza al eliminar los datos guardados y emitir el evento', () => {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify(productosEjemplo)
    );

    renderCarrito();

    localStorage.removeItem('carrito_local');

    fireEvent(
      window,
      new Event('carritoActualizado')
    );

    expect(
      screen.getByRole('button', {
        name: 'Carrito de compras, 0 productos',
      })
    ).toBeInTheDocument();
  });
});
