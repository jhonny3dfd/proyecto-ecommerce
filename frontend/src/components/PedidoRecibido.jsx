import { useSearchParams, useNavigate, useLocation } from 'react-router-dom';
import Header from './header/header';
import './ResultadoCompra.css';

// Orden creada sin pasar por una pasarela (ej. transferencia, RF-02.2): queda Pendiente
// hasta que la tienda confirme el pago. El carrito ya lo vació el checkout.
export default function PedidoRecibido() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const ordenId = searchParams.get('orden');
  // Transferencia: datos bancarios, monto y referencia que envió el checkout. Sobreviven a una recarga
  // (historial del navegador), pero no si se abre el enlace en otra pestaña: ahí quedan en el correo.
  const instrucciones = useLocation().state?.instrucciones || null;
  // El invitado no tiene historial: se le lleva al seguimiento con su número de orden (RF-02.4)
  const usuarioAutenticado = !!localStorage.getItem('access_token');

  return (
    <>
      <Header />

      <main tabIndex={-1} id="contenido" className="resultado-main">
        <section className="resultado">
          <div className="resultado-icono resultado-icono--pendiente" aria-hidden="true">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7v5l3 2" />
            </svg>
          </div>

          <span className="antetitulo">Pendiente de pago</span>
          <h1 className="resultado-titulo">¡Pedido recibido!</h1>
          <p className="resultado-texto">
            Tu pedido quedó registrado y está <strong>pendiente de pago</strong>. Cuando la tienda confirme
            el pago, lo preparará para el envío.
          </p>

          {ordenId && (
            <div className="resultado-orden">
              <p className="resultado-orden-etiqueta">Número de orden</p>
              <p className="resultado-orden-numero">#{ordenId}</p>
            </div>
          )}

          {instrucciones && (
            <div className="resultado-transferencia">
              <h2>Datos para transferir</h2>
              <p>
                Transfiere <strong>${Number(instrucciones.monto).toLocaleString('es-CL')}</strong> a esta cuenta e indica
                como referencia <strong>{instrucciones.referencia}</strong>.
              </p>
              {instrucciones.vence && (
                <p className="resultado-plazo">
                  Tienes hasta el <strong>{new Date(instrucciones.vence).toLocaleString('es-CL', { dateStyle: 'long', timeStyle: 'short' })}</strong> para
                  transferir; después el pedido se cancela automáticamente.
                </p>
              )}
              <dl className="resultado-datos">
                {instrucciones.datos.map(dato => (
                  <div key={dato.etiqueta} style={{ display: 'contents' }}>
                    <dt>{dato.etiqueta}</dt>
                    <dd>{dato.valor}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          <p className="resultado-nota">
            {instrucciones
              ? 'También te enviamos estos datos y el resumen de tu compra a tu correo. '
              : 'Te enviamos el resumen de tu compra a tu correo (si pagas por transferencia, ahí están los datos de la cuenta). '}
            Guarda tu número de orden: con él y el correo que usaste en la compra puedes consultar el estado de tu pedido en la sección de seguimiento.
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
