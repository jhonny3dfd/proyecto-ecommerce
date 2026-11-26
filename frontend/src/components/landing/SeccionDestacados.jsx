import { useState } from 'react';
import { Link } from 'react-router-dom';
import { obtenerDatosPrecioYStock } from '../../utils/precios';
import EtiquetaProducto from '../EtiquetaProducto';
import { Cargando } from '../carga/Esqueleto';
import { EsqueletoTarjetas } from '../carga/EsqueletosTienda';
// La etiqueta, la categoría y el precio usan los mismos estilos que las tarjetas de "Más vendidos"
import '../TarjetaProducto.css';

// Destacados de la landing (RF-01.1, pedido de un cliente): las obras y proyectos que eligió el admin, en vez de
// "Más vendidos". Tarjetas del doble de tamaño: dos por fila en el computador y una en el celular.
// destacados: [{ tipo: 'PRODUCTO' | 'PUBLICACION', id, nombre, imagen, enlace, categoria?, variantes? }]
// (GET catalogo/vitrina/)
// En el modo edición, editorTitulo (el campo del título) va en lugar del título y children (el editor de la
// selección) sobre la vista previa
export default function SeccionDestacados({
  titulo, destacados, cargando = false, nombreBlog, nota, editorTitulo, children,
}) {
  if (!cargando && !destacados?.length && !children) return null;

  return (
    <section id="destacados" className="seccion-landing seccion-landing--alterna" aria-labelledby="destacados-titulo">
      <div className="contenedor">
        <div className="seccion-landing-encabezado">
          <div>
            <span className="antetitulo">Selección de la tienda</span>
            <h2 id="destacados-titulo" className={editorTitulo ? 'visualmente-oculto' : undefined}>
              {titulo || 'Destacados'}
            </h2>
            {editorTitulo}
          </div>
          <Link to="/catalogo" className="enlace-flecha">
            Ver todo <span aria-hidden="true">→</span>
          </Link>
        </div>

        {nota && <p className="seccion-landing-nota">{nota}</p>}
        {/* Modo edición: el editor de la selección va aquí, sobre la vista previa */}
        {children}

        {cargando ? (
          <Cargando texto="Cargando destacados...">
            <EsqueletoTarjetas cantidad={2} className="grilla-destacados" />
          </Cargando>
        ) : destacados?.length > 0 && (
          <ul className="grilla-destacados lista-sin-estilo">
            {destacados.map((destacado) => (
              <li key={`${destacado.tipo}-${destacado.id}`}>
                <TarjetaDestacado destacado={destacado} nombreBlog={nombreBlog} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function TarjetaDestacado({ destacado, nombreBlog }) {
  const [imagenRota, setImagenRota] = useState(false);
  const esProducto = destacado.tipo === 'PRODUCTO';
  const esColeccionPrivada = esProducto && Boolean(destacado.coleccion_privada);
  const precio = (esProducto && !esColeccionPrivada) ? obtenerDatosPrecioYStock(destacado.variantes) : null;

  return (
    <Link to={destacado.enlace} className="tarjeta-destacado">
      <div className="tarjeta-destacado-imagen">
        {destacado.imagen && !imagenRota ? (
          // El nombre ya está en la tarjeta: la foto es decorativa para el lector de pantalla. El ancho y el alto
          // reservan su lugar (3:2) para que la página no salte al cargarla
          <img src={destacado.imagen} alt="" width="900" height="600" loading="lazy" decoding="async"
            onError={() => setImagenRota(true)} />
        ) : (
          <span className="tarjeta-destacado-sin-imagen" aria-hidden="true">{destacado.nombre?.charAt(0)}</span>
        )}
        {esProducto && <EtiquetaProducto producto={destacado} />}
      </div>

      {/* Sobre el nombre: la categoría del producto o el nombre del blog, para que los nombres queden alineados */}
      {(esProducto ? destacado.categoria : nombreBlog || 'Blog') && (
        <span className="tarjeta-producto-categoria">{esProducto ? destacado.categoria : nombreBlog || 'Blog'}</span>
      )}
      <h3 className="tarjeta-destacado-nombre">{destacado.nombre}</h3>

      {esProducto && (
        <p className="tarjeta-producto-precio">
          {esColeccionPrivada ? (
            <span className="tarjeta-producto-coleccion-privada">Colección privada</span>
          ) : precio?.agotado ? (
            <span className="texto-secundario">Sin stock</span>
          ) : (
            <>
              <span>{precio?.textoPrecio}</span>
              {precio?.tieneOferta && (
                <del className="tarjeta-producto-precio-anterior">
                  <span className="visualmente-oculto">Precio anterior: </span>{precio.precioTachado}
                </del>
              )}
            </>
          )}
        </p>
      )}
    </Link>
  );
}
