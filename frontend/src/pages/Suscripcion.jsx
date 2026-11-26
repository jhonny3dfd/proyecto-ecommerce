import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import clienteAxios from '../components/auth/axiosConfig';
import Header from '../components/header/header';
import { Cargando } from '../components/carga/Esqueleto';
import { EsqueletoLista } from '../components/carga/EsqueletosPanel';
import { beneficiosDelPlan, formatoPesos } from '../utils/suscripciones';
import '../components/Checkout.css';
import './Suscripcion.css';

// Planes de suscripción (pedido de un cliente, opcional y apagado por defecto). Con el módulo apagado el servidor
// responde 404 y la página avisa que no está disponible
export default function Suscripcion() {
  const [estado, setEstado] = useState({ cargando: true, planes: [], diasAviso: 3, noDisponible: false, error: '' });
  const conSesion = Boolean(localStorage.getItem('access_token'));

  useEffect(() => {
    clienteAxios.get('ventas/suscripciones/planes/')
      .then(({ data }) => setEstado({ cargando: false, planes: data.planes || [], diasAviso: data.dias_aviso ?? 3, noDisponible: false, error: '' }))
      .catch(error => setEstado({
        cargando: false, planes: [], diasAviso: 3, noDisponible: error.response?.status === 404,
        error: error.response?.status === 404 ? '' : 'No se pudieron cargar los planes. Inténtalo de nuevo en un momento.'
      }));
  }, []);

  return (
    <>
      <Header />
      <main id="contenido" tabIndex={-1} className="checkout-main">
        <div className="checkout-card suscripcion">
          <span className="antetitulo">Suscripciones</span>
          <h1 className="checkout-titulo">Recíbelo cada cierto tiempo</h1>

          {estado.cargando ? (
            <Cargando texto="Cargando planes..."><EsqueletoLista /></Cargando>
          ) : estado.noDisponible ? (
            <p className="checkout-aviso checkout-aviso--advertencia">
              Esta tienda no ofrece suscripciones por ahora. <Link to="/catalogo">Ver el catálogo</Link>
            </p>
          ) : estado.error ? (
            <p role="alert" className="checkout-aviso checkout-aviso--error">{estado.error}</p>
          ) : (
            <>
              <p className="suscripcion-intro texto-secundario">
                Elige un plan y lo que quieres recibir. {estado.diasAviso === 1 ? 'Un día' : `${estado.diasAviso} días`} antes
                de cada entrega te enviamos un correo para que la pagues. Puedes pausarla, saltar una entrega, cambiar lo
                que recibes o cancelarla cuando quieras desde tu cuenta.
              </p>
              {conSesion && (
                <p className="suscripcion-intro"><Link to="/mis-suscripciones">Ver mis suscripciones</Link></p>
              )}

              {estado.planes.length === 0 ? (
                <p className="texto-secundario">Todavía no hay planes disponibles. Vuelve pronto.</p>
              ) : (
                <ul className="lista-sin-estilo suscripcion-planes">
                  {estado.planes.map(plan => {
                    const beneficios = beneficiosDelPlan(plan);
                    return (
                      <li key={plan.id} className="suscripcion-plan">
                        <article aria-labelledby={`plan-${plan.id}-nombre`} className="suscripcion-plan-contenido">
                          <h2 id={`plan-${plan.id}-nombre`} className="suscripcion-plan-nombre">{plan.nombre}</h2>
                          {plan.descripcion && <p className="texto-secundario suscripcion-plan-descripcion">{plan.descripcion}</p>}
                          <p className="suscripcion-plan-precio">
                            <span className="suscripcion-plan-monto">{formatoPesos(plan.precio)}</span> por entrega
                          </p>
                          <p className="texto-secundario suscripcion-plan-frecuencia">
                            {plan.frecuencia_texto} · {plan.unidades === 1 ? '1 unidad' : `${plan.unidades} unidades`}
                            {!plan.envio_gratis && ' · más el despacho'}
                          </p>
                          {beneficios.length > 0 && (
                            <ul className="suscripcion-plan-beneficios">
                              {beneficios.map(beneficio => <li key={beneficio}>{beneficio}</li>)}
                            </ul>
                          )}
                          <Link to={`/suscripcion/${plan.id}`} className="boton boton-primario suscripcion-plan-boton"
                            aria-label={`Suscribirme a ${plan.nombre}`}>
                            Suscribirme
                          </Link>
                        </article>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
