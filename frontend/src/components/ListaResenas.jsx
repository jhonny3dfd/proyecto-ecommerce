import Estrellas from './Estrellas';
import './ListaResenas.css';

const formatearPromedio = (promedio) => Number(promedio).toLocaleString('es-CL', {
  minimumFractionDigits: 1, maximumFractionDigits: 1
});
const formatearMes = (iso) => new Date(iso).toLocaleDateString('es-CL', { month: 'long', year: 'numeric' });

// "★★★★★ 4,8 de 5 · 23 reseñas": las estrellas son decorativas porque el número ya está escrito
export function PromedioResenas({ promedio, total, className = '' }) {
  return (
    <span className={`resenas-promedio ${className}`.trim()}>
      <Estrellas valor={promedio} decorativa />
      <span>
        <strong>{formatearPromedio(promedio)}</strong> de 5 · {total} {total === 1 ? 'reseña' : 'reseñas'}
      </span>
    </span>
  );
}

// Reseñas aprobadas: estrellas, comentario, nombre público y mes. Nunca el correo ni el pedido
export default function ListaResenas({ resenas }) {
  return (
    <ul className="lista-sin-estilo resenas-lista">
      {resenas.map((resena) => (
        <li key={`${resena.fecha}-${resena.nombre_publico}`} className="resena-tarjeta">
          <figure>
            <Estrellas valor={resena.estrellas} />
            <blockquote className="resena-tarjeta-texto">
              <p>{resena.comentario}</p>
            </blockquote>
            <figcaption className="resena-tarjeta-autor">
              {resena.nombre_publico}
              <span className="texto-secundario"> · <time dateTime={resena.fecha}>{formatearMes(resena.fecha)}</time></span>
            </figcaption>
          </figure>
        </li>
      ))}
    </ul>
  );
}
