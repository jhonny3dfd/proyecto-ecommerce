import './Esqueleto.css';

// Un bloque del esqueleto. `forma`: 'circulo' o 'boton'; sin forma es un rectángulo (una línea de texto, una imagen)
export function Bloque({ ancho = '100%', alto = '1em', forma, className = '', style }) {
  const clases = ['esqueleto', forma && `esqueleto--${forma}`, className].filter(Boolean).join(' ');
  return <span aria-hidden="true" className={clases} style={{ width: ancho, height: alto, ...style }} />;
}

// Lo que se muestra mientras carga: el lector de pantalla oye `texto` y los bloques quedan ocultos para él.
// Sin aria-busy: en una región role="status" haría que el lector espere y no anuncie nada
export function Cargando({ texto, children, className, style }) {
  return (
    <div role="status" className={className} style={style}>
      <span className="visualmente-oculto">{texto}</span>
      <div aria-hidden="true">{children}</div>
    </div>
  );
}
