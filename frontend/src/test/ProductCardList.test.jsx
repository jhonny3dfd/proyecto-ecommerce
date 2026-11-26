import { afterEach, describe, expect, it } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProductCardList from '../components/ProductCardList';

const producto = {
  id: 'zapatillas-1',
  nombre: 'Zapatillas Runner',
  categoria: 'Calzado',
  imagenes: [],
  variantes: [
    { sku: 'ZAP-35', precio: 49990, precio_oferta: 39990, stock: 3 },
    { sku: 'ZAP-36', precio: 49990, stock: 0 },
  ],
};

function renderTarjeta(datos = producto) {
  return render(
    <MemoryRouter>
      <ProductCardList producto={datos} />
    </MemoryRouter>
  );
}

describe('ProductCardList (layout de lista del catálogo)', () => {
  afterEach(() => cleanup());

  it('muestra el precio de oferta y el precio normal tachado', () => {
    renderTarjeta();

    expect(screen.getByRole('heading', { name: 'Zapatillas Runner' })).toBeInTheDocument();
    // Las variantes tienen precios distintos (39.990 en oferta y 49.990): se muestra el menor
    expect(screen.getByText('Desde $39.990')).toBeInTheDocument();
    // El precio normal va tachado como precio anterior (<del>)
    expect(screen.getByText('$49.990').closest('del')).not.toBeNull();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/catalogo/producto/zapatillas-1');
  });

  it('marca el producto como agotado cuando ninguna variante tiene stock', () => {
    renderTarjeta({ ...producto, variantes: [{ sku: 'ZAP-36', precio: 49990, stock: 0 }] });

    expect(screen.getAllByText('Agotado').length).toBeGreaterThan(0);
  });
});
