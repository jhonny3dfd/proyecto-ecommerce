import { useEffect, useRef, useState } from 'react';

// Línea de lectura: una sección cuenta como "actual" cuando su título pasó esta altura (en píxeles desde arriba)
const LINEA_LECTURA = 120;

// Índice lateral de la vista Configuración. Queda fijo al bajar y, como es más alto que la pantalla, tiene su propia
// barra de desplazamiento (Admin.css). Marca la sección que se está leyendo y la mantiene visible dentro del índice.
export default function IndiceConfiguracion({ grupos, alElegir }) {
  const [actual, setActual] = useState(grupos[0]?.secciones[0]?.id ?? null);
  const indiceRef = useRef(null);

  useEffect(() => {
    const ids = grupos.flatMap(grupo => grupo.secciones.map(seccion => seccion.id));
    let pendiente = null;
    const revisar = () => {
      pendiente = null;
      let encontrada = ids[0];
      for (const id of ids) {
        const titulo = document.getElementById(id);
        if (titulo && titulo.getBoundingClientRect().top <= LINEA_LECTURA) encontrada = id;
      }
      // Al llegar al final de la página, la última sección no siempre alcanza la línea de lectura
      const altoPagina = document.documentElement.scrollHeight;
      const alFinal = altoPagina > window.innerHeight && window.innerHeight + window.scrollY >= altoPagina - 2;
      setActual(alFinal ? ids[ids.length - 1] : encontrada);
    };
    const alDesplazar = () => {
      if (pendiente === null) pendiente = window.requestAnimationFrame(revisar);
    };
    revisar();
    window.addEventListener('scroll', alDesplazar, { passive: true });
    window.addEventListener('resize', alDesplazar);
    return () => {
      window.removeEventListener('scroll', alDesplazar);
      window.removeEventListener('resize', alDesplazar);
      if (pendiente !== null) window.cancelAnimationFrame(pendiente);
    };
  }, [grupos]);

  // La sección actual siempre se ve dentro del índice. Se mueve solo el índice, no la página
  useEffect(() => {
    const indice = indiceRef.current;
    const boton = indice?.querySelector('[aria-current="location"]');
    if (!indice || !boton) return;
    // Posición del botón dentro del contenido del índice, contando lo que ya se desplazó
    const arriba = boton.getBoundingClientRect().top - indice.getBoundingClientRect().top + indice.scrollTop;
    const abajo = arriba + boton.offsetHeight;
    // Si quedó fuera de la vista, se centra: así se ven también las secciones de antes y de después
    if (arriba < indice.scrollTop || abajo > indice.scrollTop + indice.clientHeight) {
      indice.scrollTop = Math.max(0, arriba - (indice.clientHeight - boton.offsetHeight) / 2);
    }
  }, [actual]);

  return (
    <nav aria-label="Secciones de configuración" className="config-indice" ref={indiceRef}>
      <ul className="config-indice-grupos">
        {grupos.map(grupo => (
          <li key={grupo.id}>
            <span id={`${grupo.id}-indice`} className="config-indice-grupo">{grupo.titulo}</span>
            <ul aria-labelledby={`${grupo.id}-indice`}>
              {grupo.secciones.map(seccion => (
                <li key={seccion.id}>
                  <button type="button" aria-current={seccion.id === actual ? 'location' : undefined}
                    onClick={() => { setActual(seccion.id); alElegir(seccion.id); }}>
                    {seccion.titulo}
                  </button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </nav>
  );
}
