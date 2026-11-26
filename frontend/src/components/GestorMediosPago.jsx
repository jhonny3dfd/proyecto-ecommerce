import { useState, useEffect } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoLista } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

// Textos de la interfaz para los valores que guarda el backend
const ETIQUETAS_OPCION = {
  INTEGRACION: 'Integración (pruebas, sin cobros reales)',
  PRODUCCION: 'Producción (cobros reales)',
  // Plazo para pagar una transferencia (plazo_pago_horas)
  12: '12 horas',
  24: '24 horas',
  48: '48 horas',
  72: '72 horas'
};

const ESTILOS_ESTADO = {
  disponible: { backgroundColor: '#f0fdf4', border: '1px solid #86efac', color: '#166534' },
  incompleto: { backgroundColor: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e' },
  deshabilitado: { backgroundColor: 'var(--color-secondary)', border: '1px solid var(--color-border)', color: 'var(--color-text)' }
};

const ESTILOS_AVISO = {
  error: { backgroundColor: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b' },
  exito: { backgroundColor: '#f0fdf4', border: '1px solid #86efac', color: '#166534' }
};

const estiloCampo = { width: '100%', padding: '10px', boxSizing: 'border-box', border: '1px solid var(--color-control-border)', borderRadius: '4px' };
const estiloEtiqueta = { display: 'block', fontSize: '0.9rem', fontWeight: 'bold', marginBottom: '5px', color: 'var(--color-text)' };

const formularioDe = (medio) => ({ habilitado: medio.habilitado, datos: { ...medio.datos } });

// Ej. la API key de Transbank solo es obligatoria en producción
const esObligatorio = (campo, datos) => campo.obligatorio
  && (!campo.obligatorio_si || datos[campo.obligatorio_si[0]] === campo.obligatorio_si[1]);

function EstadoMedio({ medio }) {
  const etiquetas = Object.fromEntries(medio.campos.map(c => [c.nombre, c.etiqueta]));
  if (!medio.integracion_lista) {
    return (
      <p id={`estado-${medio.codigo}`} style={{ ...ESTILOS_ESTADO.deshabilitado, padding: '8px 12px', borderRadius: '6px', margin: '0 0 15px 0' }}>
        Integración en desarrollo: todavía no se puede ofrecer a los compradores. Puedes dejar cargadas sus credenciales.
      </p>
    );
  }
  if (medio.disponible) {
    return <p style={{ ...ESTILOS_ESTADO.disponible, padding: '8px 12px', borderRadius: '6px', margin: '0 0 15px 0' }}>Disponible: los compradores lo ven en el checkout.</p>;
  }
  if (medio.habilitado) {
    return (
      <p style={{ ...ESTILOS_ESTADO.incompleto, padding: '8px 12px', borderRadius: '6px', margin: '0 0 15px 0' }}>
        Habilitado, pero incompleto: falta {medio.faltantes.map(f => etiquetas[f]).join(', ')}. No se muestra a los compradores.
      </p>
    );
  }
  return <p style={{ ...ESTILOS_ESTADO.deshabilitado, padding: '8px 12px', borderRadius: '6px', margin: '0 0 15px 0' }}>Deshabilitado: no se muestra a los compradores.</p>;
}

// RN-02: el admin habilita cada medio y carga sus datos; las credenciales llegan enmascaradas
// y, si se devuelven sin cambios, el backend conserva las anteriores.
export default function GestorMediosPago() {
  const [medios, setMedios] = useState([]);
  const [formularios, setFormularios] = useState({});
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');
  const [guardando, setGuardando] = useState(null);
  // { [codigo]: { tipo, texto, errores } }
  const [avisos, setAvisos] = useState({});

  useEffect(() => {
    clienteAxios.get('ventas/admin/medios-pago/')
      .then(({ data }) => {
        setMedios(data);
        setFormularios(Object.fromEntries(data.map(medio => [medio.codigo, formularioDe(medio)])));
      })
      .catch((error) => {
        console.error('Error al cargar los medios de pago:', error);
        setErrorCarga('No se pudieron cargar los medios de pago.');
      })
      .finally(() => setCargando(false));
  }, []);

  const editar = (codigo, cambios) => setFormularios(actual => ({
    ...actual,
    [codigo]: { ...actual[codigo], ...cambios }
  }));

  const editarDato = (codigo, campo, valor) => setFormularios(actual => ({
    ...actual,
    [codigo]: { ...actual[codigo], datos: { ...actual[codigo].datos, [campo]: valor } }
  }));

  const handleGuardar = async (medio) => {
    setGuardando(medio.codigo);
    setAvisos(actual => ({ ...actual, [medio.codigo]: null }));
    try {
      const { data } = await clienteAxios.put(`ventas/admin/medios-pago/${medio.codigo.toLowerCase()}/`, formularios[medio.codigo]);
      setMedios(actual => actual.map(m => (m.codigo === data.codigo ? data : m)));
      setFormularios(actual => ({ ...actual, [data.codigo]: formularioDe(data) }));
      setAvisos(actual => ({ ...actual, [data.codigo]: { tipo: 'exito', texto: `${data.nombre}: cambios guardados.` } }));
    } catch (error) {
      const errores = error.response?.data?.datos || {};
      setAvisos(actual => ({
        ...actual,
        [medio.codigo]: {
          tipo: 'error',
          texto: error.response?.data?.detail || `No se pudo guardar ${medio.nombre}. Revisa los campos marcados.`,
          errores
        }
      }));
    } finally {
      setGuardando(null);
    }
  };

  if (cargando) return <Cargando texto="Cargando medios de pago..."><EsqueletoLista /></Cargando>;
  if (errorCarga) return <p role="alert" style={{ ...ESTILOS_AVISO.error, padding: '10px 12px', borderRadius: '6px' }}>{errorCarga}</p>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '640px' }}>
      <p style={{ margin: 0, color: 'var(--color-muted)', fontSize: '0.95rem' }}>
        Los compradores solo ven los medios habilitados y con todos sus datos obligatorios. Las credenciales se guardan
        cifradas y aquí solo se muestran sus últimos caracteres.
      </p>

      {medios.map(medio => {
        const formulario = formularios[medio.codigo];
        const aviso = avisos[medio.codigo];
        const errores = aviso?.errores || {};
        return (
          <fieldset key={medio.codigo} style={{ border: '1px solid var(--color-border)', borderRadius: '8px', padding: '20px', margin: 0 }}>
            <legend style={{ fontWeight: 'bold', fontSize: '1.1rem', padding: '0 6px', color: 'var(--color-text)' }}>{medio.nombre}</legend>

            <EstadoMedio medio={medio} />

            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '15px', cursor: medio.integracion_lista ? 'pointer' : 'not-allowed', color: medio.integracion_lista ? 'var(--color-text)' : 'var(--color-muted)' }}>
              <input
                type="checkbox"
                checked={formulario.habilitado && medio.integracion_lista}
                disabled={!medio.integracion_lista}
                aria-describedby={medio.integracion_lista ? undefined : `estado-${medio.codigo}`}
                onChange={(e) => editar(medio.codigo, { habilitado: e.target.checked })}
                style={{ width: '18px', height: '18px' }}
              />
              Habilitar {medio.nombre}
            </label>

            {medio.campos.map(campo => {
              const id = `medio-${medio.codigo}-${campo.nombre}`;
              const idAyuda = `${id}-ayuda`;
              const idError = `${id}-error`;
              const obligatorio = esObligatorio(campo, formulario.datos);
              const valor = formulario.datos[campo.nombre] || '';
              return (
                <div key={campo.nombre} style={{ marginBottom: '15px' }}>
                  <label htmlFor={id} style={estiloEtiqueta}>
                    {campo.etiqueta}{obligatorio ? ' (obligatorio)' : ' (opcional)'}
                  </label>
                  {campo.opciones.length > 0 ? (
                    <select
                      id={id}
                      value={valor}
                      onChange={(e) => editarDato(medio.codigo, campo.nombre, e.target.value)}
                      aria-invalid={Boolean(errores[campo.nombre])}
                      aria-describedby={errores[campo.nombre] ? idError : undefined}
                      style={{ ...estiloCampo, backgroundColor: 'var(--color-surface)' }}
                    >
                      <option value="">-- Selecciona --</option>
                      {campo.opciones.map(opcion => (
                        <option key={opcion} value={opcion}>{ETIQUETAS_OPCION[opcion] || opcion}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      id={id}
                      type={campo.formato === 'correo' ? 'email' : 'text'}
                      // Teclado numérico para la cuenta en el celular; el servidor valida el formato
                      inputMode={campo.formato === 'numero_cuenta' ? 'numeric' : undefined}
                      maxLength={500}
                      value={valor}
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(e) => editarDato(medio.codigo, campo.nombre, e.target.value)}
                      // La credencial enmascarada se selecciona entera para reemplazarla de una vez
                      onFocus={campo.secreto ? (e) => e.target.select() : undefined}
                      aria-invalid={Boolean(errores[campo.nombre])}
                      aria-describedby={[campo.secreto ? idAyuda : '', errores[campo.nombre] ? idError : ''].filter(Boolean).join(' ') || undefined}
                      style={estiloCampo}
                    />
                  )}
                  {campo.secreto && (
                    <p id={idAyuda} style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--color-muted)' }}>
                      Por seguridad solo se muestran los últimos caracteres. Escribe una nueva para reemplazarla o deja el campo vacío para borrarla.
                    </p>
                  )}
                  {errores[campo.nombre] && (
                    <p id={idError} style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#991b1b' }}>{errores[campo.nombre]}</p>
                  )}
                </div>
              );
            })}

            {aviso && (
              <p
                role={aviso.tipo === 'error' ? 'alert' : 'status'}
                style={{ ...ESTILOS_AVISO[aviso.tipo], padding: '8px 12px', borderRadius: '6px', margin: '0 0 15px 0' }}
              >
                {aviso.texto}
              </p>
            )}

            <button
              type="button"
              onClick={() => handleGuardar(medio)}
              disabled={guardando === medio.codigo}
              style={{ padding: '10px 18px', backgroundColor: 'var(--color-primary)', color: 'white', border: 'none', borderRadius: '6px', cursor: guardando === medio.codigo ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}
            >
              {guardando === medio.codigo && <Spinner />}{guardando === medio.codigo ? 'Guardando...' : `Guardar ${medio.nombre}`}
            </button>
          </fieldset>
        );
      })}
    </div>
  );
}
