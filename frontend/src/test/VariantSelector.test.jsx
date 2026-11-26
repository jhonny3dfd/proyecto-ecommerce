import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import VariantSelector from '../components/VariantSelector';

const producto = {
  id: 1,
  variantes: [
    { sku: 'POL-NEG-S', atributos_variables: { color: 'Negro', talla: 'S' }, precio: 20000, precio_oferta: 15000, stock: 5 },
    { sku: 'POL-NEG-M', atributos_variables: { color: 'Negro', talla: 'M' }, precio: 20000, precio_oferta: null, stock: 3 },
    { sku: 'POL-BLA-S', atributos_variables: { color: 'Blanco', talla: 'S' }, precio: 18000, precio_oferta: null, stock: 0 },
  ],
};

function renderSelector(datos = producto, callback = vi.fn()) {
  return render(<VariantSelector producto={datos} onAgregarAlCarrito={callback} />);
}

function elegir(color = 'Negro', talla = 'S') {
  fireEvent.click(screen.getByRole('button', { name: color }));

  const grupoTalla = screen.getByRole('group', { name: /talla/i });
  fireEvent.click(
    within(grupoTalla).getByRole('button', {
      name: new RegExp(`^${talla}(\\s*\\(Agotado\\))?$`),
    })
  );
}

describe('VariantSelector', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('muestra un aviso si no hay producto seleccionado', () => {
    renderSelector(null);
    expect(screen.getByText('No se ha seleccionado ningún producto.')).toBeInTheDocument();
  });

  it('muestra un aviso si el producto no tiene variantes', () => {
    renderSelector({ id: 2, variantes: [] });
    expect(screen.getByText('Este producto no tiene variantes disponibles.')).toBeInTheDocument();
  });

  it.each([{}, undefined])('permite comprar la única variante sin atributos (%j)', async (atributos) => {
    const variante = { sku: 'UNICA', precio: 10000, stock: 2, atributos_variables: atributos };
    const callback = vi.fn().mockResolvedValue({ ok: true, mensaje: 'Agregado.' });
    renderSelector({ id: 2, variantes: [variante] }, callback);
    expect(screen.getByText('Stock disponible: 2')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agregar al carrito' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Cantidad'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Agregar al carrito' }));
    await waitFor(() => expect(callback).toHaveBeenCalledWith(variante, 2));
    expect(await screen.findByRole('status')).toHaveTextContent('Agregado.');
  });

  it('mantiene agotada la variante sin atributos cuando su stock es cero', () => {
    const callback = vi.fn();
    renderSelector({ id: 2, variantes: [{ sku: 'UNICA', precio: 10000, stock: 0 }] }, callback);
    expect(screen.getByRole('button', { name: 'Agotado', exact: true })).toBeDisabled();
    expect(screen.queryByLabelText('Cantidad')).not.toBeInTheDocument();
    expect(callback).not.toHaveBeenCalled();
  });

  it('descuenta el carrito y bloquea al alcanzar el stock de la variante sin atributos', async () => {
    localStorage.setItem('carrito_local', JSON.stringify([{ sku: 'UNICA', cantidad: 1 }]));
    renderSelector({ id: 2, variantes: [{ sku: 'UNICA', precio: 10000, stock: 2 }] });
    expect(screen.getByLabelText('Cantidad')).toHaveAttribute('max', '1');
    expect(screen.getByRole('button', { name: 'Agregar al carrito' })).toBeEnabled();
    localStorage.setItem('carrito_local', JSON.stringify([{ sku: 'UNICA', cantidad: 2 }]));
    window.dispatchEvent(new Event('carritoActualizado'));
    expect(await screen.findByRole('button', { name: 'Agotado (en tu carrito)' })).toBeDisabled();
  });

  it('muestra los grupos y opciones únicas de atributos', () => {
    renderSelector();
    expect(screen.getByRole('group', { name: 'color' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'talla' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Negro' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Blanco' })).toBeInTheDocument();
  });

  it('muestra precio de oferta, precio anterior, stock y SKU', () => {
    renderSelector();
    elegir();
    expect(screen.getByText('$15.000')).toBeInTheDocument();
    expect(screen.getByText('$20.000')).toBeInTheDocument();
    expect(screen.getByText('Stock disponible: 5')).toBeInTheDocument();
    expect(screen.getByText('SKU: POL-NEG-S')).toBeInTheDocument();
    expect(screen.getByLabelText('Cantidad')).toHaveValue(1);
  });

  it('muestra el precio normal si no hay oferta válida', () => {
    renderSelector();
    elegir('Negro', 'M');
    expect(screen.getByText('$20.000')).toBeInTheDocument();
    expect(screen.queryByText('Precio anterior:')).not.toBeInTheDocument();
  });

  it('no permite agregar sin una variante seleccionada', () => {
    renderSelector();
    expect(
        screen.getByRole('button', { name: 'Agotado' })
    ).toBeDisabled();
  });

  it('muestra agotado al seleccionar una variante sin stock', () => {
    render(
        <VariantSelector
        producto={producto}
        onAgregarAlCarrito={vi.fn()}
        />
    );

    elegir('Blanco', 'S');

    expect(screen.getByText('Agotado', { selector: 'p' }))
        .toBeInTheDocument();

    expect(screen.getByRole('alert')).toHaveTextContent(
        'Esta variante se encuentra agotada.'
    );

    expect(
        screen.getByRole('button', { name: 'Agotado', exact: true })
    ).toBeDisabled();
  });

  it('descuenta del stock las unidades ya agregadas al carrito', () => {
    localStorage.setItem('carrito_local', JSON.stringify([{ sku: 'POL-NEG-S', cantidad: 2 }]));
    renderSelector();
    elegir();
    expect(screen.getByText('Stock disponible: 3 (2 en tu carrito)')).toBeInTheDocument();
    expect(screen.getByLabelText('Cantidad')).toHaveAttribute('max', '3');
  });

  it('marca agotada la variante si todo el stock ya está en el carrito', () => {
    localStorage.setItem('carrito_local', JSON.stringify([{ sku: 'POL-NEG-S', cantidad: 5 }]));
    renderSelector();
    elegir();
    expect(screen.getByText('Agotado (ya tienes las 5 unidades disponibles en tu carrito)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Agotado (en tu carrito)' })).toBeDisabled();
  });

  it('limita la cantidad al stock disponible y al mínimo de uno', () => {
    renderSelector();
    elegir();
    const input = screen.getByLabelText('Cantidad');
    fireEvent.change(input, { target: { value: '99' } });
    expect(input).toHaveValue(5);
    fireEvent.change(input, { target: { value: '0' } });
    expect(input).toHaveValue(1);
  });

  it('llama al callback con la variante y cantidad y muestra éxito', async () => {
    const callback = vi.fn().mockResolvedValue({ ok: true, mensaje: 'Producto agregado correctamente.' });
    renderSelector(producto, callback);
    elegir();
    fireEvent.change(screen.getByLabelText('Cantidad'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Agregar al carrito' }));
    expect(callback).toHaveBeenCalledWith(producto.variantes[0], 2);
    expect(await screen.findByRole('status')).toHaveTextContent('Producto agregado correctamente.');
    expect(screen.getByLabelText('Cantidad')).toHaveValue(1);
  });

  it('muestra el error devuelto por el callback', async () => {
    const callback = vi.fn().mockResolvedValue({ ok: false, mensaje: 'No hay stock suficiente.' });
    renderSelector(producto, callback);
    elegir();
    fireEvent.click(screen.getByRole('button', { name: 'Agregar al carrito' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No hay stock suficiente.');
  });

  it('muestra el estado de verificación mientras espera la respuesta', async () => {
    let resolver;
    const callback = vi.fn(() => new Promise((resolve) => { resolver = resolve; }));
    renderSelector(producto, callback);
    elegir();
    fireEvent.click(screen.getByRole('button', { name: 'Agregar al carrito' }));
    expect(screen.getByRole('button', { name: 'Verificando stock...' })).toBeDisabled();
    resolver({ ok: true, mensaje: 'Listo.' });
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Listo.'));
  });

  it('actualiza el stock cuando se emite carritoActualizado', async () => {
    renderSelector();
    elegir();

    expect(screen.getByText('Stock disponible: 5')).toBeInTheDocument();

    localStorage.setItem(
        'carrito_local',
        JSON.stringify([{ sku: 'POL-NEG-S', cantidad: 5 }])
    );

    window.dispatchEvent(new Event('carritoActualizado'));

    expect(
        await screen.findByText(
        'Agotado (ya tienes las 5 unidades disponibles en tu carrito)'
        )
    ).toBeInTheDocument();

    expect(
        screen.getByRole('button', { name: 'Agotado (en tu carrito)' })
    ).toBeDisabled();
  });

  it('tolera un carrito local con JSON inválido', () => {
    localStorage.setItem('carrito_local', '{esto no es json');
    renderSelector();
    elegir();
    expect(screen.getByText('Stock disponible: 5')).toBeInTheDocument();
  });

  it('reinicia la selección al cambiar de producto', () => {
    const { rerender } = render(
        <VariantSelector
        producto={producto}
        onAgregarAlCarrito={vi.fn()}
        />
    );

    elegir('Negro', 'S');

    expect(screen.getByText('SKU: POL-NEG-S')).toBeInTheDocument();

    const otro = {
        id: 2,
        variantes: [
        {
            sku: 'POL-ROJ-S',
            atributos_variables: { color: 'Rojo' },
            precio: 18000,
            stock: 2,
        },
        ],
    };

    rerender(
        <VariantSelector
        producto={otro}
        onAgregarAlCarrito={vi.fn()}
        />
    );

    expect(screen.queryByText('SKU: POL-NEG-S'))
        .not.toBeInTheDocument();

    expect(screen.queryByText('SKU: POL-ROJ-S'))
        .not.toBeInTheDocument();

    expect(
        screen.getByRole('button', { name: 'Agotado', exact: true })
    ).toBeDisabled();

    expect(screen.getByRole('heading', { name: 'color' }))
        .toBeInTheDocument();
  });
});
