// Logo de cada medio de pago en el botón del checkout. Los de Webpay y Mercado Pago son los archivos oficiales de
// cada marca, sin modificar (la guía de Mercado Pago prohíbe editar el SVG): van sobre una placa blanca para que se
// vean igual con cualquier tema. La transferencia no tiene marca: un ícono de banco del color del texto.
// Son decorativos (alt=""): el botón ya dice "Pagar con Webpay (Transbank)".
import logoWebpay from '../assets/medios-pago/webpay.png';
import logoMercadoPago from '../assets/medios-pago/mercado-pago.svg';

const LOGOS = {
  TRANSBANK: logoWebpay,
  MERCADO_PAGO: logoMercadoPago,
};

export default function LogoMedioPago({ codigo }) {
  if (LOGOS[codigo]) {
    return (
      <span className={`checkout-pagar-logo checkout-pagar-logo--${codigo.toLowerCase().replace('_', '-')}`}>
        <img src={LOGOS[codigo]} alt="" />
      </span>
    );
  }
  if (codigo === 'TRANSFERENCIA') {
    return (
      <svg className="checkout-pagar-icono" aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3 9.5 12 4l9 5.5" />
        <path d="M5 10v8M9.5 10v8M14.5 10v8M19 10v8" />
        <path d="M3 20h18" />
      </svg>
    );
  }
  return null;
}
