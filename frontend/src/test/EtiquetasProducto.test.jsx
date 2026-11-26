import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TarjetaProducto from '../components/TarjetaProducto';
import ProductCardList from '../components/ProductCardList';
import EtiquetaProducto from '../components/EtiquetaProducto';
import SeccionDestacados from '../components/landing/SeccionDestacados';
import { COLORES_ETIQUETA_PRODUCTO } from '../utils/etiquetasProducto';
import { PALETTES } from '../constants/palettes';

const base = { id: 'obra-198', nombre: 'Obra', categoria: 'Arte',
  variantes: [{ sku: '198', precio: 10000, stock: 2, precio_oferta: 8000 }] };

afterEach(cleanup);

describe.each([
  ['tarjeta de landing y grilla', producto => <TarjetaProducto producto={producto} etiqueta="Nuevo" />],
  ['fila del catálogo', producto => <ProductCardList producto={producto} />],
  ['destacado de la landing', producto => <SeccionDestacados destacados={[
    { ...producto, tipo: 'PRODUCTO', enlace: '/catalogo/producto/obra-198' },
  ]} />],
])('Etiquetas en %s', (_nombre, crear) => {
  function mostrar(cambios) {
    return render(<MemoryRouter>{crear({ ...base, ...cambios })}</MemoryRouter>);
  }

  it('la etiqueta propia prevalece sobre la oferta y la sección', () => {
    const { container } = mostrar({ etiqueta: 'Últimas unidades', etiqueta_color: 'accent' });
    const etiquetas = container.querySelectorAll('.tarjeta-producto-etiqueta');
    expect(etiquetas).toHaveLength(1);
    expect(etiquetas[0]).toHaveTextContent('Últimas unidades');
    expect(etiquetas[0]).toHaveClass('tarjeta-producto-etiqueta--accent');
    expect(screen.queryByText('Oferta')).not.toBeInTheDocument();
    expect(screen.queryByText('Nuevo')).not.toBeInTheDocument();
  });

  it('Agotado prevalece sobre la etiqueta propia', () => {
    mostrar({ etiqueta: 'Edición limitada', variantes: [{ precio: 10000, stock: 0, precio_oferta: 8000 }] });
    expect(screen.getByText('Agotado')).toHaveClass('tarjeta-producto-etiqueta--agotado');
    expect(screen.queryByText('Edición limitada')).not.toBeInTheDocument();
  });

  it('la colección privada conserva su etiqueta incluso sin variantes', () => {
    mostrar({ etiqueta: 'Original', etiqueta_color: 'secondary', coleccion_privada: true, variantes: [] });
    expect(screen.getByText('Original')).toHaveClass('tarjeta-producto-etiqueta--secondary');
    expect(screen.getByText('Original')).not.toHaveClass('tarjeta-producto-etiqueta--agotado');
    expect(screen.queryByText('Agotado')).not.toBeInTheDocument();
  });

  it('sin etiqueta propia conserva la oferta existente', () => {
    mostrar({ etiqueta: '   ' });
    expect(screen.getByText('Oferta')).toBeInTheDocument();
  });

  it('la etiqueta se presenta como texto, sin interpretar HTML', () => {
    const { container } = mostrar({ etiqueta: '<b>Único</b>' });
    expect(screen.getByText('<b>Único</b>')).toBeInTheDocument();
    expect(container.querySelector('.tarjeta-producto-etiqueta b')).toBeNull();
  });
});

describe('Regresiones de etiquetas', () => {
  it('sin etiqueta ni oferta mantiene Nuevo en la sección de últimos agregados', () => {
    render(<MemoryRouter><TarjetaProducto producto={{ ...base, variantes: [{ precio: 10000, stock: 2 }] }}
      etiqueta="Nuevo" /></MemoryRouter>);
    expect(screen.getByText('Nuevo')).toBeInTheDocument();
  });

  it('muestra la etiqueta junto al enlace de print de la colección privada en lista', () => {
    render(<MemoryRouter><ProductCardList producto={{ ...base, coleccion_privada: true,
      etiqueta: 'Original', version_a_la_venta: 'print-1', version_a_la_venta_disponible: true }} /></MemoryRouter>);
    expect(screen.getByText('Original')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Disponible en print' })).toHaveAttribute('href', '/catalogo/producto/print-1');
  });

  it('la ficha sin etiqueta conserva la presentación anterior', () => {
    const { container } = render(<EtiquetaProducto producto={base} enFicha />);
    expect(container).toBeEmptyDOMElement();
  });

  it('un color ausente o desconocido usa la pareja principal', () => {
    render(<EtiquetaProducto producto={{ ...base, etiqueta: 'Único', etiqueta_color: '#ff0000' }} />);
    expect(screen.getByText('Único')).toHaveClass('tarjeta-producto-etiqueta--primary');
  });
});

// Fórmula de luminancia relativa de WCAG; también se verifican los estilos calculados en navegador.
function luminancia(hex) {
  const canales = hex.match(/[a-f\d]{2}/gi).map(v => parseInt(v, 16) / 255)
    .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return canales[0] * 0.2126 + canales[1] * 0.7152 + canales[2] * 0.0722;
}

describe('Contraste AA de las parejas de colores', () => {
  it.each(PALETTES)('todos los colores de etiqueta superan 4.5:1 en $name', paleta => {
    for (const opcion of COLORES_ETIQUETA_PRODUCTO) {
      const fondo = luminancia(paleta.colors[opcion.fondo]);
      const texto = luminancia(paleta.colors[opcion.texto]);
      expect((Math.max(fondo, texto) + 0.05) / (Math.min(fondo, texto) + 0.05)).toBeGreaterThanOrEqual(4.5);
    }
  });
});
