import { Bloque } from './Esqueleto';

// Esqueletos de la tienda pública: usan las clases reales de cada página, así ocupan el mismo lugar que lo que
// viene. Van dentro de <Cargando> (o de un contenedor con aria-hidden), que los oculta al lector de pantalla

const lista = (cantidad) => Array.from({ length: cantidad }, (_, i) => i);
const ANCHOS = ['70%', '55%', '85%', '60%', '75%'];
const ANCHOS_PARRAFO = ['100%', '96%', '98%', '45%'];
const FOTO_PRODUCTO = { aspectRatio: '4 / 5' };

function TarjetaProducto() {
  return (
    <div className="tarjeta-producto">
      <Bloque alto="auto" style={{ ...FOTO_PRODUCTO, marginBottom: '18px' }} />
      <Bloque ancho="35%" alto="0.7rem" style={{ marginBottom: '10px' }} />
      <Bloque ancho="75%" alto="1.3rem" style={{ marginBottom: '10px' }} />
      <Bloque ancho="30%" alto="1rem" />
    </div>
  );
}

function FilaProducto() {
  return (
    <div className="fila-producto">
      <Bloque alto="auto" style={FOTO_PRODUCTO} />
      <div className="fila-producto-info">
        <Bloque ancho="20%" alto="0.7rem" style={{ marginBottom: '10px' }} />
        <Bloque ancho="45%" alto="1.3rem" style={{ marginBottom: '14px' }} />
        <Bloque ancho="90%" style={{ marginBottom: '8px' }} />
        <Bloque ancho="70%" />
      </div>
      <div className="fila-producto-compra">
        <Bloque ancho="6rem" alto="1.2rem" />
      </div>
    </div>
  );
}

// Tarjetas de productos con la grilla (o la lista) que se pase en `className`
export function EsqueletoTarjetas({ cantidad = 8, lista: comoLista = false, className }) {
  return (
    <div className={className}>
      {lista(cantidad).map((tarjeta) => (comoLista ? <FilaProducto key={tarjeta} /> : <TarjetaProducto key={tarjeta} />))}
    </div>
  );
}

// La portada de la landing (fondo oscuro): antetítulo, título en dos líneas, texto y botón.
// Va directo dentro de .portada (flex), que ya anuncia "Cargando la tienda...": oculto al lector de pantalla
export function EsqueletoPortada() {
  return (
    <div className="contenedor portada-contenido" aria-hidden="true">
      <Bloque ancho="9rem" alto="0.75rem" style={{ marginBottom: '1.5rem' }} />
      <Bloque ancho="min(100%, 32rem)" alto="clamp(2.5rem, 6vw, 4rem)" style={{ marginBottom: '0.75rem' }} />
      <Bloque ancho="min(80%, 22rem)" alto="clamp(2.5rem, 6vw, 4rem)" style={{ marginBottom: '1.5rem' }} />
      <Bloque ancho="min(100%, 28rem)" style={{ marginBottom: '0.6rem' }} />
      <Bloque ancho="min(70%, 20rem)" style={{ marginBottom: '2.25rem' }} />
      <Bloque ancho="13rem" alto="3.2rem" forma="boton" />
    </div>
  );
}

// La ficha del producto: ruta de navegación, foto y la columna con nombre, precio, descripción y compra
export function EsqueletoDetalle() {
  return (
    <>
      <div className="detalle-migas">
        <Bloque ancho="14rem" alto="0.9rem" />
      </div>
      <div className="detalle-contenido">
        <Bloque alto="auto" style={FOTO_PRODUCTO} />
        <div className="esqueleto-columna">
          <Bloque ancho="6rem" alto="0.75rem" />
          <Bloque ancho="80%" alto="2.5rem" />
          <Bloque ancho="35%" alto="1.6rem" style={{ marginBottom: '16px' }} />
          {ANCHOS.slice(0, 4).map((ancho) => <Bloque key={ancho} ancho={ancho} />)}
          <Bloque ancho="40%" alto="2.75rem" style={{ marginTop: '16px' }} />
          <Bloque alto="3.2rem" forma="boton" />
        </div>
      </div>
    </>
  );
}

// Tarjetas del blog: portada 4:3, fecha, título y resumen
export function EsqueletoBlog({ cantidad = 3 }) {
  return (
    <div className="blog-grilla">
      {lista(cantidad).map((tarjeta) => (
        <div key={tarjeta} className="esqueleto-columna">
          <Bloque alto="auto" style={{ aspectRatio: '4 / 3', marginBottom: '8px' }} />
          <Bloque ancho="35%" alto="0.75rem" />
          <Bloque ancho="80%" alto="1.5rem" />
          <Bloque ancho="95%" />
          <Bloque ancho="60%" />
        </div>
      ))}
    </div>
  );
}

// Una página de texto (publicación del blog, página legal): antetítulo, título, fecha y párrafos
export function EsqueletoTexto({ lineas = 10 }) {
  return (
    <div className="esqueleto-columna">
      <Bloque ancho="9rem" alto="0.75rem" />
      <Bloque ancho="75%" alto="clamp(2.25rem, 5vw, 3.25rem)" />
      <Bloque ancho="12rem" alto="0.85rem" style={{ marginBottom: '32px' }} />
      {/* Cada cuatro líneas, una corta: se lee como el final de un párrafo */}
      {lista(lineas).map((linea) => <Bloque key={linea} ancho={ANCHOS_PARRAFO[linea % ANCHOS_PARRAFO.length]} />)}
    </div>
  );
}
