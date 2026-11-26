import { Link } from 'react-router-dom';
import TarjetaProducto from '../TarjetaProducto';
import { Cargando } from '../carga/Esqueleto';
import { EsqueletoTarjetas } from '../carga/EsqueletosTienda';

// Sección de 4 productos de la landing ("Más vendidos", "Últimos agregados"). Sin productos no se muestra.
// nota: aviso del modo edición (estas secciones no se editan, se llenan solas con los productos).
// cargando: mientras llega la vitrina se muestran 4 tarjetas vacías bajo el título
export default function SeccionProductos({ id, antetitulo, titulo, productos, etiqueta, alterna = false, nota, cargando = false }) {
  if (!cargando && !productos?.length) return null;

  return (
    <section id={id} className={`seccion-landing${alterna ? ' seccion-landing--alterna' : ''}`}
      aria-labelledby={`${id}-titulo`}>
      <div className="contenedor">
        <div className="seccion-landing-encabezado">
          <div>
            <span className="antetitulo">{antetitulo}</span>
            <h2 id={`${id}-titulo`}>{titulo}</h2>
          </div>
          <Link to="/catalogo" className="enlace-flecha">
            Ver todo <span aria-hidden="true">→</span>
          </Link>
        </div>

        {nota && <p className="seccion-landing-nota">{nota}</p>}

        {cargando ? (
          <Cargando texto="Cargando productos..."><EsqueletoTarjetas cantidad={4} className="grilla-productos" /></Cargando>
        ) : (
          <ul className="grilla-productos lista-sin-estilo">
            {productos.map((producto) => (
              <li key={producto.id || producto._id}>
                <TarjetaProducto producto={producto} etiqueta={etiqueta} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
