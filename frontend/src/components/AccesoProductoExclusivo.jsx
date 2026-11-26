import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import clienteAxios from './auth/axiosConfig';

export function AvisoProductoExclusivo() {
  return <p className="producto-exclusivo-aviso">Disponible con un plan vigente. <Link to="/suscripcion">Suscripción</Link></p>;
}

export default function AccesoProductoExclusivo({ producto, children }) {
  const token = localStorage.getItem('access_token');
  const [consulta, setConsulta] = useState(null);
  const [intento, setIntento] = useState(0);
  useEffect(() => {
    if (!producto.solo_suscriptores || !token) return;
    let vigente = true;
    clienteAxios.get('ventas/suscripciones/acceso-exclusivos/')
      .then(({ data }) => { if (vigente) setConsulta({ id: producto.id, token, planes: data.planes_vigentes || [] }); })
      .catch(() => { if (vigente) setConsulta({ id: producto.id, token, error: true }); });
    return () => { vigente = false; };
  }, [producto.id, producto.solo_suscriptores, token, intento]);
  if (!producto.solo_suscriptores) return children;
  const actual = consulta?.id === producto.id && consulta?.token === token ? consulta : null;
  if (token && !actual) return <p role="status">Comprobando el acceso de tu suscripción…</p>;
  if (actual?.error) return <p role="alert">No pudimos comprobar tu suscripción.{' '}
    <button type="button" className="boton-texto" onClick={() => setIntento(i => i + 1)}>Reintentar</button></p>;
  const permitidos = producto.planes_suscripcion || [];
  const puedeComprar = actual?.planes?.some(plan => !permitidos.length || permitidos.includes(plan));
  if (puedeComprar) return children;
  return <div className="producto-exclusivo-acceso" role="note" aria-label="Acceso a producto exclusivo">
    <p>Para comprar este producto necesitas una suscripción vigente de uno de sus planes permitidos.</p>
    <Link to="/suscripcion" className="boton boton-primario">Ver planes de Suscripción</Link>
  </div>;
}
