import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoFormulario } from '../components/carga/EsqueletosPanel';
import Spinner from '../components/carga/Spinner';
import { fechaLarga, formatoPesos, nombreMedioPago } from '../utils/suscripciones';
import '../components/Checkout.css';
import './Suscripcion.css';

// "Pagar esta entrega" (enlace del aviso de cobro de una suscripción): el pedido del ciclo ya existe, Pendiente; aquí
// se inicia su pago con el medio de la suscripción. Si ya se pagó o se canceló, se avisa
export default function PagarEntrega() {
  const { ordenId } = useParams();
  const navigate = useNavigate();
  const conSesion = Boolean(localStorage.getItem('access_token'));
  const [estado, setEstado] = useState({ cargando: conSesion, suscripcion: null, sinSesion: !conSesion, error: '' });
  const [pagando, setPagando] = useState(false);
  const [error, setError] = useState('');

  const irALogin = () => {
    localStorage.setItem('url_anterior_login', window.location.pathname);
    navigate('/login');
  };

  useEffect(() => {
    if (!conSesion) return;
    clienteAxios.get('ventas/suscripciones/mias/')
      .then(({ data }) => {
        const suscripcion = (data.suscripciones || [])
          .find(s => String(s.pedido_pendiente?.orden_id) === String(ordenId) && s.estado !== 'CANCELADA') || null;
        setEstado({ cargando: false, suscripcion, sinSesion: false, error: '' });
      })
      .catch(err => setEstado({
        cargando: false, suscripcion: null, sinSesion: err.response?.status === 401,
        error: err.response?.status === 401 ? '' : 'No se pudo cargar tu pedido. Inténtalo de nuevo.'
      }));
  }, [conSesion, ordenId]);

  const pagar = async () => {
    setPagando(true);
    setError('');
    try {
      const { data } = await clienteAxios.post(`ventas/mis-pedidos/${ordenId}/pagar/`);
      if (data.url_pago) {
        window.location.assign(data.url_pago);
        return;
      }
      navigate(`/pedido-recibido?orden=${encodeURIComponent(data.orden_id)}`, {
        replace: true, state: { instrucciones: data.instrucciones_pago || null }
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo iniciar el pago. Inténtalo de nuevo.');
      setPagando(false);
    }
  };

  const s = estado.suscripcion;
  const pedido = s?.pedido_pendiente;

  return (
    <>
      <Header />
      <main id="contenido" tabIndex={-1} className="checkout-main">
        <div className="checkout-card suscripcion suscripcion-pagar">
          <span className="antetitulo">Suscripción</span>
          <h1 className="checkout-titulo">Pagar mi entrega</h1>

          {estado.sinSesion ? (
            <div className="suscripcion-sin-sesion">
              <p>Inicia sesión con la cuenta de tu suscripción para pagar esta entrega.</p>
              <button type="button" className="boton boton-primario" onClick={irALogin}>Iniciar sesión</button>
            </div>
          ) : estado.cargando ? (
            <Cargando texto="Cargando tu pedido..."><EsqueletoFormulario campos={2} /></Cargando>
          ) : estado.error ? (
            <p role="alert" className="checkout-aviso checkout-aviso--error">{estado.error}</p>
          ) : !s ? (
            <p className="checkout-aviso checkout-aviso--advertencia">
              Este pedido ya no está esperando su pago: puede que ya lo hayas pagado o que se haya cancelado.{' '}
              <Link to="/mis-suscripciones">Ver mis suscripciones</Link>
            </p>
          ) : (
            <div className="checkout-resumen suscripcion-pagar-resumen">
              <div className="checkout-resumen-lineas">
                <div className="checkout-resumen-linea"><span>{s.plan.nombre}</span><span>Pedido #{pedido.orden_id}</span></div>
                <div className="checkout-resumen-linea"><span>{s.plan.unidades} × {s.producto}</span></div>
                <div className="checkout-resumen-linea"><span>Entrega</span><span>{fechaLarga(pedido.ciclo_fecha)}</span></div>
                <div className="checkout-resumen-linea"><span>{s.entrega.texto}</span></div>
              </div>
              <div className="checkout-totales">
                <div className="checkout-total-linea checkout-total-linea--final">
                  <span>Total</span><span>{formatoPesos(pedido.total)}</span>
                </div>
              </div>
              <p className="checkout-ayuda suscripcion-pagar-nota">
                Pagas con {nombreMedioPago(pedido.metodo_pago)}. Tienes hasta el final del {fechaLarga(pedido.ciclo_fecha)};
                si no, esta entrega se cancela y la suscripción sigue con la siguiente.
              </p>
              {error && <p role="alert" className="checkout-aviso checkout-aviso--error">{error}</p>}
              <button type="button" className="boton boton-primario checkout-pagar" onClick={pagar} disabled={pagando}>
                {pagando && <Spinner />}{pagando ? 'Procesando...' : `Pagar ${formatoPesos(pedido.total)}`}
              </button>
              <p className="suscripcion-pagar-volver"><Link to="/mis-suscripciones">Ver mis suscripciones</Link></p>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
