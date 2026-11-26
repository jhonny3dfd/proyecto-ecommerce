import { useState } from 'react';
import { Link } from 'react-router-dom';
import { obtenerDatosPrecioYStock } from '../utils/precios';
import EtiquetaProducto from './EtiquetaProducto';
import { AvisoProductoExclusivo } from './AccesoProductoExclusivo';

// Layout de lista del catálogo (RF-01.4): foto a la izquierda y la descripción al costado. Toda la fila es un
// enlace a la ficha del producto (igual que la tarjeta de grilla).
export default function ProductCardList({ producto }) {
  const id = producto.id || producto._id;
  const imagen = producto.imagenes?.[0];
  const [imagenRota, setImagenRota] = useState(false);
  const { agotado, textoPrecio, precioTachado, tieneOferta } = obtenerDatosPrecioYStock(producto.variantes);
  const atributos = Object.entries(producto.atributos_globales || {});
  const esColeccionPrivada = Boolean(producto.coleccion_privada);
  const tieneVersionVenta = esColeccionPrivada && Boolean(producto.version_a_la_venta) && Boolean(producto.version_a_la_venta_disponible);

  if (tieneVersionVenta) {
    return (
      <div className="fila-producto fila-producto--con-version">
        <Link to={`/catalogo/producto/${id}`} className="fila-producto-cuerpo">
          <div className="fila-producto-imagen">
            <EtiquetaProducto producto={producto} />
            {imagen && !imagenRota ? (
              <img src={imagen} alt="" loading="lazy" onError={() => setImagenRota(true)} />
            ) : (
              <span className="tarjeta-producto-sin-imagen" aria-hidden="true">{producto.nombre?.charAt(0)}</span>
            )}
          </div>

          <div className="fila-producto-info">
            {producto.categoria && <span className="tarjeta-producto-categoria">{producto.categoria}</span>}
            <h3 className="tarjeta-producto-nombre">{producto.nombre}</h3>
            {producto.descripcion && <p className="fila-producto-descripcion texto-secundario">{producto.descripcion}</p>}
            {atributos.length > 0 && (
              <p className="fila-producto-atributos">
                {atributos.map(([clave, valor]) => `${clave.replaceAll('_', ' ')}: ${valor}`).join(' · ')}
              </p>
            )}
          </div>
        </Link>

        <div className="fila-producto-compra">
          <p className="tarjeta-producto-precio">
            <span className="tarjeta-producto-coleccion-privada">Colección privada</span>
          </p>
          {producto.solo_suscriptores && <AvisoProductoExclusivo />}
          <Link
            to={`/catalogo/producto/${producto.version_a_la_venta}`}
            className="tarjeta-producto-boton-version"
          >
            {producto.texto_boton_version || 'Disponible en print'}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
    <Link to={`/catalogo/producto/${id}`} className="fila-producto">
      <div className="fila-producto-imagen">
        {imagen && !imagenRota ? (
          <img src={imagen} alt="" loading="lazy" onError={() => setImagenRota(true)} />
        ) : (
          <span className="tarjeta-producto-sin-imagen" aria-hidden="true">{producto.nombre?.charAt(0)}</span>
        )}
        <EtiquetaProducto producto={producto} />
      </div>

      <div className="fila-producto-info">
        {producto.categoria && <span className="tarjeta-producto-categoria">{producto.categoria}</span>}
        <h3 className="tarjeta-producto-nombre">{producto.nombre}</h3>
        {producto.descripcion && <p className="fila-producto-descripcion texto-secundario">{producto.descripcion}</p>}
        {atributos.length > 0 && (
          <p className="fila-producto-atributos">
            {atributos.map(([clave, valor]) => `${clave.replaceAll('_', ' ')}: ${valor}`).join(' · ')}
          </p>
        )}
      </div>

      <div className="fila-producto-compra">
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
        <span className="enlace-flecha" aria-hidden="true">Ver producto →</span>
      </div>
    </Link>
    {producto.solo_suscriptores && <AvisoProductoExclusivo />}
    </>
  );
}
