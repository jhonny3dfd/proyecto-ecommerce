import { useId } from 'react';

const CAMPOS = [
  { nombre: 'password', etiqueta: 'Nueva contraseña' },
  { nombre: 'password2', etiqueta: 'Repite la nueva contraseña' },
];

// La nueva contraseña y su confirmación, con la ayuda de las reglas y el error de cada campo asociados al input
export default function CamposContrasenaNueva({ valores, errores, onChange }) {
  const id = useId();

  return CAMPOS.map(({ nombre, etiqueta }) => {
    const mensaje = errores[nombre];
    const idCampo = `${id}-${nombre}`;
    const describe = [nombre === 'password' ? `${id}-ayuda` : '', mensaje ? `${idCampo}-error` : '']
      .filter(Boolean).join(' ');
    return (
      <div className="auth-campo" key={nombre}>
        <label htmlFor={idCampo}>{etiqueta}</label>
        <input
          id={idCampo}
          type="password"
          name={nombre}
          autoComplete="new-password"
          value={valores[nombre]}
          onChange={onChange}
          required
          aria-invalid={mensaje ? true : undefined}
          aria-describedby={describe || undefined}
        />
        {nombre === 'password' && (
          <p id={`${id}-ayuda`} className="auth-campo-ayuda">
            Al menos 8 caracteres, que no sean solo números ni una contraseña común.
          </p>
        )}
        {mensaje && <p id={`${idCampo}-error`} className="auth-campo-error">{mensaje}</p>}
      </div>
    );
  });
}
