import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { useLocation } from 'react-router-dom';

const { getMock, postMock, ajustarMock, guardarMock, validarMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  ajustarMock: vi.fn(),
  guardarMock: vi.fn(),
  validarMock: vi.fn(),
}));

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: getMock,
    post: postMock,
  },
}));

vi.mock('../components/carrito', async (importOriginal) => ({
  ...await importOriginal(),
  ajustarCarrito: ajustarMock,
  guardarCarrito: guardarMock,
  validarCarrito: validarMock,
}));

import Checkout from '../components/Checkout';

const producto = {
  id: 'producto-1',
  sku: 'SKU-001',
  nombre: 'Teclado mecánico',
  precio: 15000,
  cantidad: 1,
  peso_kg: 1,
  alto_cm: 10,
  ancho_cm: 10,
  largo_cm: 10,
};

// entregaCoordinada: null (desactivada) o { costo, instrucciones }
const CHILEXPRESS = { codigo: 'CHILEXPRESS', nombre: 'Chilexpress', sucursales: true };

function prepararRespuestas({ pasarelas = ['TRANSFERENCIA'], retiroLocal = true, chilexpress = true,
                              entregaCoordinada = null, couriers = chilexpress ? [CHILEXPRESS] : [],
                              automaticos = [] } = {}) {
  getMock.mockImplementation((url) => {
    if (url === 'ventas/promociones/automaticas/') {
      return Promise.resolve({ data: automaticos });
    }
    if (url === 'configuracion/') {
      return Promise.resolve({
        data: {
          pasarelas_activas: pasarelas,
          retiro_en_local_activo: retiroLocal,
          couriers,
          entrega_coordinada_activa: Boolean(entregaCoordinada),
          costo_entrega_coordinada: entregaCoordinada?.costo ?? 0,
          instrucciones_entrega_coordinada: entregaCoordinada?.instrucciones ?? '',
          calle_origen: 'Av. Principal',
          numero_origen: '123',
          comuna_origen: 'Santiago',
          region_origen: 'Metropolitana',
        },
      });
    }

    if (url === 'ventas/logistica/comunas/') {
      return Promise.resolve({ data: { comunas: ['Santiago'] } });
    }

    if (url === 'ventas/checkout/reglas/') {
      return Promise.resolve({ data: { modo_autenticacion: 'INVITADO' } });
    }

    if (url === 'ventas/paginas-legales/') {
      return Promise.resolve({ data: ['TERMINOS', 'PRIVACIDAD'].map((tipo_pagina) => ({ tipo_pagina })) });
    }

    return Promise.resolve({ data: [] });
  });

  postMock.mockResolvedValue({ data: {} });
  validarMock.mockResolvedValue([producto]);
  ajustarMock.mockReturnValue({ items: [producto], avisos: [] });
  guardarMock.mockImplementation(async (items) => {
    const snapshot = JSON.stringify(items);

    if (localStorage.getItem('carrito_local') !== snapshot) {
      localStorage.setItem('carrito_local', snapshot);
      window.dispatchEvent(new Event('carritoActualizado'));
    }
    return items;
  });
}

function renderCheckout({ conProducto = true } = {}) {
  if (conProducto) {
    localStorage.setItem('carrito_local', JSON.stringify([producto]));
  }

  return render(
    <MemoryRouter>
      <Checkout />
    </MemoryRouter>
  );
}

// Con datos faltantes el botón responde (avisa qué falta) pero se anuncia como no disponible
function noSePuedePagar(boton) {
  expect(boton).toHaveAttribute('aria-disabled', 'true');
}

function sePuedePagar(boton) {
  expect(boton).toBeEnabled();
  expect(boton).not.toHaveAttribute('aria-disabled');
}

const escribirCorreo = () => fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
  target: { value: 'qa@example.test' },
});

function completarDestinatario() {
  fireEvent.change(screen.getByLabelText(/nombre de quien recibe/i), {
    target: { value: 'Comprador QA' },
  });
  fireEvent.change(screen.getByLabelText(/teléfono de contacto/i), {
    target: { value: '+56912345678' },
  });
}

function MostrarRutaActual() {
  const location = useLocation();

  return (
    <p data-testid="ruta-actual">
      {location.pathname}
      {location.search}
    </p>
  );
}

function renderCheckoutConRuta({ conProducto = true } = {}) {
  if (conProducto) {
    localStorage.setItem(
      'carrito_local',
      JSON.stringify([producto])
    );
  }

  return render(
    <MemoryRouter>
      <Checkout />
      <MostrarRutaActual />
    </MemoryRouter>
  );
}

describe('Checkout', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.removeItem('access_token');
    prepararRespuestas();
  });

  afterEach(() => {
    cleanup();
  });

  it('muestra el checkbox legal desmarcado por defecto', async () => {
    renderCheckout();

    const checkbox = await screen.findByRole('checkbox', {
      name: /acepto los/i,
    });

    expect(checkbox).not.toBeChecked();
  });

  it('mantiene deshabilitado el botón de pago mientras no se acepten los términos', async () => {
    renderCheckout();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    completarDestinatario();
    escribirCorreo();

    noSePuedePagar(botonPago);

    const checkbox = screen.getByRole('checkbox', { name: /acepto los/i });
    fireEvent.click(checkbox);

    await waitFor(() => sePuedePagar(botonPago));
  });

  it('permite marcar y desmarcar el checkbox legal', async () => {
    renderCheckout();

    const checkbox = await screen.findByRole('checkbox', {
      name: /acepto los/i,
    });

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it('mantiene deshabilitado el pago cuando el carrito está vacío', async () => {
    renderCheckout({ conProducto: false });

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    const checkbox = screen.getByRole('checkbox', { name: /acepto los/i });
    fireEvent.click(checkbox);

    noSePuedePagar(botonPago);
    fireEvent.click(botonPago);
    expect(screen.getByRole('alert')).toHaveTextContent('agregar productos al carrito');
  });

  it('muestra los enlaces a las páginas legales cuando están publicadas', async () => {
    renderCheckout();

    expect(
      await screen.findByRole('link', { name: /términos y condiciones/i })
    ).toHaveAttribute('href', '/legal/terminos');

    expect(
      screen.getByRole('link', { name: /política de privacidad/i })
    ).toHaveAttribute('href', '/legal/privacidad');
  });


  it('deshabilita nuevamente el pago si se desmarcan los términos', async () => {
    renderCheckout();

    const botonPago = await screen.findByRole('button', {
        name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(
        screen.getByRole('radio', { name: /retiro en local/i })
    );

    const checkbox = screen.getByRole('checkbox', {
        name: /acepto los/i,
    });

    completarDestinatario();
    escribirCorreo();
    fireEvent.click(checkbox);
    await waitFor(() => sePuedePagar(botonPago));

    fireEvent.click(checkbox);

    expect(checkbox).not.toBeChecked();
    noSePuedePagar(botonPago);
  });

  it('no envía la compra cuando los términos no han sido aceptados', async () => {
    renderCheckout();

    const botonPago = await screen.findByRole('button', {
        name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(
        screen.getByRole('radio', { name: /retiro en local/i })
    );

    const checkbox = screen.getByRole('checkbox', {
        name: /acepto los/i,
    });

    expect(checkbox).not.toBeChecked();
    noSePuedePagar(botonPago);

    fireEvent.click(botonPago);

    expect(postMock).not.toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.anything()
    );
    expect(screen.getByRole('alert')).toHaveTextContent('aceptar los Términos y Condiciones');
  });

  it('envía acepta_terminos como true al confirmar la compra', async () => {
    renderCheckout();

    const botonPago = await screen.findByRole('button', {
        name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(
        screen.getByRole('radio', { name: /retiro en local/i })
    );

    const checkbox = screen.getByRole('checkbox', {
        name: /acepto los/i,
    });

    fireEvent.click(checkbox);

    fireEvent.change(screen.getByLabelText(/nombre de quien recibe/i), {
      target: { value: 'Comprador QA' },
    });
    fireEvent.change(screen.getByLabelText(/teléfono de contacto/i), {
      target: { value: '+56912345678' },
    });
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => expect(botonPago).toBeEnabled());

    fireEvent.click(botonPago);

    await waitFor(() => {
        expect(postMock).toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.objectContaining({
            acepta_terminos: true,
        })
        );
    });
  });

  it('envía al checkout el cupón que validó el servidor para que lo descuente del total', async () => {
    postMock.mockImplementation((url) => (url === 'ventas/promociones/validar/'
      ? Promise.resolve({ data: { codigo: 'VERANO20', tipo_descuento: 'PORCENTAJE', valor_descuento: 20,
                                  descuento: 3000, umbral_envio_gratis: null } })
      : Promise.resolve({ data: {} })));
    renderCheckout();

    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    fireEvent.change(screen.getByPlaceholderText(/cupón de descuento/i), { target: { value: 'verano20' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      'ventas/promociones/validar/', { codigo: 'VERANO20', subtotal: 15000 }));
    expect(await screen.findByText('-$3.000')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    completarDestinatario();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@example.test' } });
    await waitFor(() => expect(botonPago).toBeEnabled());
    fireEvent.click(botonPago);

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      'ventas/checkout/', expect.objectContaining({ codigo_promocion: 'VERANO20' })));
  });

  it('un cupón rechazado por el servidor no descuenta ni viaja en el checkout', async () => {
    postMock.mockImplementation((url) => (url === 'ventas/promociones/validar/'
      ? Promise.reject({ response: { data: { error: 'Código inválido o expirado.' } } })
      : Promise.resolve({ data: {} })));
    renderCheckout();

    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    fireEvent.change(screen.getByPlaceholderText(/cupón de descuento/i), { target: { value: 'VENCIDO' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    expect(await screen.findByText('Código inválido o expirado.')).toBeInTheDocument();
    expect(screen.queryByText(/^Descuento/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    completarDestinatario();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@example.test' } });
    await waitFor(() => expect(botonPago).toBeEnabled());
    fireEvent.click(botonPago);

    await waitFor(() => expect(postMock).toHaveBeenCalledWith(
      'ventas/checkout/', expect.objectContaining({ codigo_promocion: null })));
  });

  it('muestra todos los medios de pago configurados', async () => {
    prepararRespuestas({
        pasarelas: ['TRANSFERENCIA', 'TRANSBANK'],
    });

    renderCheckout();

    expect(
        await screen.findByRole('button', {
            name: 'Pagar con Transferencia bancaria',
        })
    ).toBeInTheDocument();

    expect(
        screen.getByRole('button', {
            name: 'Pagar con Webpay (Transbank)',
        })
    ).toBeInTheDocument();
  });

  it('muestra un mensaje si no hay medios de pago configurados', async () => {
    prepararRespuestas({ pasarelas: [] });

    renderCheckout();

    expect(
        await screen.findByText(
            'No hay métodos de pago configurados en la tienda.'
        )
    ).toBeInTheDocument();

    expect(
        screen.queryByRole('button', {
            name: /pagar con/i,
        })
    ).not.toBeInTheDocument();
  });

  it('muestra correctamente el subtotal de varios productos', async () => {
    const segundoProducto = {
        ...producto,
        id: 'producto-2',
        sku: 'SKU-002',
        nombre: 'Mouse inalámbrico',
        precio: 10000,
        cantidad: 1,
    };

    localStorage.setItem(
        'carrito_local',
        JSON.stringify([producto, segundoProducto])
    );

    render(
        <MemoryRouter>
            <Checkout />
        </MemoryRouter>
    );

    expect(
        await screen.findByText('Teclado mecánico (x1)')
    ).toBeInTheDocument();

    expect(
        screen.getByText('Mouse inalámbrico (x1)')
    ).toBeInTheDocument();

    const subtotalLabel = screen.getByText('Subtotal:');
    const subtotalContainer = subtotalLabel.parentElement;

    expect(subtotalContainer).toHaveTextContent('$25.000');
  });

  it('mantiene el checkout disponible si falla la carga de páginas legales', async () => {
    getMock.mockImplementation((url) => {
        if (url === 'ventas/paginas-legales/') {
            return Promise.reject(new Error('Error de conexión'));
        }

        if (url === 'configuracion/') {
            return Promise.resolve({
                data: {
                    pasarelas_activas: ['TRANSFERENCIA'],
                    retiro_en_local_activo: true,
                    calle_origen: 'Av. Principal',
                    numero_origen: '123',
                    comuna_origen: 'Santiago',
                    region_origen: 'Metropolitana',
                },
            });
        }

        if (url === 'ventas/logistica/comunas/') {
            return Promise.resolve({
                data: { comunas: ['Santiago'] },
            });
        }

        if (url === 'ventas/checkout/reglas/') {
            return Promise.resolve({
                data: { modo_autenticacion: 'INVITADO' },
            });
        }

        return Promise.resolve({ data: [] });
    });

    renderCheckout();

    expect(
        await screen.findByRole('checkbox', {
            name: /acepto los/i,
        })
    ).toBeInTheDocument();

    expect(
        screen.queryByRole('link', {
            name: /términos y condiciones/i,
        })
    ).not.toBeInTheDocument();

    expect(
        screen.queryByRole('link', {
            name: /política de privacidad/i,
        })
    ).not.toBeInTheDocument();
  });

  it('muestra un error si no se pueden cargar las reglas del checkout', async () => {
    getMock.mockImplementation((url) => {
        if (url === 'ventas/checkout/reglas/') {
            return Promise.reject(new Error('Error de conexión'));
        }

        if (url === 'configuracion/') {
            return Promise.resolve({
                data: {
                    pasarelas_activas: ['TRANSFERENCIA'],
                    retiro_en_local_activo: true,
                },
            });
        }

        if (url === 'ventas/logistica/comunas/') {
            return Promise.resolve({
                data: { comunas: ['Santiago'] },
            });
        }

        if (url === 'ventas/paginas-legales/') {
            return Promise.resolve({ data: [] });
        }

        return Promise.resolve({ data: [] });
    });

    renderCheckout();

    expect(await screen.findByRole('alert')).toHaveTextContent(
        'No se pudieron cargar las opciones de compra.'
    );

    expect(screen.queryByText('Cargando...')).not.toBeInTheDocument();
  });

  it('solicita una cotización y muestra el costo de envío devuelto por el backend', async () => {
    postMock.mockImplementation((url) => {
        if (url === 'ventas/logistica/cotizar/') {
            return Promise.resolve({
                data: {
                    opciones: [{ proveedor: 'CHILEXPRESS', nombre: 'Chilexpress', tiempo_estimado: '2 días', precio: 3500 }],
                },
            });
        }

        return Promise.resolve({ data: {} });
    });

    renderCheckout();

    await screen.findByRole('option', { name: 'Santiago' });

    const selectorComuna = screen.getByLabelText('Comuna');

    fireEvent.change(selectorComuna, {
        target: { value: 'Santiago' },
    });

    await waitFor(() => {
        expect(postMock).toHaveBeenCalledWith(
            'ventas/logistica/cotizar/',
            // RF-02.3: los productos, no el peso ni las medidas; el paquete lo arma el servidor con el catálogo
            {
                destino: 'SANTIAGO',
                items: [{ producto_mongo_id: 'producto-1', variante_sku: 'SKU-001', cantidad: 1 }],
            },
            expect.objectContaining({ signal: expect.any(AbortSignal) })
        );
    });

    expect(
        await screen.findByText('Chilexpress - 2 días')
    ).toBeInTheDocument();

    expect(screen.getAllByText('$3.500')).toHaveLength(2);
  });

  it('muestra un mensaje cuando falla la cotización del envío', async () => {
    postMock.mockImplementation((url) => {
        if (url === 'ventas/logistica/cotizar/') {
            return Promise.reject(new Error('Error de conexión'));
        }

        return Promise.resolve({ data: {} });
    });

    renderCheckout();

    await screen.findByRole('option', { name: 'Santiago' });

    fireEvent.change(screen.getByLabelText('Comuna'), {
        target: { value: 'Santiago' },
    });

    expect(
        await screen.findByText(
            'No se pudo calcular el costo de envío.'
        )
    ).toBeInTheDocument();

    expect(
        screen.queryByText('Chilexpress - 2 días')
    ).not.toBeInTheDocument();
  });

  it('sincroniza el resumen y el contador al cambiar cantidades desde el encabezado', async () => {
    validarMock.mockResolvedValue({
      items: [{
        producto_mongo_id: producto.id,
        variante_sku: producto.sku,
        disponible: 5,
        precio: producto.precio,
        problema: null,
      }],
    });

    renderCheckout();

    await screen.findByRole('checkbox', { name: /acepto los/i });

    validarMock.mockResolvedValue({
      items: [{ producto_mongo_id: producto.id, variante_sku: producto.sku,
        disponible: 5, precio: producto.precio, problema: null }],
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Carrito de compras, 1 producto' }));
    fireEvent.click(screen.getByRole('button', { name: /aumentar cantidad de teclado/i }));

    expect(await screen.findByText('Teclado mecánico (x2)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Carrito de compras, 2 productos' })).toBeInTheDocument();
    expect(screen.getByText('Subtotal:').parentElement).toHaveTextContent('$30.000');

    fireEvent.click(screen.getByRole('button', { name: /quitar teclado.*del carrito/i }));
    await waitFor(() => expect(screen.getByRole('button', {
      name: 'Carrito de compras, 0 productos',
    })).toBeInTheDocument());
    expect(screen.getByText('No hay productos')).toBeInTheDocument();
    noSePuedePagar(screen.getByRole('button', { name: 'Pagar con Transferencia bancaria' }));
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });

  it('muestra un mensaje cuando el backend rechaza la compra', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.reject({
          response: { data: {} },
        });
      }

      return Promise.resolve({ data: {} });
    });

    try {
      renderCheckout();

      const botonPago = await screen.findByRole('button', {
        name: 'Pagar con Transferencia bancaria',
      });

      fireEvent.click(
        screen.getByRole('radio', { name: /retiro en local/i })
      );
      fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));

      completarDestinatario();

      fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
        target: { value: 'qa@example.test' },
      });

      await waitFor(() => expect(botonPago).toBeEnabled());

      fireEvent.click(botonPago);

      expect(
        await screen.findByText('Error al procesar la compra.')
      ).toBeInTheDocument();
    } finally {
      errorSpy.mockRestore();
    }
  });

  it('actualiza el precio del carrito cuando el servidor informa un cambio de precio', async () => {
    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.reject({
          response: {
            data: {
              precios_vigentes: [
                {
                  variante_sku: 'SKU-001',
                  precio: 12000,
                },
              ],
            },
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    try {
      renderCheckout();

      const botonPago = await screen.findByRole('button', {
        name: 'Pagar con Transferencia bancaria',
      });

      fireEvent.click(
        screen.getByRole('radio', { name: /retiro en local/i })
      );
      fireEvent.click(
        screen.getByRole('checkbox', { name: /acepto los/i })
      );

      completarDestinatario();

      fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
        target: { value: 'qa@example.test' },
      });

      await waitFor(() => expect(botonPago).toBeEnabled());

      fireEvent.click(botonPago);

      await waitFor(() => {
        expect(guardarMock).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              sku: 'SKU-001',
              precio: 12000,
            }),
          ])
        );
      });
    } finally {
      errorSpy.mockRestore();
    }
  });

  it('limpia el carrito cuando la compra es exitosa', async () => {
    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.resolve({
          data: {
            orden_id: 'ORD-001',
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(
      screen.getByRole('radio', { name: /retiro en local/i })
    );

    fireEvent.click(
      screen.getByRole('checkbox', { name: /acepto los/i })
    );

    completarDestinatario();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => {
      expect(botonPago).toBeEnabled();
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.objectContaining({
          acepta_terminos: true,
        })
      );
    });

    await waitFor(() => {
      expect(
        JSON.parse(localStorage.getItem('carrito_local') || '[]')
      ).toHaveLength(0);
    });

    await waitFor(() => {
      expect(screen.getByTestId('ruta-actual').textContent).toBe('/pedido-recibido?orden=ORD-001');
    });
  });

  it('guarda la orden pendiente y abre Mercado Pago cuando recibe url_pago', async () => {
    const abrirVentana = vi.spyOn(window, 'open').mockReturnValue({});

    prepararRespuestas({
      pasarelas: ['MERCADO_PAGO'],
    });

    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.resolve({
          data: {
            orden_id: 'ORD-MP-001',
            url_pago: 'https://mercadopago.example/pagar/ORD-MP-001',
            token_verificacion: 'token-prueba-mp',
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: /pagar con mercado pago/i,
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));

    completarDestinatario();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => {
      expect(botonPago).toBeEnabled();
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.objectContaining({
          acepta_terminos: true,
        })
      );
    });

    await waitFor(() => {
      expect(abrirVentana).toHaveBeenCalledWith(
        'https://mercadopago.example/pagar/ORD-MP-001',
        '_blank'
      );
    });

    expect(localStorage.getItem('orden_pendiente_pago')).toBe('ORD-MP-001');
    expect(localStorage.getItem('orden_pendiente_token')).toBe('token-prueba-mp');

    abrirVentana.mockRestore();
  });


  it('un descuento automático se aplica solo y avisa cuánto falta para el siguiente', async () => {
    // El carrito es de $15.000: el 10 % desde $10.000 se aplica; el de $5.000 desde $20.000 todavía no
    prepararRespuestas({ automaticos: [
      { tipo_descuento: 'PORCENTAJE', valor_descuento: 10, monto_minimo: 10000, umbral_envio_gratis: null },
      { tipo_descuento: 'MONTO_FIJO', valor_descuento: 5000, monto_minimo: 20000, umbral_envio_gratis: null },
    ] });
    renderCheckoutConRuta();
    await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });

    expect(await screen.findByText('Descuento (automático):')).toBeInTheDocument();
    expect(screen.getByText('-$1.500')).toBeInTheDocument();
    expect(screen.getByText(/Agrega \$5\.000 más y obtén \$5\.000 de descuento/)).toBeInTheDocument();
  });

  it('el suscriptor con sesión ve su descuento; sin sesión no se piden beneficios (suscripciones)', async () => {
    prepararRespuestas();
    const base = getMock.getMockImplementation();
    getMock.mockImplementation((url) => {
      if (url === 'ventas/suscripciones/beneficios/') return Promise.resolve({ data: { descuento: 10, envio_gratis: true } });
      if (url === 'configuracion/') return base(url).then(({ data }) => ({ data: { ...data, suscripciones_activas: true } }));
      return base(url);
    });
    localStorage.setItem('access_token', 'token-suscriptor');
    renderCheckoutConRuta();

    expect(await screen.findByText('Descuento de suscriptor (10%):')).toBeInTheDocument();
    expect(screen.getByText('-$1.500')).toBeInTheDocument();
    expect(screen.getByText('Total a pagar:').parentElement).toHaveTextContent('$13.500');
    cleanup();

    localStorage.removeItem('access_token');
    getMock.mockClear();
    renderCheckoutConRuta();
    await screen.findByText('Total a pagar:');
    expect(screen.queryByText(/Descuento de suscriptor/)).not.toBeInTheDocument();
    expect(getMock).not.toHaveBeenCalledWith('ventas/suscripciones/beneficios/');
  });

  it('con un código menor que el automático se queda el automático y se avisa', async () => {
    prepararRespuestas({ automaticos: [
      { tipo_descuento: 'PORCENTAJE', valor_descuento: 20, monto_minimo: 10000, umbral_envio_gratis: null },
    ] });
    postMock.mockImplementation((url) => url === 'ventas/promociones/validar/'
      ? Promise.resolve({ data: { codigo: 'CINCO', tipo_descuento: 'PORCENTAJE', valor_descuento: 5,
        monto_minimo: null, umbral_envio_gratis: null } })
      : Promise.resolve({ data: {} }));
    renderCheckoutConRuta();
    await screen.findByText('Descuento (automático):');

    fireEvent.change(screen.getByLabelText('Cupón de descuento'), { target: { value: 'cinco' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar' }));

    expect(await screen.findByText(/ya tiene un descuento mayor/)).toBeInTheDocument();
    expect(screen.getByText('-$3.000')).toBeInTheDocument();
  });

  it('al intentar pagar sin los datos dice qué falta, lleva al primer campo y la lista se achica al completar', async () => {
    prepararRespuestas();
    renderCheckoutConRuta();
    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@sin-punto' } });

    fireEvent.click(botonPago);

    const aviso = screen.getByRole('alert');
    expect(aviso).toHaveTextContent('Para pagar, completa:');
    expect([...aviso.querySelectorAll('li')].map(li => li.textContent)).toEqual([
      'un correo electrónico válido', 'el nombre de quien recibe', 'el teléfono de contacto',
      'aceptar los Términos y Condiciones y la Política de Privacidad',
    ]);
    expect(screen.getByLabelText(/correo electrónico/i)).toHaveFocus();
    expect(botonPago).toHaveAttribute('aria-describedby', 'checkout-faltantes');
    expect(postMock).not.toHaveBeenCalledWith('ventas/checkout/', expect.anything());

    escribirCorreo();
    completarDestinatario();
    expect(screen.getByRole('alert')).toHaveTextContent(/^Para pagar, completa:aceptar los Términos/);
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    expect(screen.queryByText('Para pagar, completa:')).not.toBeInTheDocument();
    sePuedePagar(botonPago);
  });

  it('cada medio de pago muestra su logo, decorativo: el botón se nombra por su texto', async () => {
    prepararRespuestas({ pasarelas: ['TRANSBANK', 'MERCADO_PAGO', 'TRANSFERENCIA'] });
    renderCheckoutConRuta();

    const webpay = await screen.findByRole('button', { name: 'Pagar con Webpay (Transbank)' });
    const mercadoPago = screen.getByRole('button', { name: 'Pagar con Mercado Pago' });
    const transferencia = screen.getByRole('button', { name: 'Pagar con Transferencia bancaria' });
    expect(webpay.querySelector('img')).toHaveAttribute('src', expect.stringContaining('webpay'));
    expect(mercadoPago.querySelector('img')).toHaveAttribute('src', expect.stringContaining('mercado-pago'));
    expect(webpay.querySelector('img')).toHaveAttribute('alt', '');
    expect(transferencia.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('el teléfono de contacto no acepta letras', async () => {
    prepararRespuestas();
    renderCheckoutConRuta();
    await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });

    const telefono = screen.getByLabelText(/teléfono de contacto/i);
    fireEvent.change(telefono, { target: { value: '+56 9 abc1234 5678' } });

    expect(telefono).toHaveValue('+56 9 1234 5678');
  });

  it('no procesa la compra cuando falta el nombre del destinatario', async () => {
    prepararRespuestas();
    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));

    fireEvent.change(screen.getByLabelText(/teléfono/i), {
      target: { value: '912345678' },
    });

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(postMock).not.toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.anything()
      );
    });
  });

  it('no procesa la compra si no se aceptan los términos legales', async () => {
    prepararRespuestas();
    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));

    completarDestinatario();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(postMock).not.toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.anything()
      );
    });
  });

  it('maneja el fallo al verificar el estado de una orden pendiente', async () => {
    prepararRespuestas();

    localStorage.setItem('orden_pendiente_pago', 'ORD-MP-001');
    localStorage.setItem('orden_pendiente_token', 'token-prueba');

    getMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/verificar-pago/') {
        return Promise.reject(new Error('Error de conexión'));
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckoutConRuta();

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith(
        'ventas/checkout/verificar-pago/',
        expect.anything()
      );
    });

    expect(screen.getByTestId('ruta-actual')).toBeInTheDocument();
  });

  it('muestra el error del backend cuando falla el checkout', async () => {
    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.reject({
          response: {
            data: {
              error: 'No fue posible procesar el pago',
            },
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));

    completarDestinatario();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => {
      expect(botonPago).toBeEnabled();
    });

    fireEvent.click(botonPago);

   expect(
    await screen.findByRole('status')
   ).toHaveTextContent(/error al procesar la compra/i);

    expect(JSON.parse(localStorage.getItem('carrito_local') || '[]').length)
      .toBeGreaterThan(0);
  });

  it('maneja los precios vigentes que devuelve el backend', async () => {
    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.reject({
          response: {
            data: {
              error: 'Los precios han cambiado',
              precios_vigentes: [
                {
                  sku: 'SKU-001',
                  precio: '15000',
                },
              ],
            },
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));

    completarDestinatario();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => {
      expect(botonPago).toBeEnabled();
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.anything()
      );
    });

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem('carrito_local') || '[]').length)
        .toBeGreaterThan(0);
    });
  });

  it('redirige a pedido recibido cuando el checkout termina correctamente', async () => {
    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.resolve({
          data: {
            orden_id: 'ORD-001',
            instrucciones_pago: 'Realiza la transferencia con el número de orden.',
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckoutConRuta();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));

    completarDestinatario();

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => {
      expect(botonPago).toBeEnabled();
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(screen.getByTestId('ruta-actual').textContent).toBe(
        '/pedido-recibido?orden=ORD-001'
      );
    });

    await waitFor(() => {
      expect(JSON.parse(localStorage.getItem('carrito_local') || '[]'))
        .toHaveLength(0);
    });
  });

  it('revisa y guarda el carrito cuando el backend devuelve errores en los artículos', async () => {
    renderCheckout();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(
      screen.getByRole('radio', { name: /retiro en local/i })
    );

    fireEvent.click(
      screen.getByRole('checkbox', { name: /acepto los/i })
    );

    fireEvent.change(screen.getByLabelText(/nombre de quien recibe/i), {
      target: { value: 'Comprador QA' },
    });

    fireEvent.change(screen.getByLabelText(/teléfono de contacto/i), {
      target: { value: '+56912345678' },
    });

    fireEvent.change(screen.getByLabelText(/correo electrónico/i), {
      target: { value: 'qa@example.test' },
    });

    await waitFor(() => {
      expect(botonPago).toBeEnabled();
    });

    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.reject({
          response: {
            data: {
              items: ['Uno o más productos cambiaron.'],
            },
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    fireEvent.click(botonPago);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith(
        'ventas/checkout/',
        expect.objectContaining({
          acepta_terminos: true,
        })
      );
    });

    await waitFor(() => {
      expect(validarMock).toHaveBeenCalled();
    });
  });

  it('carga las direcciones guardadas y selecciona la predeterminada', async () => {
    const direcciones = [
      {
        id: 1,
        calle: 'Los Aromos',
        calle_numero: '123',
        dpto_casa: '',
        comuna: 'Santiago',
        ciudad: 'Santiago',
        region: 'Metropolitana',
        es_predeterminado: false,
      },
      {
        id: 2,
        calle: 'Calle Falsa',
        calle_numero: '123',
        dpto_casa: 'Casa 2',
        comuna: 'Santiago',
        ciudad: 'Santiago',
        region: 'Metropolitana',
        es_predeterminado: true,
      },
    ];

    localStorage.setItem('access_token', 'token-prueba');

    getMock.mockImplementation((url) => {
      if (url === 'usuarios/me/') {
        return Promise.resolve({
          data: { id: 10, email: 'qa@example.test' },
        });
      }

      if (url === 'ventas/direcciones/') {
        return Promise.resolve({ data: direcciones });
      }

      if (url === 'configuracion/') {
        return Promise.resolve({
          data: {
            pasarelas_activas: ['TRANSFERENCIA'],
            retiro_en_local_activo: true,
            calle_origen: 'Av. Principal',
            numero_origen: '123',
            comuna_origen: 'Santiago',
            region_origen: 'Metropolitana',
          },
        });
      }

      if (url === 'ventas/logistica/comunas/') {
        return Promise.resolve({
          data: { comunas: ['Santiago'] },
        });
      }

      if (url === 'ventas/checkout/reglas/') {
        return Promise.resolve({
          data: { modo_autenticacion: 'INVITADO' },
        });
      }

      if (url === 'ventas/paginas-legales/') {
        return Promise.resolve({
          data: [
            { tipo_pagina: 'TERMINOS' },
            { tipo_pagina: 'PRIVACIDAD' },
          ],
        });
      }

      return Promise.resolve({ data: [] });
    });

    renderCheckout();

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('ventas/direcciones/');
    });
  });

  it('permite elegir comprar como invitado en modo MIXTO', async () => {
    getMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/reglas/') {
        return Promise.resolve({
          data: { modo_autenticacion: 'MIXTO' },
        });
      }

      if (url === 'configuracion/') {
        return Promise.resolve({
          data: {
            pasarelas_activas: ['TRANSFERENCIA'],
            retiro_en_local_activo: true,
          },
        });
      }

      if (url === 'ventas/logistica/comunas/') {
        return Promise.resolve({
          data: { comunas: ['Santiago'] },
        });
      }

      if (url === 'ventas/paginas-legales/') {
        return Promise.resolve({
          data: [
            { tipo_pagina: 'TERMINOS' },
            { tipo_pagina: 'PRIVACIDAD' },
          ],
        });
      }

      return Promise.resolve({ data: [] });
    });

    renderCheckout();

    expect(
      await screen.findByRole('button', {
        name: /comprar como invitado/i,
      })
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole('button', {
        name: /comprar como invitado/i,
      })
    );

    expect(
      await screen.findByRole('button', {
        name: 'Pagar con Transferencia bancaria',
      })
    ).toBeInTheDocument();
  });

  it('actualiza el precio del carrito si el backend informa un precio vigente', async () => {
    postMock.mockImplementation((url) => {
      if (url === 'ventas/checkout/') {
        return Promise.reject({
          response: {
            data: {
              precios_vigentes: [
                {
                  variante_sku: producto.sku,
                  precio: 12000,
                },
              ],
            },
          },
        });
      }

      return Promise.resolve({ data: {} });
    });

    renderCheckout();

    const botonPago = await screen.findByRole('button', {
      name: 'Pagar con Transferencia bancaria',
    });

    fireEvent.click(
      screen.getByRole('radio', { name: /retiro en local/i })
    );
    fireEvent.click(
      screen.getByRole('checkbox', { name: /acepto los/i })
    );
    completarDestinatario();

    fireEvent.change(
      screen.getByLabelText(/correo electrónico/i),
      { target: { value: 'qa@example.test' } }
    );

    await waitFor(() => expect(botonPago).toBeEnabled());
    fireEvent.click(botonPago);

    await waitFor(() => {
      const carrito = JSON.parse(
        localStorage.getItem('carrito_local')
      );

      expect(carrito[0].precio).toBe(12000);
    });

    expect(
      await screen.findByText('Teclado mecánico (x1)')
    ).toBeInTheDocument();
  });

});

describe('Checkout: entrega coordinada (RF-02.3)', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => cleanup());

  const completarDireccion = () => {
    fireEvent.change(screen.getByLabelText('Calle'), { target: { value: 'Los Aromos' } });
    fireEvent.change(screen.getByLabelText('Número'), { target: { value: '1550' } });
    fireEvent.change(screen.getByLabelText('Comuna'), { target: { value: 'Ñuñoa' } });
    fireEvent.change(screen.getByLabelText('Ciudad'), { target: { value: 'Santiago' } });
  };

  it('sin Chilexpress no ofrece despacho ni sucursales, ni pide sus comunas', async () => {
    prepararRespuestas({ chilexpress: false, retiroLocal: false,
                         entregaCoordinada: { costo: 3000, instrucciones: 'Te escribimos por WhatsApp.' } });
    renderCheckout();

    const opcion = await screen.findByRole('radio', { name: 'Entrega coordinada' });
    expect(opcion).toBeChecked();
    expect(screen.queryByRole('radio', { name: /a domicilio/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /sucursal/i })).not.toBeInTheDocument();
    expect(screen.getByText('Te escribimos por WhatsApp.')).toBeInTheDocument();
    // La comuna se escribe a mano: no hay lista de cobertura
    expect(screen.getByLabelText('Comuna').tagName).toBe('INPUT');
    expect(getMock).not.toHaveBeenCalledWith('ventas/logistica/comunas/');
    expect(screen.queryByText(/no se pudieron cargar las comunas/i)).not.toBeInTheDocument();
  });

  it('cobra el costo del admin y envía la dirección sin paquete ni cotización', async () => {
    prepararRespuestas({ chilexpress: false, retiroLocal: false, entregaCoordinada: { costo: 3000 } });
    renderCheckout();

    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    await screen.findByRole('radio', { name: 'Entrega coordinada' });
    expect(screen.getByText('La tienda te contactará para acordar el día y la hora de la entrega.')).toBeInTheDocument();
    expect(screen.getByText('Total a pagar:').parentElement).toHaveTextContent('$18.000');

    completarDireccion();
    completarDestinatario();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@example.test' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    await waitFor(() => expect(botonPago).toBeEnabled());
    fireEvent.click(botonPago);

    await waitFor(() => expect(postMock).toHaveBeenCalledWith('ventas/checkout/', expect.objectContaining({
      proveedor_logistico: 'ENTREGA_COORDINADA',
      direccion_envio_snapshot: expect.objectContaining({ calle: 'Los Aromos', numero: '1550', comuna: 'Ñuñoa' }),
    })));
    // El navegador nunca manda el paquete: lo arma el servidor (RF-02.3)
    const [, cuerpo] = postMock.mock.calls.find(([url]) => url === 'ventas/checkout/');
    expect(cuerpo).not.toHaveProperty('paquete');
    expect(postMock).not.toHaveBeenCalledWith('ventas/logistica/cotizar/', expect.anything(), expect.anything());
  });

  it('la dirección es opcional: sin ella se compra y la tienda la acuerda con el comprador', async () => {
    prepararRespuestas({ chilexpress: false, retiroLocal: false, entregaCoordinada: { costo: 3000 } });
    renderCheckout();

    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    expect(screen.getByText(/la dirección es opcional/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Calle')).not.toBeRequired();
    completarDestinatario();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@example.test' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    await waitFor(() => expect(botonPago).toBeEnabled());
    fireEvent.click(botonPago);

    await waitFor(() => expect(postMock).toHaveBeenCalledWith('ventas/checkout/', expect.objectContaining({
      proveedor_logistico: 'ENTREGA_COORDINADA',
      direccion_envio_snapshot: {},
    })));
  });

  it('si escribe una dirección a medias pide la calle y la comuna', async () => {
    prepararRespuestas({ chilexpress: false, retiroLocal: false, entregaCoordinada: { costo: 3000 } });
    renderCheckout();

    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    fireEvent.change(screen.getByLabelText('Calle'), { target: { value: 'Los Aromos' } });
    completarDestinatario();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@example.test' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    noSePuedePagar(botonPago);
    fireEvent.click(botonPago);

    // Escribió la calle: entonces la comuna también hace falta (la calle no se pide de nuevo)
    const aviso = await screen.findByRole('alert');
    expect(aviso).toHaveTextContent('la comuna');
    expect(aviso).not.toHaveTextContent('la calle');
    expect(postMock).not.toHaveBeenCalledWith('ventas/checkout/', expect.anything());
  });

  it('con varios couriers el comprador elige con cuál enviar y se cobra ese', async () => {
    prepararRespuestas({ couriers: [CHILEXPRESS, { codigo: 'STARKEN', nombre: 'Starken', sucursales: false }] });
    postMock.mockImplementation((url) => Promise.resolve({ data: url === 'ventas/logistica/cotizar/' ? {
      opciones: [
        { proveedor: 'CHILEXPRESS', nombre: 'Chilexpress', tiempo_estimado: 'EXPRESS', precio: 3990 },
        { proveedor: 'STARKEN', nombre: 'Starken', tiempo_estimado: '', precio: 3500 },
      ],
    } : { orden_id: 7, instrucciones_pago: {} } }));
    renderCheckout();

    await screen.findByRole('option', { name: 'Santiago' });
    // Con un solo courier con oficinas, el retiro lleva su nombre
    expect(screen.getByRole('radio', { name: 'Sucursal Chilexpress' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'qa@example.test' } });
    fireEvent.change(screen.getByLabelText('Calle'), { target: { value: 'Uno' } });
    fireEvent.change(screen.getByLabelText('Número'), { target: { value: '123' } });
    fireEvent.change(screen.getByLabelText('Comuna'), { target: { value: 'Santiago' } });
    fireEvent.change(screen.getByLabelText('Ciudad'), { target: { value: 'Santiago' } });

    const chilexpress = await screen.findByRole('radio', { name: /Chilexpress - EXPRESS/ });
    expect(chilexpress).toBeChecked();
    expect(postMock).toHaveBeenCalledWith('ventas/logistica/cotizar/', expect.not.objectContaining({ proveedor: expect.anything() }),
      expect.anything());
    fireEvent.click(screen.getByRole('radio', { name: /Starken/ }));
    expect(screen.getByRole('radio', { name: /Starken/ })).toBeChecked();

    completarDestinatario();
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    fireEvent.click(screen.getByRole('button', { name: 'Pagar con Transferencia bancaria' }));

    await waitFor(() => expect(postMock).toHaveBeenCalledWith('ventas/checkout/',
      expect.objectContaining({ proveedor_logistico: 'STARKEN' })));
  });

  it('con Chilexpress se ofrece junto al despacho, que sigue siendo la opción por defecto', async () => {
    prepararRespuestas({ entregaCoordinada: { costo: 0 } });
    renderCheckout();

    expect(await screen.findByRole('radio', { name: /a domicilio/i })).toBeChecked();
    expect(screen.getByRole('radio', { name: /sucursal chilexpress/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /retiro en local/i })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Entrega coordinada' })).not.toBeChecked();
  });

  it('sin ninguna forma de entrega lo avisa y no deja pagar', async () => {
    prepararRespuestas({ chilexpress: false, retiroLocal: false });
    renderCheckout();

    expect(await screen.findByText('Esta tienda todavía no tiene formas de entrega disponibles.')).toBeInTheDocument();
    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    completarDestinatario();
    const botonPago = screen.getByRole('button', { name: 'Pagar con Transferencia bancaria' });
    noSePuedePagar(botonPago);
    fireEvent.click(botonPago);
    expect(screen.getByRole('alert')).toHaveTextContent('una forma de entrega');
  });
});

describe('Checkout: compra como empresa', () => {
  const EMPRESA = {
    razon_social: 'Comercial Andes SpA', rut: '761234560', giro: 'Venta de artículos de regalo',
    direccion: 'Av. Providencia 1234', correo: 'facturas@andes.test'
  };

  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    localStorage.clear();
    prepararRespuestas();
  });

  afterEach(() => cleanup());

  const prepararPago = async () => {
    const botonPago = await screen.findByRole('button', { name: 'Pagar con Transferencia bancaria' });
    fireEvent.click(screen.getByRole('radio', { name: /retiro en local/i }));
    completarDestinatario();
    fireEvent.change(screen.getByLabelText(/correo electrónico/i), { target: { value: 'compras@andes.test' } });
    fireEvent.click(screen.getByRole('checkbox', { name: /acepto los/i }));
    await waitFor(() => expect(botonPago).toBeEnabled());
    return botonPago;
  };

  const completarEmpresa = (datos) => {
    fireEvent.click(screen.getByRole('checkbox', { name: /compro como empresa/i }));
    const etiquetas = { razon_social: 'Razón social', rut: 'RUT de la empresa', giro: 'Giro',
                        direccion: 'Dirección comercial', correo: 'Correo para la factura' };
    Object.entries(datos).forEach(([campo, valor]) =>
      fireEvent.change(screen.getByLabelText(etiquetas[campo]), { target: { value: valor } }));
  };

  const payloadCheckout = () => postMock.mock.calls.find(([url]) => url === 'ventas/checkout/')?.[1];

  it('una persona compra sin datos de empresa', async () => {
    renderCheckout();
    fireEvent.click(await prepararPago());

    await waitFor(() => expect(payloadCheckout()).toBeDefined());
    expect(payloadCheckout()).toMatchObject({ datos_empresa: null, guardar_datos_empresa: false });
    expect(screen.queryByLabelText('Razón social')).not.toBeInTheDocument();
  });

  it('envía los datos para la factura con el RUT normalizado', async () => {
    renderCheckout();
    const botonPago = await prepararPago();
    completarEmpresa(EMPRESA);
    fireEvent.click(botonPago);

    await waitFor(() => expect(payloadCheckout()).toBeDefined());
    expect(payloadCheckout().datos_empresa).toEqual({ ...EMPRESA, rut: '76.123.456-0' });
    // Un invitado no tiene dónde guardarlos
    expect(payloadCheckout().guardar_datos_empresa).toBe(false);
  });

  it('un RUT inválido o un dato faltante se marca junto al campo y no se envía la compra', async () => {
    renderCheckout();
    const botonPago = await prepararPago();
    completarEmpresa({ ...EMPRESA, rut: '76.123.456-1', giro: '' });
    fireEvent.click(botonPago);

    const rut = screen.getByLabelText('RUT de la empresa');
    await waitFor(() => expect(rut).toHaveAttribute('aria-invalid', 'true'));
    expect(rut).toHaveAccessibleDescription(/dígito verificador/);
    expect(screen.getByLabelText('Giro')).toHaveAccessibleDescription('Este dato es obligatorio para la factura.');
    expect(payloadCheckout()).toBeUndefined();

    // Al corregir el campo, su error desaparece
    fireEvent.change(rut, { target: { value: '76.123.456-0' } });
    expect(rut).not.toHaveAttribute('aria-invalid');
  });

  it('muestra junto al campo el error que devuelve el servidor', async () => {
    postMock.mockImplementation((url) => (url === 'ventas/checkout/'
      ? Promise.reject({ response: { data: { datos_empresa: { correo: ['Introduzca una dirección de correo electrónico válida.'] } } } })
      : Promise.resolve({ data: {} })));
    vi.spyOn(console, 'error').mockImplementation(() => {});
    renderCheckout();
    const botonPago = await prepararPago();
    completarEmpresa(EMPRESA);
    fireEvent.click(botonPago);

    await waitFor(() => expect(screen.getByLabelText('Correo para la factura'))
      .toHaveAccessibleDescription('Introduzca una dirección de correo electrónico válida.'));
  });

  it('con sesión precarga los datos guardados y ofrece guardarlos de nuevo', async () => {
    localStorage.setItem('access_token', 'token-de-prueba');
    const anterior = getMock.getMockImplementation();
    getMock.mockImplementation((url) => (url === 'ventas/empresa/'
      ? Promise.resolve({ data: { ...EMPRESA, rut: '76.123.456-0' } })
      : anterior(url)));
    renderCheckout();

    fireEvent.click(await screen.findByRole('checkbox', { name: /compro como empresa/i }));

    await waitFor(() => expect(screen.getByLabelText('Razón social')).toHaveValue('Comercial Andes SpA'));
    expect(screen.getByLabelText('RUT de la empresa')).toHaveValue('76.123.456-0');
    expect(screen.getByRole('checkbox', { name: /guardar los datos de la empresa/i })).toBeChecked();
  });
});
