import { useEffect, useRef, useState } from 'react';

// Galería de una publicación del blog: las miniaturas abren un visor que se recorre con las flechas del teclado,
// se cierra con Escape o haciendo clic fuera, y no deja salir el foco con Tab mientras está abierto
export default function GaleriaPublicacion({ fotos, titulo }) {
  const [abierta, setAbierta] = useState(null);
  const botonQueAbrio = useRef(null);
  const botonCerrar = useRef(null);
  const visor = useRef(null);
  const total = fotos.length;
  const visible = abierta !== null;
  const descripcion = (indice) => `Foto ${indice + 1} de ${total} de "${titulo}"`;

  useEffect(() => {
    if (!visible) return undefined;
    botonCerrar.current?.focus();
    const alPresionar = (e) => {
      if (e.key === 'Escape') {
        setAbierta(null);
        botonQueAbrio.current?.focus();
      } else if (e.key === 'ArrowRight') {
        setAbierta((indice) => (indice + 1) % total);
      } else if (e.key === 'ArrowLeft') {
        setAbierta((indice) => (indice - 1 + total) % total);
      } else if (e.key === 'Tab') {
        const botones = visor.current?.querySelectorAll('button') ?? [];
        if (botones.length === 0) return;
        const primero = botones[0];
        const ultimo = botones[botones.length - 1];
        if (e.shiftKey && document.activeElement === primero) {
          e.preventDefault();
          ultimo.focus();
        } else if (!e.shiftKey && document.activeElement === ultimo) {
          e.preventDefault();
          primero.focus();
        }
      }
    };
    document.addEventListener('keydown', alPresionar);
    // La página de atrás no se desplaza mientras el visor está abierto
    const desplazamiento = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', alPresionar);
      document.body.style.overflow = desplazamiento;
    };
  }, [visible, total]);

  const abrir = (indice, evento) => {
    botonQueAbrio.current = evento.currentTarget;
    setAbierta(indice);
  };

  const cerrar = () => {
    setAbierta(null);
    botonQueAbrio.current?.focus();
  };

  const mover = (paso) => setAbierta((indice) => (indice + paso + total) % total);

  return (
    <section className="blog-galeria" aria-labelledby="blog-galeria-titulo">
      <h2 id="blog-galeria-titulo" className="blog-galeria-titulo">Galería</h2>
      <ul className="lista-sin-estilo blog-galeria-grilla">
        {fotos.map((foto, indice) => (
          <li key={foto.id}>
            <button type="button" className="blog-galeria-miniatura" onClick={(e) => abrir(indice, e)}
              aria-label={`Ver en grande: ${descripcion(indice)}`}>
              <img src={foto.imagen} alt="" loading="lazy" />
            </button>
          </li>
        ))}
      </ul>

      {visible && (
        <div className="blog-visor-fondo" onClick={(e) => e.target === e.currentTarget && cerrar()}>
          <div ref={visor} className="blog-visor" role="dialog" aria-modal="true" aria-label={`Galería de "${titulo}"`}>
            <img className="blog-visor-imagen" src={fotos[abierta].imagen} alt={descripcion(abierta)} />
            <div className="blog-visor-controles">
              {total > 1 && (
                <button type="button" className="boton boton-contorno" onClick={() => mover(-1)}>
                  <span aria-hidden="true">←</span> Anterior
                </button>
              )}
              <p className="blog-visor-contador" aria-live="polite">{abierta + 1} de {total}</p>
              {total > 1 && (
                <button type="button" className="boton boton-contorno" onClick={() => mover(1)}>
                  Siguiente <span aria-hidden="true">→</span>
                </button>
              )}
              <button ref={botonCerrar} type="button" className="boton boton-primario" onClick={cerrar}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
