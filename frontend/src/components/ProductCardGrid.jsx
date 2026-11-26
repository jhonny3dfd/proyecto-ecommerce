import TarjetaProducto from './TarjetaProducto';

// Tarjeta de los layouts de grilla del catálogo (RF-01.4): la misma tarjeta editorial de la landing
export default function ProductCardGrid({ producto }) {
  return <TarjetaProducto producto={producto} />;
}
