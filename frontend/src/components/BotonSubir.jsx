import { useEffect, useState } from 'react';
import './BotonSubir.css';

// Píxeles que hay que bajar para que aparezca: arriba no hace falta, porque ya se ve el inicio
const DISTANCIA_PARA_MOSTRAR = 400;

// Botón flotante abajo a la derecha que lleva al inicio de la página. Solo existe mientras se está más abajo de
// DISTANCIA_PARA_MOSTRAR: oculto no se renderiza, así que tampoco recibe el foco con el teclado.
export default function BotonSubir({ destino = 'contenido' }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let pendiente = null;
    const revisar = () => {
      pendiente = null;
      setVisible(window.scrollY > DISTANCIA_PARA_MOSTRAR);
    };
    const alDesplazar = () => {
      if (pendiente === null) pendiente = window.requestAnimationFrame(revisar);
    };
    revisar();
    window.addEventListener('scroll', alDesplazar, { passive: true });
    return () => {
      window.removeEventListener('scroll', alDesplazar);
      if (pendiente !== null) window.cancelAnimationFrame(pendiente);
    };
  }, []);

  if (!visible) return null;

  const subir = () => {
    const reducirMovimiento = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: reducirMovimiento ? 'auto' : 'smooth' });
    // El foco va al inicio del contenido: con el teclado se sigue desde arriba y no se pierde al ocultarse el botón
    document.getElementById(destino)?.focus({ preventScroll: true });
  };

  return (
    <button type="button" className="boton-subir" onClick={subir} aria-label="Volver al inicio de la página">
      <svg className="boton-subir__icono" width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"
        focusable="false">
        <path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="currentColor" strokeWidth="2.25"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
}
