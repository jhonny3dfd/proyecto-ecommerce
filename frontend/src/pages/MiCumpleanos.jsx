import { useEffect, useId, useState } from 'react';
import clienteAxios from '../components/auth/axiosConfig';
import AuthLayout from '../components/auth/AuthLayout';
import { MESES } from '../utils/suscripciones';
import './MiCumpleanos.css';
import { Navigate } from 'react-router-dom';
import useConfiguracionTienda from '../hooks/useConfiguracionTienda';

export default function MiCumpleanos() {
  const config = useConfiguracionTienda();
  if (!config) return <p role="status">Cargando configuración…</p>;
  if (!config.suscripciones_activas) return <Navigate to="/" replace />;
  return <FormularioCumpleanos />;
}

function FormularioCumpleanos() {
  const id = useId();
  const [fecha, setFecha] = useState(null);
  const [errorCarga, setErrorCarga] = useState('');
  const [error, setError] = useState('');
  const [exito, setExito] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [intento, setIntento] = useState(0);
  useEffect(() => {
    let vigente = true;
    clienteAxios.get('usuarios/cumpleanos/')
      .then(({ data }) => { if (vigente) { setFecha({ dia: data.dia ?? '', mes: data.mes ?? '' }); setErrorCarga(''); } })
      .catch(() => { if (vigente) setErrorCarga('No pudimos cargar tu cumpleaños. Inténtalo nuevamente.'); });
    return () => { vigente = false; };
  }, [intento]);

  async function guardar(datos) {
    setGuardando(true); setError(''); setExito('');
    try {
      const { data } = await clienteAxios.patch('usuarios/cumpleanos/', datos);
      setFecha({ dia: data.dia ?? '', mes: data.mes ?? '' });
      setExito(data.dia === null ? 'Tu cumpleaños se eliminó.' : 'Tu cumpleaños quedó guardado.');
    } catch (fallo) {
      const datos = fallo.response?.data;
      setError(datos?.dia?.[0] || datos?.mes?.[0] || 'No pudimos guardar la fecha. Revisa el día y el mes.');
    } finally { setGuardando(false); }
  }

  return <AuthLayout><div className="auth-tarjeta">
    <span className="antetitulo">Mi cuenta</span><h1 className="auth-titulo">Mi cumpleaños</h1>
    <p className="auth-texto" id={`${id}-ayuda`}>Es opcional. Solo guardamos el día y el mes, sin el año de nacimiento.
      Puedes cambiarlo o eliminarlo cuando quieras. Si tienes una suscripción vigente, la tienda podrá preparar un regalo.</p>
    {errorCarga && <p role="alert" className="auth-aviso auth-aviso--error">{errorCarga}{' '}
      <button type="button" className="boton-texto" onClick={() => setIntento(i => i + 1)}>Reintentar</button></p>}
    {!fecha && !errorCarga && <p role="status">Cargando tu cumpleaños…</p>}
    {fecha && <form className="auth-formulario" aria-describedby={`${id}-ayuda`} onSubmit={e => {
      e.preventDefault(); guardar({ dia: fecha.dia === '' ? null : Number(fecha.dia), mes: fecha.mes === '' ? null : Number(fecha.mes) });
    }}>
      <div className="cumpleanos-campos">
        <div className="auth-campo"><label htmlFor={`${id}-dia`}>Día</label>
          <input id={`${id}-dia`} type="number" min="1" max="31" inputMode="numeric" value={fecha.dia}
            aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined}
            onChange={e => { setFecha(f => ({ ...f, dia: e.target.value })); setExito(''); setError(''); }} disabled={guardando} /></div>
        <div className="auth-campo"><label htmlFor={`${id}-mes`}>Mes</label>
          <select id={`${id}-mes`} value={fecha.mes} aria-invalid={error ? true : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            onChange={e => { setFecha(f => ({ ...f, mes: e.target.value })); setExito(''); setError(''); }} disabled={guardando}>
            <option value="">Sin indicar</option>
            {MESES.map((mes, i) => <option key={mes} value={i + 1}>{mes}</option>)}
          </select></div>
      </div>
      {error && <p role="alert" id={`${id}-error`} className="auth-aviso auth-aviso--error">{error}</p>}
      {exito && <p role="status" className="auth-aviso auth-aviso--exito">{exito}</p>}
      <button type="submit" className="boton boton-primario auth-enviar" disabled={guardando}>
        {guardando ? 'Guardando…' : 'Guardar cumpleaños'}</button>
      <button type="button" className="boton boton-secundario" disabled={guardando}
        onClick={() => guardar({ dia: null, mes: null })}>Eliminar cumpleaños</button>
    </form>}
  </div></AuthLayout>;
}
