import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Catalogo from '../pages/Catalogo';
import clienteAxios from '../components/auth/axiosConfig';

vi.mock('../components/auth/axiosConfig', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('../components/header/header', () => ({
  default: () => <header>Encabezado</header>,
}));

vi.mock('../components/ProductCardGrid', () => ({
  default: ({ producto }) => (
    <article>
      <h3>{producto.nombre}</h3>
      <span>{producto.categoria}</span>
      <button
        onClick={() => {}}
        aria-label={`Ver ${producto.nombre}`}
      >
        Ver producto
      </button>
    </article>
  ),
}));

vi.mock('../components/ProductCardList', () => ({
  default: ({ producto }) => (
    <article>
      <h3>{producto.nombre}</h3>
      <span>{producto.categoria}</span>
    </article>
  ),
}));

vi.mock('../components/VariantSelector', () => ({
  default: ({ producto }) => (
    <div>Selector de variantes: {producto.nombre}</div>
  ),
}));


const productosEjemplo = [
  {
    id: '1',
    nombre: 'Teclado mecánico',
    categoria: 'Periféricos',
    activo: true,
    publicado: true,
    atributos_globales: { color: 'Negro', conexion: 'USB' },
  },
  {
    id: '2',
    nombre: 'Mouse gamer',
    categoria: 'Periféricos',
    activo: true,
    publicado: true,
    atributos_globales: { color: 'Negro', conexion: 'USB' },
  },
  {
    id: '3',
    nombre: 'Monitor de prueba',
    categoria: 'Monitores',
    activo: true,
    publicado: false,
    atributos_globales: { color: 'Blanco' },
  },
  {
    id: '4',
    nombre: 'Producto inactivo',
    categoria: 'Periféricos',
    activo: false,
    publicado: true,
    atributos_globales: { color: 'Rojo' },
  },
  {
    id: '5',
    nombre: 'Monitor publicado',
    categoria: 'Monitores',
    activo: true,
    publicado: true,
    atributos_globales: { color: 'Blanco' },
  },
  {
    id: '6',
    nombre: 'Teclado rojo',
    categoria: 'Periféricos',
    activo: true,
    publicado: true,
    atributos_globales: { color: 'Rojo', conexion: 'USB' },
  },
];


function configurarRespuestas({
  configuracion = { tema_seleccionado: 1, layout_catalogo: 'GRID_3' },
  productos = productosEjemplo,
  filtros = {
    categorias: ['Periféricos', 'Monitores'],
    atributos: {
      Periféricos: { color: ['Negro', 'Blanco'], conexion: ['USB', 'Bluetooth'] },
      Monitores: { resolucion: ['4K'] },
    },
  },
  paginacion = null,
} = {}) {
  clienteAxios.get.mockImplementation((url) => {
    if (url === 'configuracion/') {
      return Promise.resolve({ data: configuracion });
    }

    if (url === 'catalogo/filtros/') {
      return Promise.resolve({ data: filtros });
    }

    if (url === 'catalogo/productos/') {
      if (paginacion) {
        return Promise.resolve({
          data: {
            count: paginacion.count ?? productos.length,
            total_pages: paginacion.total_pages ?? 2,
            current_page: paginacion.current_page ?? 1,
            page_size: 24,
            results: productos,
            filtros,
          },
        });
      }
      return Promise.resolve({ data: productos });
    }

    return Promise.reject(new Error(`URL no esperada: ${url}`));
  });
}

function renderCatalogo() {
  return render(
    <MemoryRouter>
      <Catalogo />
    </MemoryRouter>
  );
}

afterEach(() => {
  cleanup();
});

describe('Catalogo', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.style.cssText = '';
    vi.clearAllMocks();
    configurarRespuestas();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('muestra el título del catálogo', () => {
    renderCatalogo();

    expect(
      screen.getByRole('heading', { name: 'Catálogo' })
    ).toBeInTheDocument();
  });

  it('muestra solo los productos publicados y activos', async () => {
    renderCatalogo();

    expect(await screen.findByText('Teclado mecánico')).toBeInTheDocument();
    expect(screen.getByText('Mouse gamer')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.queryByText('Monitor de prueba')).not.toBeInTheDocument();
      expect(screen.queryByText('Producto inactivo')).not.toBeInTheDocument();
    });
  });

  it('mientras carga muestra tarjetas vacías, no "0 productos" ni "No hay productos"', async () => {
    renderCatalogo();

    expect(screen.getByRole('status')).toHaveTextContent('Cargando productos...');
    expect(screen.queryByText('No hay productos para mostrar.')).not.toBeInTheDocument();
    expect(document.querySelectorAll('.tarjeta-producto .esqueleto').length).toBeGreaterThan(0);

    expect(await screen.findByText('Teclado mecánico')).toBeInTheDocument();
    expect(document.querySelector('.esqueleto')).toBeNull();
  });

  it('muestra el mensaje cuando no hay productos publicados', async () => {
    configurarRespuestas({ productos: [] });

    renderCatalogo();

    expect(
      await screen.findByText('No hay productos para mostrar.')
    ).toBeInTheDocument();
  });

  it('muestra el mensaje si la respuesta de productos no es un arreglo', async () => {
    configurarRespuestas({ productos: null });

    renderCatalogo();

    expect(
      await screen.findByText('No hay productos para mostrar.')
    ).toBeInTheDocument();
  });

  //Aca esta el error 1 (solucionado)
  it('filtra los productos por categoría', async () => {
    renderCatalogo();

    // 1. Validamos el estado inicial (todo visible)
    expect(await screen.findByText('Monitor publicado')).toBeInTheDocument();
    expect(screen.getByText('Teclado mecánico')).toBeInTheDocument();

    // 2. Cambiamos la categoría a 'Monitores'
    fireEvent.change(screen.getByLabelText('Categoría'), {
        target: { value: 'Monitores' },
    });

    // CORRECCIÓN: Esperamos ver el monitor en pantalla tras el filtrado
    expect(await screen.findByText('Monitor publicado')).toBeInTheDocument();

    // 3. Nos aseguramos de que los periféricos SÍ hayan desaparecido
    expect(screen.queryByText('Teclado mecánico')).not.toBeInTheDocument();
    expect(screen.queryByText('Teclado rojo')).not.toBeInTheDocument();

    // Opcional: Validamos que NO salga el cartel de vacío
    expect(screen.queryByText('No hay productos para mostrar.')).not.toBeInTheDocument();
  });

  //Aca esta el error 2 (solucionado)
  it('filtra por un atributo dinámico', async () => {
    renderCatalogo();

    // 1. En el estado inicial, AMBOS teclados están presentes (asumiendo que muestra todo)
    expect(await screen.findByText('Teclado rojo')).toBeInTheDocument();
    expect(await screen.findByText('Teclado mecánico')).toBeInTheDocument(); // <-- CAMBIO AQUÍ (Si es que aparece al inicio)

    // 2. Cambiamos la categoría (por ejemplo, a 'Periféricos')
    fireEvent.change(screen.getByLabelText('Categoría'), {
        target: { value: 'Periféricos' },
    });

    // 3. Esperamos el filtro dinámico
    const filtroColor = await screen.findByLabelText('color');

    // 4. Cambiamos el color a 'Negro'
    fireEvent.change(filtroColor, {
        target: { value: 'Negro' },
    });

    // Verificamos que se mantengan o aparezcan los negros
    expect(await screen.findByText('Teclado mecánico')).toBeInTheDocument();
    expect(await screen.findByText('Mouse gamer')).toBeInTheDocument();

    // CORRECCIÓN: Aquí es donde el 'Teclado rojo' debería desaparecer
    expect(screen.queryByText('Teclado rojo')).not.toBeInTheDocument();

    // 5. Cambiamos el color a 'Rojo'
    fireEvent.change(filtroColor, {
        target: { value: 'Rojo' },
    });

    // CORRECCIÓN: Ahora esperamos ver el Teclado rojo en pantalla
    expect(await screen.findByText('Teclado rojo')).toBeInTheDocument();

    // Aseguramos que los de color negro que vimos antes SÍ hayan desaparecido por completo
    expect(screen.queryByText('Teclado mecánico')).not.toBeInTheDocument();
    expect(screen.queryByText('Mouse gamer')).not.toBeInTheDocument();
    expect(screen.queryByText('No hay productos para mostrar.')).not.toBeInTheDocument();
  });
  //

  it('usa el diseño de lista cuando la configuración lo indica', async () => {
    configurarRespuestas({
      configuracion: {
        tema_seleccionado: 1,
        layout_catalogo: 'LISTA',
      },
    });

    renderCatalogo();

    expect(await screen.findByText('Teclado mecánico')).toBeInTheDocument();

    expect(
      screen.queryByRole('button', { name: 'Ver Teclado mecánico' })
    ).not.toBeInTheDocument();
  });

  it('consulta la configuración y los productos', async () => {
    renderCatalogo();

    await screen.findByText('Teclado mecánico');

    expect(clienteAxios.get).toHaveBeenCalledWith(
      'configuracion/'
    );

    expect(clienteAxios.get).toHaveBeenCalledWith(
      'catalogo/productos/',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('registra un error si falla la carga de productos', async () => {
    const error = new Error('Error de conexión');
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    clienteAxios.get.mockImplementation((url) => {
      if (url === 'configuracion/') {
        return Promise.resolve({ data: { tema_seleccionado: 1 } });
      }

      return Promise.reject(error);
    });

    renderCatalogo();

    expect(
      await screen.findByText('No hay productos para mostrar.')
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'No se pudo cargar el catálogo:',
        error
      );
    });
  });

  it('guarda en localStorage el tema recibido del backend', async () => {
    configurarRespuestas({
      configuracion: {
        tema_seleccionado: 2,
        layout_catalogo: 'GRID_4',
      },
    });

    renderCatalogo();

    await waitFor(() => {
      expect(localStorage.getItem('ecommerce_palette')).toBe('2');
    });
  });

  it('muestra controles de paginación accesibles y permite cambiar de página (SCRUM-179)', async () => {
    configurarRespuestas({
      paginacion: {
        count: 48,
        total_pages: 2,
        current_page: 1,
      },
    });

    renderCatalogo();

    const paginacionNav = await screen.findByRole('navigation', { name: 'Paginación del catálogo' });
    expect(paginacionNav).toBeInTheDocument();

    const btnAnterior = screen.getByRole('button', { name: 'Página anterior' });
    const btnSiguiente = screen.getByRole('button', { name: 'Página siguiente' });
    const btnPagina1 = screen.getByRole('button', { name: 'Página 1' });
    const btnPagina2 = screen.getByRole('button', { name: 'Página 2' });

    expect(btnAnterior).toBeDisabled();
    expect(btnSiguiente).not.toBeDisabled();
    expect(btnPagina1).toHaveAttribute('aria-current', 'page');
    expect(btnPagina2).not.toHaveAttribute('aria-current');

    // Navegar a la página 2
    fireEvent.click(btnPagina2);

    await waitFor(() => {
      expect(clienteAxios.get).toHaveBeenCalledWith(
        'catalogo/productos/',
        expect.objectContaining({
          params: expect.objectContaining({ page: 2 }),
        })
      );
    });
  });

  it('usa las opciones globales de la página sin una petición separada de filtros (SCRUM-149)', async () => {
    configurarRespuestas({ paginacion: { count: 48, total_pages: 2 } });
    await renderCatalogo();
    await screen.findByText('Teclado mecánico');
    fireEvent.change(screen.getByLabelText('Categoría'), { target: { value: 'Periféricos' } });
    expect(await screen.findByRole('option', { name: 'Bluetooth' })).toBeInTheDocument();
    expect(clienteAxios.get.mock.calls.some(([url]) => url === 'catalogo/filtros/')).toBe(false);
  });

  it('reinicia a la página 1 cuando cambia la categoría o el orden (SCRUM-179)', async () => {
    configurarRespuestas({
      paginacion: {
        count: 48,
        total_pages: 2,
        current_page: 1,
      },
    });

    renderCatalogo();

    const selectCategoria = await screen.findByLabelText('Categoría');
    fireEvent.change(selectCategoria, { target: { value: 'Periféricos' } });

    await waitFor(() => {
      expect(clienteAxios.get).toHaveBeenCalledWith(
        'catalogo/productos/',
        expect.objectContaining({
          params: expect.objectContaining({ page: 1, categoria: 'Periféricos' }),
        })
      );
    });
  });

  it('muestra elipsis en la paginación cuando hay muchas páginas (ej. 10 páginas)', async () => {
    configurarRespuestas({
      paginacion: {
        count: 240,
        total_pages: 10,
        current_page: 1,
      },
    });

    renderCatalogo();

    const paginacionNav = await screen.findByRole('navigation', { name: 'Paginación del catálogo' });
    expect(paginacionNav).toBeInTheDocument();

    // Deben existir páginas iniciales y la última página 10
    expect(screen.getByRole('button', { name: 'Página 1' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Página 2' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Página 10' })).toBeInTheDocument();
    // La elipsis debe existir como elemento decorativo
    expect(document.querySelector('.catalogo-paginacion__elipsis')).toBeInTheDocument();
  });

  it('el selector de colecciones NO debe aparecer si la lista de colecciones está vacía', async () => {
    configurarRespuestas({
      results: [
        { id: 1, nombre: 'Teclado mecánico', categoria: 'Electronica', activo: true, publicado: true }
      ],
      total_pages: 1,
      count: 1,
      filtros: {
        categorias: ['Electronica'],
        colecciones: []
      }
    });

    renderCatalogo();

    await waitFor(() => {
      const selector = screen.queryByTestId('selector-colecciones');
      expect(selector).not.toBeInTheDocument();
    });
  });

  it('el selector de colecciones SÍ debe aparecer cuando hay colecciones vigentes', async () => {
    
    clienteAxios.get.mockImplementation((url) => {
      if (typeof url === 'string' && url.includes('catalogo/productos')) {
        return Promise.resolve({
          data: {
            results: [
              { id: 1, nombre: 'Teclado mecánico', categoria: 'Electronica', activo: true, publicado: true }
            ],
            total_pages: 1,
            count: 1,
            filtros: {
              categorias: ['Electronica'],
              colecciones: ['Cyber', 'Verano']
            }
          }
        });
      }
      
      return Promise.resolve({ data: {} });
    });

    renderCatalogo();

    const selector = await screen.findByTestId('selector-colecciones');
    expect(selector).toBeInTheDocument();
  });
});
