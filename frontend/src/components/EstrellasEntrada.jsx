import { useState } from 'react';
import './Estrellas.css';

const PUNTA = 'M12 2.5l2.94 5.96 6.56.95-4.75 4.63 1.12 6.54L12 17.5l-5.87 3.08 1.12-6.54L2.5 9.41l6.56-.95z';
const TEXTOS_ESTRELLAS ={ 1: 'Muy mala', 2: 'Mala', 3: 'Regular', 4: 'Buena', 5: 'Excelente' };

// Elegir de 1 a 5 estrellas. Son 5 radios nativos: con Tab se entra al grupo, las flechas cambian la elección y
// el lector de pantalla lee "4 estrellas: Buena, 4 de 5". `alQuitar` (opcional) deja borrar la elección
export default function EstrellasEntrada({ nombre, leyenda, valor, onChange, alQuitar, error, requerido = false }) {
  // Al pasar el mouse se ven las estrellas que quedarían marcadas
  const [previa, setPrevia] = useState(null);
  const marcadas = previa ?? valor ?? 0;
  const idError = `${nombre}-error`;

  return (
    <fieldset className="estrellas-entrada">
      <legend className="estrellas-entrada-leyenda">{leyenda}</legend>
      <div className="estrellas-entrada-fila">
        <div className="estrellas-entrada-opciones" onMouseLeave={() => setPrevia(null)}>
          {[1, 2, 3, 4, 5].map((numero) => (
            <label key={numero} className="estrellas-entrada-opcion" onMouseEnter={() => setPrevia(numero)}>
              <input type="radio" className="visualmente-oculto" name={nombre} value={numero}
                checked={valor === numero} onChange={() => onChange(numero)} required={requerido}
                aria-invalid={error ? true : undefined} aria-describedby={error ? idError : undefined} />
              <svg aria-hidden="true" width="34" height="34" viewBox="0 0 24 24"
                className={numero <= marcadas ? 'estrella estrella--llena' : 'estrella'}>
                <path d={PUNTA} />
              </svg>
              <span className="visualmente-oculto">
                {numero} {numero === 1 ? 'estrella' : 'estrellas'}: {TEXTOS_ESTRELLAS[numero]}
              </span>
            </label>
          ))}
        </div>
        {/* El texto ya lo lee el radio elegido: aquí solo se muestra */}
        <span className="estrellas-entrada-texto" aria-hidden="true">{TEXTOS_ESTRELLAS[marcadas] || ''}</span>
        {alQuitar && valor && (
          <button type="button" className="estrellas-entrada-quitar" onClick={alQuitar}
            aria-label={`Quitar la calificación de ${leyenda}`}>
            Quitar
          </button>
        )}
      </div>
      {error && <p id={idError} role="alert" className="checkout-error-campo">{error}</p>}
    </fieldset>
  );
}
