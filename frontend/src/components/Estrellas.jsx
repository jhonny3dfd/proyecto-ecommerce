import './Estrellas.css';

const PUNTA = 'M12 2.5l2.94 5.96 6.56.95-4.75 4.63 1.12 6.54L12 17.5l-5.87 3.08 1.12-6.54L2.5 9.41l6.56-.95z';

// Muestra una calificación de 1 a 5. Los lectores de pantalla leen "4,5 de 5 estrellas", no cada ícono; un
// promedio se dibuja redondeado a estrellas enteras. `decorativa` las oculta cuando el número ya está escrito al lado
export default function Estrellas({ valor, tamano = 18, className = '', decorativa = false }) {
  const llenas = Math.round(valor);
  const texto = `${Number(valor).toLocaleString('es-CL', { maximumFractionDigits: 1 })} de 5 estrellas`;
  const accesible = decorativa ? { 'aria-hidden': true } : { role: 'img', 'aria-label': texto };
  return (
    <span {...accesible} className={`estrellas ${className}`.trim()}>
      {[1, 2, 3, 4, 5].map((numero) => (
        <svg key={numero} aria-hidden="true" width={tamano} height={tamano} viewBox="0 0 24 24"
          className={numero <= llenas ? 'estrella estrella--llena' : 'estrella'}>
          <path d={PUNTA} />
        </svg>
      ))}
    </span>
  );
}
