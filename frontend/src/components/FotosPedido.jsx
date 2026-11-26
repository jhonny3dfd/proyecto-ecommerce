import { useState } from 'react';
import Dialogo from './Dialogo';

// Ícono genérico para un producto sin foto (o que ya no está en el catálogo)
function SinFoto({ className }) {
  return (
    <span className={className} aria-hidden="true">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </svg>
    </span>
  );
}

const plural = (cantidad, singular, varios) => `${cantidad} ${cantidad === 1 ? singular : varios}`;

// "Mis pedidos": la foto del primer producto antes del número de orden, con "+2" si hay más. Al hacerle click se
// abren en grande las fotos de cada producto del pedido (las que tienen hoy en el catálogo), con su nombre
export default function FotosPedido({ pedido }) {
  const productos = pedido.detalles || [];
  const [abierta, setAbierta] = useState(null);
  const portada = productos[0]?.imagen;
  const conFoto = productos.some((producto) => producto.imagen);

  if (!conFoto) return <SinFoto className="pedido-miniatura pedido-miniatura--vacia" />;

  const total = productos.length;
  const actual = abierta === null ? null : productos[abierta];
  const ir = (paso) => setAbierta((indice) => (indice + paso + total) % total);
  const tituloId = `pedido-fotos-${pedido.id}`;

  return (
    <>
      <button type="button" className="pedido-miniatura" onClick={() => setAbierta(0)}
        aria-label={`Ver las fotos del pedido #${pedido.id}, ${plural(total, 'producto', 'productos')}`}>
        {portada ? <img src={portada} alt="" loading="lazy" /> : <SinFoto className="pedido-miniatura-icono" />}
        {total > 1 && <span className="pedido-miniatura-mas" aria-hidden="true">+{total - 1}</span>}
      </button>

      {actual && (
        <Dialogo className="historial-dialogo pedido-visor" tituloId={tituloId} onCerrar={() => setAbierta(null)}
          cerrarFuera>
          <div onKeyDown={(evento) => {
            if (total < 2 || !['ArrowLeft', 'ArrowRight'].includes(evento.key)) return;
            evento.preventDefault();
            ir(evento.key === 'ArrowRight' ? 1 : -1);
          }}>
            <h2 id={tituloId} tabIndex={-1} data-foco-inicial>Pedido #{pedido.id}</h2>
            <figure className="pedido-visor-figura">
              {actual.imagen
                ? <img src={actual.imagen} alt={actual.nombre_producto} />
                : <SinFoto className="pedido-visor-sin-foto" />}
              <figcaption>
                <strong>{actual.nombre_producto}</strong>
                {actual.variante && <span>{actual.variante}</span>}
                <span>{plural(actual.cantidad, 'unidad', 'unidades')}</span>
                {!actual.imagen && <span>Este producto ya no tiene foto en la tienda.</span>}
              </figcaption>
            </figure>
            <div className="pedido-visor-controles">
              {total > 1 && (
                <>
                  <button type="button" className="boton boton-contorno" onClick={() => ir(-1)}>
                    <span aria-hidden="true">←</span> Anterior
                  </button>
                  <p className="pedido-visor-contador" aria-live="polite">{abierta + 1} de {total}</p>
                  <button type="button" className="boton boton-contorno" onClick={() => ir(1)}>
                    Siguiente <span aria-hidden="true">→</span>
                  </button>
                </>
              )}
              <button type="button" className="boton boton-primario pedido-visor-cerrar"
                onClick={() => setAbierta(null)}>
                Cerrar
              </button>
            </div>
          </div>
        </Dialogo>
      )}
    </>
  );
}
