import { useEffect, useId, useState } from 'react';
import clienteAxios from './auth/axiosConfig';

export default function CampoExclusivoProducto({ activo, exclusivo, planes, onChange, disabled }) {
  const id = useId();
  const [disponibles, setDisponibles] = useState([]);
  const [error, setError] = useState('');
  const [intento, setIntento] = useState(0);
  useEffect(() => {
    if (!activo) return;
    let vigente = true;
    clienteAxios.get('ventas/admin/suscripciones/planes/')
      .then(({ data }) => { if (vigente) { setDisponibles(data.planes || []); setError(''); } })
      .catch(() => { if (vigente) setError('No se pudieron cargar los planes. Puedes volver a intentarlo.'); });
    return () => { vigente = false; };
  }, [activo, intento]);
  if (!activo) return null;
  return (
    <fieldset className="campo-exclusivo" disabled={disabled} aria-describedby={`${id}-ayuda`}>
      <legend>Acceso de suscriptores</legend>
      <label><input type="checkbox" checked={exclusivo}
        onChange={e => onChange({ solo_suscriptores: e.target.checked })} /> Solo para suscriptores</label>
      <p id={`${id}-ayuda`}>Se muestra en la tienda, pero solo pueden comprarlo los suscriptores vigentes.</p>
      {exclusivo && <>
        <p>Planes permitidos (opcional). Sin marcar ninguno, se admite cualquier plan vigente.</p>
        {error && <p role="alert">{error} <button type="button" onClick={() => setIntento(i => i + 1)}>Reintentar</button></p>}
        <div role="group" aria-label="Planes permitidos">
          {disponibles.map(plan => <label key={plan.id}>
            <input type="checkbox" checked={planes.includes(plan.id)} onChange={e => onChange({
              planes_suscripcion: e.target.checked ? [...planes, plan.id] : planes.filter(p => p !== plan.id),
            })} /> {plan.nombre}{plan.activo ? '' : ' (inactivo para nuevas suscripciones)'}
          </label>)}
        </div>
      </>}
    </fieldset>
  );
}
