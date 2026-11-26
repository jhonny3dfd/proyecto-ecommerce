import { useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Header from './header/header';
import clienteAxios from './auth/axiosConfig';
import './ResultadoCompra.css';

export default function PagoExitoso() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const ordenId = searchParams.get('orden');
  // El pago se aprobó pero la orden quedó para revisión del admin (ej. sin stock):
  // no se le promete el pedido ni se le muestra el motivo interno
  const enRevision = searchParams.get('revision') === '1';
  // El invitado no tiene historial: se le lleva al seguimiento con su número de orden (RF-02.4)
  const usuarioAutenticado = !!localStorage.getItem('access_token');

  useEffect(() => {
    // Limpiar el carrito local y la orden pendiente una vez que el pago fue exitoso
    localStorage.removeItem('carrito_local');
    localStorage.removeItem('orden_pendiente_pago');
    window.dispatchEvent(new Event('carritoActualizado'));
    if (usuarioAutenticado) {
      clienteAxios.post('ventas/carrito/', { items: [] }).catch(() => {});
    }
  }, [usuarioAutenticado]);

  return (
    <>
      <Header />

      <main tabIndex={-1} id="contenido" className="resultado-main">
        <section className="resultado">
          <div className="resultado-icono resultado-icono--exito" aria-hidden="true">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
          </div>

          <span className="antetitulo">Gracias por tu compra</span>
          <h1 className="resultado-titulo">{enRevision ? '¡Pago recibido!' : '¡Pago exitoso!'}</h1>
          <p className="resultado-texto">
            {enRevision
              ? 'Recibimos tu pago. La tienda revisará tu pedido antes de prepararlo y se pondrá en contacto contigo.'
              : 'Tu compra se ha procesado correctamente.'}
          </p>

          {ordenId && (
            <div className="resultado-orden">
              <p className="resultado-orden-etiqueta">Número de orden</p>
              <p className="resultado-orden-numero">#{ordenId}</p>
            </div>
          )}

          <p className="resultado-nota">
            Te enviamos la confirmación a tu correo. Guarda tu número de orden: con él y el correo que usaste en la compra puedes consultar el estado de tu pedido en la sección de seguimiento.
          </p>

          <div className="resultado-acciones">
            <button type="button" className="boton boton-primario" onClick={() => navigate('/catalogo')}>
              Seguir comprando
            </button>
            <button
              type="button"
              className="boton boton-contorno"
              onClick={() => navigate(usuarioAutenticado ? '/mis-pedidos' : `/seguimiento${ordenId ? `?orden=${encodeURIComponent(ordenId)}` : ''}`)}
            >
              {usuarioAutenticado ? 'Ver mis pedidos' : 'Seguir mi pedido'}
            </button>
          </div>
        </section>
      </main>
    </>
  );
}
