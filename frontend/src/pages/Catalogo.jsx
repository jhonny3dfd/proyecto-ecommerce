import { useEffect, useMemo, useState } from 'react';
import clienteAxios from '../components/auth/axiosConfig';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import { aplicarPaleta } from '../constants/palettes';
import Header from '../components/header/header';
import ProductCardGrid from '../components/ProductCardGrid';
import ProductCardList from '../components/ProductCardList';
import { precioMinimoVigente } from '../utils/precios';
import { EsqueletoTarjetas } from '../components/carga/EsqueletosTienda';
import BotonSubir from '../components/BotonSubir';
import '../components/TarjetaProducto.css';
import './Catalogo.css';

const TEMA_PREDETERMINADO = 1;

// Órdenes del catálogo; "Destacados" respeta el orden en que llegan del servidor
const ORDENES = {
  destacados: { etiqueta: 'Destacados', comparar: null },
  recientes: {
    etiqueta: 'Más nuevos',
    comparar: (a, b) => new Date(b.fecha_creacion || 0) - new Date(a.fecha_creacion || 0)
  },
  'precio-asc': {
    etiqueta: 'Precio: menor a mayor',
    comparar: (a, b) => precioMinimoVigente(a.variantes) - precioMinimoVigente(b.variantes)
  },
  'precio-desc': {
    etiqueta: 'Precio: mayor a menor',
    comparar: (a, b) => precioMinimoVigente(b.variantes) - precioMinimoVigente(a.variantes)
  },
  nombre: { etiqueta: 'Nombre (A-Z)', comparar: (a, b) => String(a.nombre).localeCompare(String(b.nombre), 'es') }
};

// RF-01.4: grilla de 3, grilla de 4 o lista con la descripción al costado
const CLASES_LAYOUT = { GRID_3: 'catalogo-grilla catalogo-grilla--3', GRID_4: 'catalogo-grilla', LISTA: 'catalogo-lista' };

function obtenerAtributos(producto) {
  const atributos = producto?.atributos_globales;
  return atributos && typeof atributos === 'object' && !Array.isArray(atributos)
    ? atributos
    : {};
}

function mostrarValor(valor) {
  return valor !== null && typeof valor === 'object'
    ? JSON.stringify(valor)
    : String(valor);
}

// Identifica una consulta al servidor: si la cargada no es la pedida, el catálogo aún está cargando
const claveConsulta = (pagina, categoria, coleccion, filtros, orden) => JSON.stringify([pagina, categoria, coleccion, filtros, orden]);

function calcularRangoPaginacion(paginaActual, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  if (paginaActual <= 4) {
    return [1, 2, 3, 4, 5, '...', total];
  }
  if (paginaActual >= total - 3) {
    return [1, '...', total - 4, total - 3, total - 2, total - 1, total];
  }
  return [1, '...', paginaActual - 1, paginaActual, paginaActual + 1, '...', total];
}

export default function Catalogo() {
  const configuracion = useConfiguracionTienda({ refrescar: true });
  const configuracionDisponible = Boolean(configuracion);
  const temaConfigurado = Number(configuracion?.tema_seleccionado)
    || Number(localStorage.getItem('ecommerce_palette')) || TEMA_PREDETERMINADO;

  const [productos, setProductos] = useState([]);
  const [categoriaSeleccionada, setCategoriaSeleccionada] = useState('');
  const [coleccionSeleccionada, setColeccionSeleccionada] = useState('');
  const [filtrosActivos, setFiltrosActivos] = useState({});
  const [ordenElegido, setOrden] = useState(null);
  const orden = ordenElegido ?? (ORDENES[configuracion?.orden_catalogo] ? configuracion.orden_catalogo : 'destacados');
  const [respuestaPaginada, setRespuestaPaginada] = useState(false);
  const layoutCatalogo = configuracion?.layout_catalogo || 'GRID_3';

  // Estado de paginación y filtros del servidor (SCRUM-179)
  const [pagina, setPagina] = useState(1);
  const [totalPaginas, setTotalPaginas] = useState(1);
  const [totalProductos, setTotalProductos] = useState(0);
  const [filtrosServidor, setFiltrosServidor] = useState({ categorias: [], atributos: {} });
  const [consultaCargada, setConsultaCargada] = useState(null);
  const cargando = consultaCargada !== claveConsulta(pagina, categoriaSeleccionada, coleccionSeleccionada, filtrosActivos, orden);

  // APLICAR COLORES: Paleta del Administrador
  useEffect(() => {
    aplicarPaleta(temaConfigurado);
    localStorage.setItem('ecommerce_palette', String(temaConfigurado));
  }, [temaConfigurado]);

  // FETCH DE PRODUCTOS PAGINADOS Y FILTRADOS DESDE EL SERVIDOR (SCRUM-179)
  useEffect(() => {
    if (!configuracionDisponible) return;
    const controller = new AbortController();
    const clave = claveConsulta(pagina, categoriaSeleccionada, coleccionSeleccionada, filtrosActivos, orden);

    const params = {
      page: pagina,
      page_size: 24,
      orden,
    };
    if (categoriaSeleccionada) {
      params.categoria = categoriaSeleccionada;
    }
    if (coleccionSeleccionada) {
      params.coleccion = coleccionSeleccionada;
    }
    Object.entries(filtrosActivos).forEach(([k, v]) => {
      if (v) params[`atributo_${k}`] = v;
    });

    clienteAxios
      .get('catalogo/productos/', { params, signal: controller.signal })
      .then(({ data }) => {
        const listaProductos = Array.isArray(data) ? data : (data?.results || []);
        
        const productosPublicados = listaProductos.filter(
          (producto) => producto && typeof producto === 'object' && producto.activo !== false && producto.publicado !== false
        );

        setProductos(productosPublicados);
        setRespuestaPaginada(!Array.isArray(data) && Array.isArray(data?.results));

        if (data && !Array.isArray(data) && typeof data === 'object') {
          setTotalPaginas(data.total_pages || 1);
          setTotalProductos(data.count ?? productosPublicados.length);
          if (data.filtros) {
            setFiltrosServidor(data.filtros);
          }
        } else {
          setTotalPaginas(1);
          setTotalProductos(productosPublicados.length);
        }
        setConsultaCargada(clave);
      })
      .catch((error) => {
        if (error.name !== 'CanceledError' && error.code !== 'ERR_CANCELED') {
          console.error('No se pudo cargar el catálogo:', error);
          setConsultaCargada(clave);
        }
      });

    return () => controller.abort();
  }, [pagina, categoriaSeleccionada, coleccionSeleccionada, filtrosActivos, orden, configuracionDisponible]);

  // LÓGICA DE FILTROS: Opciones que vienen del servidor o fallback local
  const categoriasUnicas = useMemo(() => {
    if (filtrosServidor?.categorias?.length > 0) {
      return filtrosServidor.categorias;
    }
    const categorias = [...new Set(productos.map((producto) => producto.categoria).filter(Boolean))].sort();
    const prioridades = (configuracion?.orden_categorias || []).filter(categoria => categorias.includes(categoria));
    return [...prioridades, ...categorias.filter(categoria => !prioridades.includes(categoria))];
  }, [filtrosServidor, productos, configuracion?.orden_categorias]);

  const productosFiltrados = useMemo(() => {
    // Si el backend ya devolvió resultados paginados o filtrados por servidor
    if (respuestaPaginada) {
      return productos;
    }
    return productos.filter((producto) => {
      if (categoriaSeleccionada && producto.categoria !== categoriaSeleccionada) return false;

      return Object.entries(filtrosActivos).every(([atributo, valor]) => {
        if (!valor) return true;
        const valorAtributo = obtenerAtributos(producto)[atributo];
        return mostrarValor(valorAtributo) === valor;
      });
    });
  }, [productos, categoriaSeleccionada, filtrosActivos, respuestaPaginada]);

  const atributosDinamicos = useMemo(() => {
    if (!categoriaSeleccionada) return [];
    const claves = new Set();
    if (filtrosServidor?.atributos?.[categoriaSeleccionada]) {
      Object.keys(filtrosServidor.atributos[categoriaSeleccionada]).forEach((clave) => claves.add(clave));
    }
    productosFiltrados.forEach((producto) => {
      Object.keys(obtenerAtributos(producto)).forEach((clave) => claves.add(clave));
    });
    return [...claves];
  }, [filtrosServidor, categoriaSeleccionada, productosFiltrados]);

  const obtenerOpcionesPorAtributo = (atributo) => {
    const opcionesServidor = filtrosServidor?.atributos?.[categoriaSeleccionada]?.[atributo] || [];
    const opcionesLocales = productos
      .filter((producto) => producto.categoria === categoriaSeleccionada)
      .map((producto) => obtenerAtributos(producto)[atributo])
      .filter((valor) => valor !== null && valor !== undefined && valor !== '')
      .map(mostrarValor);
    return [...new Set([...opcionesServidor, ...opcionesLocales])];
  };

  const cambiarCategoria = (event) => {
    setCategoriaSeleccionada(event.target.value);
    setFiltrosActivos({});
    setPagina(1);
  };

  const cambiarColeccion = (evento) => {
    setColeccionSeleccionada(evento.target.value);
    setPagina(1); 
  };

  const cambiarFiltroAtributo = (atributo, valor) => {
    setFiltrosActivos((previos) => ({ ...previos, [atributo]: valor }));
    setPagina(1);
  };

  const cambiarOrden = (event) => {
    setOrden(event.target.value);
    setPagina(1);
  };

  const cambiarPagina = (nuevaPagina) => {
    if (nuevaPagina >= 1 && nuevaPagina <= totalPaginas) {
      setPagina(nuevaPagina);
      document.getElementById('contenido')?.scrollIntoView?.({ behavior: 'smooth' });
    }
  };

  const productosOrdenados = useMemo(() => {
    if (respuestaPaginada) {
      return productosFiltrados;
    }
    const { comparar } = ORDENES[orden];
    return comparar ? [...productosFiltrados].sort(comparar) : productosFiltrados;
  }, [productosFiltrados, orden, respuestaPaginada]);

  const rangoPaginacion = useMemo(
    () => calcularRangoPaginacion(pagina, totalPaginas),
    [pagina, totalPaginas]
  );

  const esLista = layoutCatalogo === 'LISTA';
  

  return (
    <div className="catalogo-page">
      <Header />
      <main tabIndex={-1} className="catalogo" id="contenido">
        <section className="catalogo-encabezado" aria-labelledby="catalogo-titulo">
          <div className="contenedor">
            <span className="antetitulo">Tienda</span>
            <h1 id="catalogo-titulo">Catálogo</h1>
          </div>
        </section>

        {/* RF-01.3: los filtros de atributos salen de los productos de la categoría elegida */}
        <div className="catalogo-filtros">
          <div className="contenedor catalogo-filtros-contenido">
            <div className="catalogo__campo">
              <label htmlFor="categoria">Categoría</label>
              <select id="categoria" value={categoriaSeleccionada} onChange={cambiarCategoria}>
                <option value="">Todas</option>
                {categoriasUnicas.map((categoria) => (
                  <option key={categoria} value={categoria}>{categoria}</option>
                ))}
              </select>
            </div>

            {(filtrosServidor?.colecciones && filtrosServidor.colecciones.length > 0) && (
              <div className="catalogo__campo" data-testid="selector-colecciones">
                <label htmlFor="coleccion">Colección</label>
                <select
                  id="coleccion"
                  value={coleccionSeleccionada}
                  onChange={cambiarColeccion}
                >
                  <option value="">Cualquier colección</option>
                  
                  
                  {filtrosServidor.colecciones.map((coleccion) => (
                    <option key={coleccion} value={coleccion}>
                      {coleccion}
                    </option>
                  ))}
                </select>
              </div>
            )}


            {categoriaSeleccionada && atributosDinamicos.map((atributo) => (
              <div className="catalogo__campo" key={atributo}>
                <label htmlFor={`atributo-${atributo}`}>{atributo.replaceAll('_', ' ')}</label>
                <select
                  id={`atributo-${atributo}`}
                  value={filtrosActivos[atributo] ?? ''}
                  onChange={(event) => cambiarFiltroAtributo(atributo, event.target.value)}
                >
                  <option value="">Cualquier {atributo.replaceAll('_', ' ')}</option>
                  {obtenerOpcionesPorAtributo(atributo).map((valor) => (
                    <option key={valor} value={valor}>{valor}</option>
                  ))}
                </select>
              </div>
            ))}

            <div className="catalogo__campo catalogo__campo--orden">
              <label htmlFor="orden">Ordenar por</label>
              <select id="orden" value={orden} onChange={cambiarOrden}>
                {Object.entries(ORDENES).map(([valor, { etiqueta }]) => (
                  <option key={valor} value={valor}>{etiqueta}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="contenedor catalogo__contenido">
          <p className="catalogo-cantidad texto-secundario" role="status">
            {cargando ? 'Cargando productos...' : totalProductos === 1 ? '1 producto' : `${totalProductos} productos`}
          </p>

          {cargando ? (
            <div aria-hidden="true">
              <EsqueletoTarjetas cantidad={{ LISTA: 4, GRID_4: 8 }[layoutCatalogo] || 6} lista={esLista}
                className={CLASES_LAYOUT[layoutCatalogo] || CLASES_LAYOUT.GRID_3} />
            </div>
          ) : productosOrdenados.length === 0 ? (
            <p className="catalogo__vacio">No hay productos para mostrar.</p>
          ) : (
            <>
              <ul className={`${CLASES_LAYOUT[layoutCatalogo] || CLASES_LAYOUT.GRID_3} lista-sin-estilo`}>
                {productosOrdenados.map((prod) => (
                  <li key={prod.id ?? prod._id}>
                    {esLista ? <ProductCardList producto={prod} /> : <ProductCardGrid producto={prod} />}
                  </li>
                ))}
              </ul>

              {totalPaginas > 1 && (
                <nav aria-label="Paginación del catálogo" className="catalogo-paginacion">
                  <button
                    type="button"
                    className="catalogo-paginacion__btn"
                    onClick={() => cambiarPagina(pagina - 1)}
                    disabled={pagina <= 1}
                    aria-label="Página anterior"
                  >
                    Anterior
                  </button>

                  {rangoPaginacion.map((item, idx) =>
                    item === '...' ? (
                      <span key={`elipsis-${idx}`} className="catalogo-paginacion__elipsis" aria-hidden="true">
                        &hellip;
                      </span>
                    ) : (
                      <button
                        key={item}
                        type="button"
                        className={`catalogo-paginacion__btn ${pagina === item ? 'catalogo-paginacion__btn--activa' : ''}`}
                        onClick={() => cambiarPagina(item)}
                        aria-current={pagina === item ? 'page' : undefined}
                        aria-label={`Página ${item}`}
                      >
                        {item}
                      </button>
                    )
                  )}

                  <button
                    type="button"
                    className="catalogo-paginacion__btn"
                    onClick={() => cambiarPagina(pagina + 1)}
                    disabled={pagina >= totalPaginas}
                    aria-label="Página siguiente"
                  >
                    Siguiente
                  </button>
                </nav>
              )}
            </>
          )}
        </div>
      </main>
      <BotonSubir destino="contenido" />
    </div>
  );
}
