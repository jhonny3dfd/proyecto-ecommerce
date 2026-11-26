// Datos para la factura cuando se compra (o cotiza) como empresa. Lo controla quien lo usa: recibe los datos,
// los errores por campo y avisa cada cambio con onChange(campo, valor)
const CAMPOS = [
  { campo: 'razon_social', etiqueta: 'Razón social', autoComplete: 'organization', maxLength: 150,
    placeholder: 'Ej: Comercial Andes SpA' },
  { campo: 'rut', etiqueta: 'RUT de la empresa', maxLength: 12, placeholder: 'Ej: 76.123.456-0' },
  { campo: 'giro', etiqueta: 'Giro', maxLength: 120, placeholder: 'Ej: Venta de artículos de regalo' },
  { campo: 'direccion', etiqueta: 'Dirección comercial', autoComplete: 'street-address', maxLength: 255,
    placeholder: 'Ej: Av. Providencia 1234, Providencia' },
  { campo: 'correo', etiqueta: 'Correo para la factura', tipo: 'email', autoComplete: 'email', maxLength: 254,
    placeholder: 'Ej: facturas@miempresa.cl' }
];

export default function DatosEmpresa({ id, datos, errores = {}, onChange }) {
  return (
    <div className="datos-empresa">
      {CAMPOS.map(({ campo, etiqueta, tipo = 'text', autoComplete, maxLength, placeholder }) => {
        const idCampo = `${id}-${campo}`;
        const idError = `${idCampo}-error`;
        return (
          <div key={campo} className="checkout-campo">
            <label htmlFor={idCampo}>{etiqueta}</label>
            <input
              id={idCampo}
              type={tipo}
              autoComplete={autoComplete}
              maxLength={maxLength}
              value={datos[campo] || ''}
              onChange={(e) => onChange(campo, e.target.value)}
              placeholder={placeholder}
              required
              aria-invalid={errores[campo] ? true : undefined}
              aria-describedby={errores[campo] ? idError : undefined}
            />
            {errores[campo] && (
              <p id={idError} role="alert" className="checkout-error-campo">{errores[campo]}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}
