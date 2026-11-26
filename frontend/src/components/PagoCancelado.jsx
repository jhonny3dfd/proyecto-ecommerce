import { useNavigate, useSearchParams } from 'react-router-dom';
import Header from './header/header';
import './ResultadoCompra.css';

export default function PagoCancelado() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const ordenId = searchParams.get('orden');

  return (
    <>
      <Header />

      <main tabIndex={-1} id="contenido" className="resultado-main">
        <section className="resultado">
          <div className="resultado-icono resultado-icono--error" aria-hidden="true">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 7l10 10M17 7L7 17" />
            </svg>
          </div>

          {ordenId && <span className="antetitulo">Orden #{ordenId}</span>}
          <h1 className="resultado-titulo">Pago cancelado</h1>
          <p className="resultado-texto">
            Has anulado el proceso de pago o la transacción fue rechazada.
          </p>

          <p className="resultado-nota">
            No te preocupes, <strong>no se ha realizado ningún cargo en tu cuenta</strong>.
            Tus productos siguen seguros en tu carrito por si deseas intentar la compra nuevamente con otro medio de pago.
          </p>

          <div className="resultado-acciones">
            <button type="button" className="boton boton-primario" onClick={() => navigate('/checkout')}>
              Volver al checkout
            </button>
            <button type="button" className="boton boton-contorno" onClick={() => navigate('/catalogo')}>
              Ir al catálogo
            </button>
          </div>
        </section>
      </main>
    </>
  );
}
