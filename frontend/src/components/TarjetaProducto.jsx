import { useState } from 'react';
import { Link } from 'react-router-dom';
import { obtenerDatosPrecioYStock } from '../utils/precios';
import EtiquetaProducto from './EtiquetaProducto';
import { AvisoProductoExclusivo } from './AccesoProductoExclusivo';
import './TarjetaProducto.css';

// Tarjeta de producto del estilo editorial: foto vertical, categoría, nombre y precio (con oferta tachada).
// La usan las secciones de la landing; toda la tarjeta es un enlace a la ficha del producto.
export default function TarjetaProducto({ producto, etiqueta }) {
  const id = producto.id || producto._id;
  const imagen = producto.imagenes?.[0];
  const [imagenRota, setImagenRota] = useState(false);
  const { agotado, textoPrecio, precioTachado, tieneOferta } = obtenerDatosPrecioYStock(producto.variantes);
  const esColeccionPrivada = Boolean(producto.coleccion_privada);
  const tieneVersionVenta = esColeccionPrivada && Boolean(producto.version_a_la_venta) && Boolean(producto.version_a_la_venta_disponible);

  const contenido = (
    <>
      <div className="tarjeta-producto-imagen">
        {imagen && !imagenRota ? (
          // El nombre ya está en la tarjeta: la foto es decorativa para el lector de pantalla
          <img src={imagen} alt="" loading="lazy" onError={() => setImagenRota(true)} />
        ) : (
          <span className="tarjeta-producto-sin-imagen" aria-hidden="true">{producto.nombre?.charAt(0)}</span>
        )}
        <EtiquetaProducto producto={producto} etiquetaSeccion={etiqueta} />
      </div>

      {producto.categoria && <span className="tarjeta-producto-categoria">{producto.categoria}</span>}
      <h3 className="tarjeta-producto-nombre">{producto.nombre}</h3>

      <p className="tarjeta-producto-precio">
        {esColeccionPrivada ? (
          <span className="tarjeta-producto-coleccion-privada">Colección privada</span>
        ) : agotado ? (
          <span className="texto-secundario">Sin stock</span>
        ) : (
          <>
            <span>{textoPrecio}</span>
            {tieneOferta && (
              <del className="tarjeta-producto-precio-anterior">
                <span className="visualmente-oculto">Precio anterior: </span>{precioTachado}
              </del>
            )}
          </>
        )}
      </p>
    </>
  );

  if (tieneVersionVenta || producto.solo_suscriptores) {
    return (
      <div className="tarjeta-producto tarjeta-producto--con-version">
        <Link to={`/catalogo/producto/${id}`} className="tarjeta-producto-enlace">
          {contenido}
        </Link>
        {producto.solo_suscriptores && <AvisoProductoExclusivo />}
        {tieneVersionVenta && <Link
          to={`/catalogo/producto/${producto.version_a_la_venta}`}
          className="tarjeta-producto-boton-version"
        >
          {producto.texto_boton_version || 'Disponible en print'}
        </Link>}
      </div>
    );
  }

  return (
    <Link to={`/catalogo/producto/${id}`} className="tarjeta-producto">
      {contenido}
    </Link>
  );
}
