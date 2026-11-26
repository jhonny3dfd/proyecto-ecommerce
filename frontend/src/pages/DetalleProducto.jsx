import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';
import VariantSelector from '../components/VariantSelector';
import ListaResenas, { PromedioResenas } from '../components/ListaResenas';
import useResenas from '../hooks/useResenas';
import { guardarCarrito, validarCarrito } from '../components/carrito';
import { obtenerDatosPrecioYStock } from '../utils/precios';
import EtiquetaProducto from '../components/EtiquetaProducto';
import AccesoProductoExclusivo from '../components/AccesoProductoExclusivo';
import VideoYouTube, { IconoPlay } from '../components/VideoYouTube';
import './DetalleProducto.css';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoDetalle } from '../components/carga/EsqueletosTienda';

export default function DetalleProducto() {
  const { id } = useParams();
  const configuracion = useConfiguracionTienda();
  const [producto, setProducto] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);

  // Índice de la imagen actualmente seleccionada
  const [imagenActual, setImagenActual] = useState(0);
  // Reseñas aprobadas del producto (si la tienda las activó)
  const resenas = useResenas(`ventas/resenas/producto/${encodeURIComponent(id)}/`,
    configuracion ? Boolean(configuracion.resenas_activas) : undefined);

  useEffect(() => {
    clienteAxios.get(`catalogo/productos/${id}/`)
      .then(({ data }) => {
        setProducto(data);
        setImagenActual(0);
        setCargando(false);
      })
      .catch((err) => {
        console.error('Error al cargar el detalle del producto:', err);
        setError('No se pudo encontrar el producto.');
        setCargando(false);
      });
  }, [id]);

  // Actualizar los metadatos SEO del producto
  useEffect(() => {
    if (!producto) return;

    const tituloAnterior = document.title;
    const descripcionMeta = document.querySelector(
      'meta[name="description"]'
    );

    const descripcionAnterior = descripcionMeta?.content;

    const tituloSEO =
      producto.meta_titulo?.trim() || producto.nombre;

    const descripcionSEO =
      producto.meta_descripcion?.trim() ||
      producto.descripcion ||
      '';

    document.title = tituloSEO;

    let metaDescripcion = descripcionMeta;

    if (!metaDescripcion) {
      metaDescripcion = document.createElement('meta');
      metaDescripcion.name = 'description';
      document.head.appendChild(metaDescripcion);
    }

    metaDescripcion.content = descripcionSEO;

    return () => {
      document.title = tituloAnterior;

      if (descripcionMeta) {
        descripcionMeta.content = descripcionAnterior;
      } else {
        metaDescripcion.remove();
      }
    };
  }, [producto]);

  // Muestra el stock que informó el servidor, que puede ser más reciente que el de la carga
  const actualizarStock = (sku, stock) => setProducto(actual => ({
    ...actual,
    variantes: actual.variantes.map(v => (v.sku === sku ? { ...v, stock } : v))
  }));

  //Función unificada para agregar al carrito. Devuelve { ok, mensaje } para VariantSelector
  const handleAgregarAlCarrito = async (
    varianteSeleccionada,
    cantidadSeleccionada = 1
  ) => {
    if (!varianteSeleccionada) {
      return { ok: false, mensaje: 'Selecciona una variante primero.' };
    }

    const carritoGuardado = localStorage.getItem('carrito_local');
    const carritoActual = carritoGuardado
      ? JSON.parse(carritoGuardado)
      : [];

    const existente = carritoActual.find(
      item => item.sku === varianteSeleccionada.sku
    );
    const enCarrito = existente ? Number(existente.cantidad) : 0;
    const tieneOferta = varianteSeleccionada.precio_oferta != null &&
      Number(varianteSeleccionada.precio_oferta) > 0 &&
      Number(varianteSeleccionada.precio_oferta) < Number(varianteSeleccionada.precio);
    const precioEfectivo = tieneOferta 
      ? Number(varianteSeleccionada.precio_oferta) 
      : Number(varianteSeleccionada.precio);

    const atributos = varianteSeleccionada.atributos_variables || {};

    const detalleAtributos = Object.entries(atributos)
      .map(([nombre, valor]) => `${nombre}: ${valor}`)
      .join(' · ');

    const linea = {
      id: producto.id,
      sku: varianteSeleccionada.sku,
      nombre: detalleAtributos
        ? `${producto.nombre} · ${detalleAtributos}`
        : producto.nombre,
      atributos,
      precio: precioEfectivo,
      cantidad: enCarrito + cantidadSeleccionada
    };

    // RN-03: lo que ya está en el carrito también cuenta contra el stock
    let revisada;
    try {
      ({ items: [revisada] } = await validarCarrito([linea]));
    } catch (error) {
      console.error('No se pudo validar el stock:', error);
      return { ok: false, mensaje: 'No pudimos verificar el stock. Intenta nuevamente.' };
    }

    actualizarStock(linea.sku, revisada.disponible);
    if (revisada.problema) {
      const yaTienes = enCarrito > 0 ? ` Ya tienes ${enCarrito} en tu carrito.` : '';
      return { ok: false, mensaje: `${revisada.mensaje}${yaTienes}` };
    }

    const precioConfirmado = (revisada?.precio !== undefined && revisada?.precio !== null)
      ? Number(revisada.precio)
      : precioEfectivo;

    const carritoNuevo = existente
      ? carritoActual.map(item => (item.sku === linea.sku ? { ...item, nombre: linea.nombre, atributos: linea.atributos, cantidad: linea.cantidad, precio: precioConfirmado } : item))
      : [...carritoActual, { ...linea, precio: precioConfirmado }];
    await guardarCarrito(carritoNuevo);
    return { ok: true, mensaje: `¡Agregaste ${cantidadSeleccionada} unidad(es) al carrito!` };
  };

  // La galería son las fotos y, al final, el video de YouTube si el producto tiene uno (pedido de Alan)
  const totalGaleria = (producto?.imagenes?.length || 0) + (producto?.youtube_id ? 1 : 0);

  // Cambiar al elemento anterior de la galería
  const imagenAnterior = () => {
    if (!totalGaleria) return;

    setImagenActual((actual) =>
      actual === 0
        ? totalGaleria - 1
        : actual - 1
    );
  };

  // Cambiar al elemento siguiente de la galería
  const imagenSiguiente = () => {
    if (!totalGaleria) return;

    setImagenActual((actual) =>
      actual === totalGaleria - 1
        ? 0
        : actual + 1
    );
  };

  // Seleccionar una imagen directamente desde las miniaturas
  const seleccionarImagen = (index) => {
    setImagenActual(index);
  };

  if (cargando) {
    return (
      <div className="detalle-page">
        <Header />
        <main tabIndex={-1} className="contenedor detalle" id="contenido">
          <Cargando texto="Cargando producto..."><EsqueletoDetalle /></Cargando>
        </main>
      </div>
    );
  }

  if (error || !producto) {
    return (
      <div className="detalle-page">
        <Header />
        <main tabIndex={-1} className="contenedor detalle-estado" id="contenido">
          <p role="alert">{error || 'Producto no disponible'}</p>
          <Link to="/catalogo" className="enlace-flecha">Volver al catálogo <span aria-hidden="true">→</span></Link>
        </main>
      </div>
    );
  }

  const imagenes = producto.imagenes || [];
  // El video va después de las fotos: se ve cuando el índice pasa la última foto
  const verVideo = Boolean(producto.youtube_id) && imagenActual === imagenes.length;
  const { agotado, textoPrecio, precioTachado, tieneOferta } = obtenerDatosPrecioYStock(producto.variantes);
  const esColeccionPrivada = Boolean(producto.coleccion_privada);
  const tieneVersionVenta = esColeccionPrivada && Boolean(producto.version_a_la_venta) && Boolean(producto.version_a_la_venta_disponible);
  const fichaTecnica = Object.entries(producto.atributos_globales || {});

  return (
    <div className="detalle-page">
      <Header />
      <main tabIndex={-1} className="contenedor detalle" id="contenido">
        <nav className="detalle-migas" aria-label="Ruta de navegación">
          <ol className="lista-sin-estilo">
            <li><Link to="/catalogo">Catálogo</Link></li>
            {producto.categoria && <li>{producto.categoria}</li>}
            <li aria-current="page">{producto.nombre}</li>
          </ol>
        </nav>

        <div className="detalle-contenido">
          {/* Galería */}
          <div className="detalle-galeria">
            {totalGaleria > 0 ? (
              <>
                <div className="detalle-imagen-principal">
                  {verVideo ? (
                    // Se monta al elegirlo y se desmonta al cambiar de foto: así el video se detiene
                    <VideoYouTube className="detalle-video" youtubeId={producto.youtube_id} titulo={producto.nombre}
                      portada={imagenes[0]} />
                  ) : (
                    <img src={imagenes[imagenActual]} alt={`${producto.nombre}, imagen ${imagenActual + 1} de ${imagenes.length}`} />
                  )}
                  {totalGaleria > 1 && (
                    <>
                      <button type="button" className="detalle-flecha detalle-flecha--anterior"
                        onClick={imagenAnterior} aria-label="Imagen anterior">‹</button>
                      <button type="button" className="detalle-flecha detalle-flecha--siguiente"
                        onClick={imagenSiguiente} aria-label="Imagen siguiente">›</button>
                      {/* Sobre el video taparía los controles del reproductor */}
                      {!verVideo && (
                        <span className="detalle-contador" aria-hidden="true">{imagenActual + 1} / {totalGaleria}</span>
                      )}
                    </>
                  )}
                </div>
                {totalGaleria > 1 && (
                  <ul className="detalle-miniaturas lista-sin-estilo">
                    {imagenes.map((imagen, index) => (
                      <li key={imagen || index}>
                        <button type="button" onClick={() => seleccionarImagen(index)}
                          aria-label={`Ver imagen ${index + 1}`} aria-pressed={index === imagenActual}
                          className="detalle-miniatura">
                          <img src={imagen} alt="" />
                        </button>
                      </li>
                    ))}
                    {producto.youtube_id && (
                      <li>
                        {/* La miniatura no pide nada a YouTube: muestra la primera foto con el ícono de play */}
                        <button type="button" onClick={() => seleccionarImagen(imagenes.length)}
                          aria-label="Ver video" aria-pressed={verVideo}
                          className="detalle-miniatura detalle-miniatura--video">
                          {imagenes[0] ? <img src={imagenes[0]} alt="" /> : <span className="detalle-miniatura-neutra" />}
                          <span className="detalle-miniatura-play" aria-hidden="true"><IconoPlay /></span>
                        </button>
                      </li>
                    )}
                  </ul>
                )}
              </>
            ) : (
              <div className="detalle-sin-imagen">
                <span aria-hidden="true">{producto.nombre?.charAt(0)}</span>
                <p className="visualmente-oculto">Sin imagen disponible</p>
              </div>
            )}
          </div>

          {/* Información y compra */}
          <div className="detalle-info">
            <EtiquetaProducto producto={producto} enFicha />
            {producto.categoria && <span className="antetitulo">{producto.categoria}</span>}
            <h1 className="detalle-nombre">{producto.nombre}</h1>
            {resenas?.total > 0 && (
              <a href="#resenas" className="detalle-calificacion">
                <PromedioResenas promedio={resenas.promedio} total={resenas.total} />
              </a>
            )}

            <p className="detalle-precio">
              {esColeccionPrivada ? (
                <span className="detalle-coleccion-privada">Colección privada</span>
              ) : agotado ? (
                <span className="texto-secundario">Sin stock</span>
              ) : (
                <>
                  <span>{textoPrecio}</span>
                  {tieneOferta && (
                    <del className="detalle-precio-anterior">
                      <span className="visualmente-oculto">Precio anterior: </span>{precioTachado}
                    </del>
                  )}
                </>
              )}
            </p>

            <hr className="detalle-separador" />

            <p className="detalle-descripcion texto-secundario">
              {producto.descripcion || 'Sin descripción disponible.'}
            </p>

            {fichaTecnica.length > 0 && (
              <dl className="detalle-ficha">
                {fichaTecnica.map(([clave, valor]) => (
                  <div key={clave}>
                    <dt>{clave.replaceAll('_', ' ')}</dt>
                    <dd>{String(valor)}</dd>
                  </div>
                ))}
              </dl>
            )}

            <div className="detalle-compra">
              {esColeccionPrivada ? (
                tieneVersionVenta ? (
                  <Link
                    to={`/catalogo/producto/${producto.version_a_la_venta}`}
                    className="boton boton-primario detalle-boton-version-print"
                  >
                    {producto.texto_boton_version || 'Disponible en print'}
                  </Link>
                ) : null
              ) : (
                <AccesoProductoExclusivo producto={producto}>
                  <VariantSelector producto={producto} onAgregarAlCarrito={handleAgregarAlCarrito} />
                </AccesoProductoExclusivo>
              )}
            </div>

            {configuracion?.cotizaciones_activas && (
              <p className="detalle-cotizar texto-secundario">
                ¿Lo necesitas personalizado o en cantidad?{' '}
                <Link to={`/cotizar?producto=${encodeURIComponent(producto.id)}`}>Pide una cotización</Link>
              </p>
            )}
          </div>
        </div>

        {resenas?.total > 0 && (
          <section id="resenas" className="detalle-resenas" aria-labelledby="detalle-resenas-titulo">
            <div className="detalle-resenas-encabezado">
              <h2 id="detalle-resenas-titulo">Reseñas</h2>
              <PromedioResenas promedio={resenas.promedio} total={resenas.total} />
            </div>
            {resenas.resenas.length > 0 ? (
              <ListaResenas resenas={resenas.resenas} />
            ) : (
              <p className="texto-secundario">Quienes lo compraron lo calificaron, pero todavía no dejan comentarios.</p>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
