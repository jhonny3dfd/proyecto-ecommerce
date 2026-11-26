import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor,} from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const { getMock, validarMock, guardarMock, headerMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  validarMock: vi.fn(),
  guardarMock: vi.fn(),
  headerMock: vi.fn(),
}));

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: getMock,
  },
}));

vi.mock('../components/header/header', () => ({
  default: () => <header>Header de prueba</header>,
}));

vi.mock('../components/carrito', () => ({
  validarCarrito: validarMock,
  guardarCarrito: guardarMock,
}));

vi.mock('../utils/precios', () => ({
  obtenerDatosPrecioYStock: vi.fn((variantes) => {
    const disponibles = (variantes || []).filter(
      (variante) => Number(variante.stock) > 0,
    );

    if (disponibles.length === 0) {
      return {
        agotado: true,
        textoPrecio: '',
        precioTachado: '',
        tieneOferta: false,
      };
    }

    const precios = disponibles.map((variante) =>
      Number(
        variante.precio_oferta > 0 &&
          Number(variante.precio_oferta) < Number(variante.precio)
          ? variante.precio_oferta
          : variante.precio,
      ),
    );

    return {
      agotado: false,
      textoPrecio: `$${Math.min(...precios).toLocaleString('es-CL')}`,
      precioTachado: '',
      tieneOferta: false,
    };
  }),
}));

// El selector real se prueba en sus propios tests.
// Aquí simulamos su integración con DetalleProducto.
vi.mock('../components/VariantSelector', () => ({
  default: ({ producto, onAgregarAlCarrito }) => (
    <div data-testid="selector-variantes">
      <span>Selector de {producto.nombre}</span>
      <button
        type="button"
        onClick={async () => {
          const resultado = await onAgregarAlCarrito(
            producto.variantes[0],
            1,
          );
          headerMock(resultado);
        }}
      >
        Probar agregar al carrito
      </button>
    </div>
  ),
}));

import DetalleProducto from '../pages/DetalleProducto';

const productoEjemplo = {
  id: 'producto-1',
  nombre: 'Polera Ecode',
  categoria: 'Ropa',
  descripcion: 'Polera de algodón',
  imagenes: ['/polera-1.jpg', '/polera-2.jpg', '/polera-3.jpg'],
  atributos_globales: {
    material: 'Algodón',
    origen: 'Chile',
  },
  meta_titulo: 'Polera Ecode SEO',
  meta_descripcion: 'Descripción SEO de la polera',
  variantes: [
    {
      sku: 'POL-001',
      precio: 15000,
      precio_oferta: 12000,
      stock: 5,
      atributos_variables: { talla: 'M' },
    },
  ],
};

function renderDetalle(id = 'producto-1') {
  return render(
    <MemoryRouter initialEntries={[`/producto/${id}`]}>
      <Routes>
        <Route path="/producto/:id" element={<DetalleProducto />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('DetalleProducto', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    getMock.mockResolvedValue({
      data: structuredClone(productoEjemplo),
    });

    validarMock.mockResolvedValue({
      items: [
        {
          disponible: 4,
          problema: false,
          precio: 12000,
        },
      ],
    });

    guardarMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    document.title = '';
    document
      .querySelector('meta[name="description"]')
      ?.remove();
  });

  it('muestra la etiqueta propia en la ficha', async () => {
    getMock.mockResolvedValue({ data: { ...productoEjemplo, etiqueta: 'Edición limitada', etiqueta_color: 'accent' } });
    renderDetalle();
    expect(await screen.findByText('Edición limitada')).toHaveClass('tarjeta-producto-etiqueta--accent');
  });

  it('en la ficha sustituye la etiqueta por Agotado cuando no hay stock', async () => {
    getMock.mockResolvedValue({ data: { ...productoEjemplo, etiqueta: 'Últimas unidades',
      variantes: [{ sku: 'SIN-STOCK', precio: 10000, stock: 0 }] } });
    renderDetalle();
    expect(await screen.findByText('Agotado')).toBeInTheDocument();
    expect(screen.queryByText('Últimas unidades')).not.toBeInTheDocument();
  });

  it('la colección privada muestra su etiqueta en la ficha sin Agotado', async () => {
    getMock.mockResolvedValue({ data: { ...productoEjemplo, etiqueta: 'Obra única', coleccion_privada: true,
      variantes: [] } });
    renderDetalle();
    expect(await screen.findByText('Obra única')).toBeInTheDocument();
    expect(screen.queryByText('Agotado')).not.toBeInTheDocument();
  });

  it('muestra el estado de carga inicialmente', () => {
    getMock.mockReturnValue(new Promise(() => {}));

    renderDetalle();

    expect(screen.getByRole('status')).toHaveTextContent(
      'Cargando producto...',
    );
  });

  it('solicita el producto usando el id de la URL', async () => {
    renderDetalle('producto-25');

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    expect(getMock).toHaveBeenCalledWith(
      'catalogo/productos/producto-25/',
    );
  });

  it('muestra el nombre, categoría y descripción', async () => {
    renderDetalle();

    expect(
      await screen.findByRole('heading', { name: 'Polera Ecode' }),
    ).toBeInTheDocument();

    // "Ropa" aparece en la navegación y en la categoría.
    expect(screen.getAllByText('Ropa')).toHaveLength(2);
    expect(screen.getByText('Polera de algodón')).toBeInTheDocument();
  });

  it('muestra un enlace para volver al catálogo si falla la petición', async () => {
    getMock.mockRejectedValue(new Error('Error de red'));

    renderDetalle();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo encontrar el producto.',
    );

    expect(
      screen.getByRole('link', { name: /volver al catálogo/i }),
    ).toHaveAttribute('href', '/catalogo');
  });

  it('actualiza el título y la descripción SEO', async () => {
    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    await waitFor(() => {
      expect(document.title).toBe('Polera Ecode SEO');
      expect(
        document.querySelector('meta[name="description"]')?.content,
      ).toBe('Descripción SEO de la polera');
    });
  });

  it('usa el nombre y descripción del producto si no hay metadatos SEO', async () => {
    getMock.mockResolvedValue({
      data: {
        ...structuredClone(productoEjemplo),
        meta_titulo: ' ',
        meta_descripcion: '',
      },
    });

    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    await waitFor(() => {
      expect(document.title).toBe('Polera Ecode');
      expect(
        document.querySelector('meta[name="description"]')?.content,
      ).toBe('Polera de algodón');
    });
  });

  it('muestra la imagen principal y las miniaturas', async () => {
    renderDetalle();

    const imagen = await screen.findByRole('img', {
      name: 'Polera Ecode, imagen 1 de 3',
    });

    expect(imagen).toHaveAttribute('src', '/polera-1.jpg');

    expect(
      screen.getByRole('button', { name: 'Ver imagen 2' }),
    ).toBeInTheDocument();
  });

  it('avanza a la siguiente imagen', async () => {
    renderDetalle();

    await screen.findByRole('img', {
      name: 'Polera Ecode, imagen 1 de 3',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Imagen siguiente' }));

    expect(
      screen.getByRole('img', { name: 'Polera Ecode, imagen 2 de 3' }),
    ).toHaveAttribute('src', '/polera-2.jpg');
  });

  it('vuelve a la última imagen al retroceder desde la primera', async () => {
    renderDetalle();

    await screen.findByRole('img', {
      name: 'Polera Ecode, imagen 1 de 3',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Imagen anterior' }));

    expect(
      screen.getByRole('img', { name: 'Polera Ecode, imagen 3 de 3' }),
    ).toHaveAttribute('src', '/polera-3.jpg');
  });

  it('permite seleccionar una imagen mediante su miniatura', async () => {
    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    fireEvent.click(screen.getByRole('button', { name: 'Ver imagen 2' }));

    expect(
      screen.getByRole('img', { name: 'Polera Ecode, imagen 2 de 3' }),
    ).toHaveAttribute('src', '/polera-2.jpg');

    expect(
      screen.getByRole('button', { name: 'Ver imagen 2' }),
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('muestra una alternativa cuando el producto no tiene imágenes', async () => {
    getMock.mockResolvedValue({
      data: {
        ...structuredClone(productoEjemplo),
        imagenes: [],
      },
    });

    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    expect(screen.getByText('Sin imagen disponible')).toBeInTheDocument();
  });

  it('muestra los atributos globales de la ficha técnica', async () => {
    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    expect(screen.getByText('material')).toBeInTheDocument();
    expect(screen.getByText('Algodón')).toBeInTheDocument();
    expect(screen.getByText('Chile')).toBeInTheDocument();
  });

  it('muestra el selector de variantes del producto', async () => {
    renderDetalle();

    expect(
      await screen.findByTestId('selector-variantes'),
    ).toHaveTextContent('Selector de Polera Ecode');
  });

  it('muestra un precio para un producto con stock', async () => {
    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    expect(screen.getByText('$12.000')).toBeInTheDocument();
  });

  it('muestra el estado sin stock cuando todas las variantes están agotadas', async () => {
    getMock.mockResolvedValue({
      data: {
        ...structuredClone(productoEjemplo),
        variantes: [
          {
            ...productoEjemplo.variantes[0],
            stock: 0,
          },
        ],
      },
    });

    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    expect(screen.getByText('Sin stock')).toBeInTheDocument();
  });

  it('agrega al carrito cuando la validación de stock es correcta', async () => {
    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    fireEvent.click(
      screen.getByRole('button', { name: 'Probar agregar al carrito' }),
    );

    await waitFor(() => {
      expect(validarMock).toHaveBeenCalledTimes(1);
      expect(guardarMock).toHaveBeenCalledTimes(1);
    });

    expect(guardarMock).toHaveBeenCalledWith([
      expect.objectContaining({
        id: 'producto-1',
        sku: 'POL-001',
        cantidad: 1,
        precio: 12000,
      }),
    ]);

    expect(headerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        ok: true,
        mensaje: expect.stringContaining('Agregaste 1'),
      }),
    );
  });

  it('muestra un error cuando falla la validación del stock', async () => {
    validarMock.mockRejectedValue(new Error('Sin conexión'));

    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    renderDetalle();

    await screen.findByRole('heading', { name: 'Polera Ecode' });

    fireEvent.click(
      screen.getByRole('button', { name: 'Probar agregar al carrito' }),
    );

    await waitFor(() => {
      expect(headerMock).toHaveBeenCalledWith({
        ok: false,
        mensaje: 'No pudimos verificar el stock. Intenta nuevamente.',
      });
    });

    expect(guardarMock).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });

  describe('Colección privada (SCRUM-197)', () => {
    it('muestra "Colección privada", no muestra "Sin stock" ni el selector de variantes', async () => {
      getMock.mockResolvedValueOnce({
        data: {
          id: 'obra-privada-1',
          nombre: 'Escultura Singular',
          categoria: 'Escultura',
          descripcion: 'Pieza exclusiva.',
          coleccion_privada: true,
          version_a_la_venta: null,
          version_a_la_venta_disponible: false,
          variantes: [{ sku: 'ESC-01', precio: 800000, stock: 0 }],
        },
      });

      renderDetalle();

      await screen.findByRole('heading', { name: 'Escultura Singular' });

      expect(screen.getByText('Colección privada')).toBeInTheDocument();
      expect(screen.queryByText('Sin stock')).not.toBeInTheDocument();
      expect(screen.queryByText('Agotado')).not.toBeInTheDocument();
      expect(screen.queryByTestId('selector-variantes')).not.toBeInTheDocument();
    });

    it('muestra enlace a la versión a la venta cuando está disponible', async () => {
      getMock.mockResolvedValueOnce({
        data: {
          id: 'obra-privada-1',
          nombre: 'Escultura Singular',
          categoria: 'Escultura',
          descripcion: 'Pieza exclusiva.',
          coleccion_privada: true,
          version_a_la_venta: 'replica-print-1',
          version_a_la_venta_disponible: true,
          texto_boton_version: 'Comprar réplica 3D',
          variantes: [{ sku: 'ESC-01', precio: 800000, stock: 0 }],
        },
      });

      renderDetalle();

      await screen.findByRole('heading', { name: 'Escultura Singular' });

      const enlaceVersion = screen.getByRole('link', { name: 'Comprar réplica 3D' });
      expect(enlaceVersion).toBeInTheDocument();
      expect(enlaceVersion).toHaveAttribute('href', '/catalogo/producto/replica-print-1');
    });

    it('oculta el botón si la versión a la venta está despublicada o no disponible', async () => {
      getMock.mockResolvedValueOnce({
        data: {
          id: 'obra-privada-1',
          nombre: 'Escultura Singular',
          categoria: 'Escultura',
          descripcion: 'Pieza exclusiva.',
          coleccion_privada: true,
          version_a_la_venta: 'replica-print-1',
          version_a_la_venta_disponible: false,
          texto_boton_version: 'Comprar réplica 3D',
          variantes: [{ sku: 'ESC-01', precio: 800000, stock: 0 }],
        },
      });

      renderDetalle();

      await screen.findByRole('heading', { name: 'Escultura Singular' });

      expect(screen.queryByRole('link', { name: 'Comprar réplica 3D' })).not.toBeInTheDocument();
      expect(screen.queryByTestId('selector-variantes')).not.toBeInTheDocument();
    });
  });
});

// Video de YouTube opcional del producto (pedido de Alan): va al final de la galería
describe('DetalleProducto con video de YouTube', () => {
  const conVideo = (cambios = {}) => getMock.mockResolvedValue({
    data: { ...structuredClone(productoEjemplo), youtube_id: 'dQw4w9WgXcQ', ...cambios },
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => { cleanup(); document.title = ''; });

  it('sin video la galería sigue igual', async () => {
    getMock.mockResolvedValue({ data: structuredClone(productoEjemplo) });
    renderDetalle();
    await screen.findByRole('img', { name: 'Polera Ecode, imagen 1 de 3' });
    expect(screen.queryByRole('button', { name: 'Ver video' })).not.toBeInTheDocument();
    expect(screen.getByText('1 / 3')).toBeInTheDocument();
  });

  it('el video es la última miniatura y no se conecta a YouTube hasta reproducirlo', async () => {
    conVideo();
    const { container } = renderDetalle();
    await screen.findByText('1 / 4');

    const miniaturas = screen.getAllByRole('button', { name: /^Ver (imagen|video)/ });
    expect(miniaturas.map((boton) => boton.getAttribute('aria-label')))
      .toEqual(['Ver imagen 1', 'Ver imagen 2', 'Ver imagen 3', 'Ver video']);

    fireEvent.click(screen.getByRole('button', { name: 'Ver video' }));
    expect(screen.getByRole('button', { name: 'Ver video' })).toHaveAttribute('aria-pressed', 'true');
    // Sin aceptar las cookies de marketing: la portada es la primera foto y no hay nada de YouTube en la página
    expect(container.querySelector('.video-youtube-miniatura')).toHaveAttribute('src', '/polera-1.jpg');
    expect(container.innerHTML).not.toMatch(/ytimg\.com|youtube(-nocookie)?\.com/);
    // Sobre el video, el contador taparía los controles del reproductor
    expect(screen.queryByText(/\/ 4/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Reproducir video: Polera Ecode' }));
    const reproductor = screen.getByTitle('Reproductor de video: Polera Ecode');
    expect(reproductor).toHaveAttribute('src', 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1');
  });

  it('las flechas recorren las fotos y el video en círculo, y al cambiar de foto el video se detiene', async () => {
    conVideo();
    renderDetalle();
    await screen.findByText('1 / 4');

    fireEvent.click(screen.getByRole('button', { name: 'Imagen anterior' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reproducir video: Polera Ecode' }));
    expect(screen.getByTitle('Reproductor de video: Polera Ecode')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Imagen siguiente' }));
    expect(screen.getByRole('img', { name: 'Polera Ecode, imagen 1 de 3' })).toBeInTheDocument();
    expect(screen.queryByTitle('Reproductor de video: Polera Ecode')).not.toBeInTheDocument();

    // Al volver, el video espera otro clic: no parte solo
    fireEvent.click(screen.getByRole('button', { name: 'Ver video' }));
    expect(screen.getByRole('button', { name: 'Reproducir video: Polera Ecode' })).toBeInTheDocument();
  });

  it('un producto sin fotos muestra solo el video', async () => {
    conVideo({ imagenes: [] });
    const { container } = renderDetalle();
    await screen.findByRole('heading', { name: 'Polera Ecode' });

    expect(screen.getByRole('button', { name: 'Reproducir video: Polera Ecode' })).toBeInTheDocument();
    expect(container.querySelector('.video-youtube-miniatura--neutra')).toBeInTheDocument();
    expect(screen.queryByText('Sin imagen disponible')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Imagen siguiente' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ver video' })).not.toBeInTheDocument();
  });
});
