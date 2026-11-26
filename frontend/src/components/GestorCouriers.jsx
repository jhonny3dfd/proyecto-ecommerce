import { useState, useEffect } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

const ESTILOS_AVISO = {
  error: { backgroundColor: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b' },
  exito: { backgroundColor: '#f0fdf4', border: '1px solid #86efac', color: '#166534' },
  incompleto: { backgroundColor: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e' }
};

const estiloCampo = { width: '100%', padding: '10px', boxSizing: 'border-box', border: '1px solid var(--color-control-border)', borderRadius: '4px' };
const estiloEtiqueta = { display: 'block', fontSize: '0.9rem', fontWeight: 'bold', marginBottom: '5px', color: 'var(--color-text)' };
const estiloAyuda = { margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--color-muted)' };

// Textos de la interfaz para los valores que guarda el backend
const ETIQUETAS_OPCION = {
  PRUEBAS: 'Pruebas (sandbox, sin envíos reales)',
  PRODUCCION: 'Producción (envíos reales con tu contrato)'
};

// Igual que en los medios de pago: ej. la TCC solo es obligatoria en producción
const esObligatorio = (campo, datos) => campo.obligatorio
  && (!campo.obligatorio_si || datos[campo.obligatorio_si[0]] === campo.obligatorio_si[1]);

function textoObligatorio(campo, obligatorio) {
  if (obligatorio) return ' (obligatorio)';
  if (campo.obligatorio && campo.obligatorio_si?.[1] === 'PRODUCCION') return ' (solo en producción)';
  return ' (opcional)';
}

// RNF-03: las llaves de un courier; llegan enmascaradas y, si se devuelven sin cambios, el backend conserva las
// anteriores. Los datos que no son llaves (ambiente, número de cliente, RUT) se ven completos. Los campos y la
// ayuda los declara cada courier en el backend.
function FormularioCourier({ inicial }) {
  const [config, setConfig] = useState(inicial);
  const [datos, setDatos] = useState(() => ({ ...inicial.datos }));
  const [guardando, setGuardando] = useState(false);
  // { tipo, texto, errores }
  const [aviso, setAviso] = useState(null);
  const { codigo, nombre } = config;

  const handleGuardar = async () => {
    setGuardando(true);
    setAviso(null);
    try {
      const { data } = await clienteAxios.put(`ventas/admin/couriers/${codigo}/`, { datos });
      setConfig(data);
      setDatos({ ...data.datos });
      setAviso({ tipo: 'exito', texto: `Credenciales de ${nombre} guardadas.` });
    } catch (error) {
      setAviso({
        tipo: 'error',
        texto: error.response?.data?.detail || 'No se pudieron guardar las credenciales. Revisa los campos marcados.',
        errores: error.response?.data?.datos || {}
      });
    } finally {
      setGuardando(false);
    }
  };

  const etiquetas = Object.fromEntries(config.campos.map(c => [c.nombre, c.etiqueta]));
  const errores = aviso?.errores || {};

  return (
    <section aria-labelledby={`courier-${codigo}-titulo`} style={{ display: 'flex', flexDirection: 'column', gap: '15px', maxWidth: '640px' }}>
      <h5 id={`courier-${codigo}-titulo`} style={{ margin: 0, fontSize: '1.1rem' }}>{nombre}</h5>
      <p style={{ margin: 0, color: 'var(--color-muted)', fontSize: '0.95rem' }}>
        Con estas llaves la tienda cotiza el despacho, muestra las sucursales y genera la orden de transporte.
        {config.ayuda && ` ${config.ayuda}`} Las llaves se guardan cifradas y aquí solo se muestran sus últimos caracteres.
      </p>

      {config.configuradas
        ? <p style={{ ...ESTILOS_AVISO.exito, padding: '8px 12px', borderRadius: '6px', margin: 0 }}>Configurado: el checkout puede cotizar con {nombre}.</p>
        : (
          <p style={{ ...ESTILOS_AVISO.incompleto, padding: '8px 12px', borderRadius: '6px', margin: 0 }}>
            Falta {config.faltantes.map(f => etiquetas[f]).join(', ')}: sin {config.faltantes.length > 1 ? 'esos datos' : 'ese dato'} el checkout no ofrece {nombre}.
          </p>
        )}

      {config.campos.map(campo => {
        const id = `courier-${codigo}-${campo.nombre}`;
        const idAyuda = `${id}-ayuda`;
        const idError = `${id}-error`;
        const valor = datos[campo.nombre] || '';
        const editar = (e) => setDatos(actual => ({ ...actual, [campo.nombre]: e.target.value }));
        // Al pasar a producción, la tienda despacha con sus propios datos
        const ayudaProduccion = campo.nombre === 'ambiente' && valor === 'PRODUCCION';
        const tieneAyuda = campo.secreto || ayudaProduccion;
        const describidoPor = [tieneAyuda ? idAyuda : '', errores[campo.nombre] ? idError : ''].filter(Boolean).join(' ') || undefined;
        return (
          <div key={campo.nombre}>
            <label htmlFor={id} style={estiloEtiqueta}>
              {campo.etiqueta}{textoObligatorio(campo, esObligatorio(campo, datos))}
            </label>
            {campo.opciones.length > 0 ? (
              <select
                id={id}
                value={valor}
                onChange={editar}
                aria-invalid={Boolean(errores[campo.nombre])}
                aria-describedby={describidoPor}
                style={{ ...estiloCampo, backgroundColor: 'var(--color-surface)' }}
              >
                {!valor && <option value="">-- Selecciona --</option>}
                {campo.opciones.map(opcion => (
                  <option key={opcion} value={opcion}>{ETIQUETAS_OPCION[opcion] || opcion}</option>
                ))}
              </select>
            ) : (
              <input
                id={id}
                type="text"
                // Teclado numérico en el celular; el servidor valida el formato
                inputMode={campo.formato === 'digitos' ? 'numeric' : undefined}
                maxLength={500}
                value={valor}
                autoComplete="off"
                spellCheck={false}
                onChange={editar}
                // La llave enmascarada se selecciona entera para reemplazarla de una vez
                onFocus={campo.secreto ? (e) => e.target.select() : undefined}
                aria-invalid={Boolean(errores[campo.nombre])}
                aria-describedby={describidoPor}
                style={estiloCampo}
              />
            )}
            {campo.secreto && (
              <p id={idAyuda} style={estiloAyuda}>
                Por seguridad solo se muestran los últimos caracteres. Escribe una nueva para reemplazarla o deja el campo vacío para borrarla.
              </p>
            )}
            {ayudaProduccion && (
              <p id={idAyuda} style={estiloAyuda}>
                Usa las llaves de producción que te entregó {nombre}. Cada envío se cobra a tu tarjeta de cliente, y el
                remitente y la dirección de devolución son el nombre de la tienda, el teléfono comercial, el correo de
                contacto y la dirección del local que cargaste en Configuración: revisa que estén completos.
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
          style={{ ...ESTILOS_AVISO[aviso.tipo], padding: '8px 12px', borderRadius: '6px', margin: 0 }}
        >
          {aviso.texto}
        </p>
      )}

      <div>
        <button
          type="button"
          onClick={handleGuardar}
          disabled={guardando}
          style={{ padding: '10px 18px', backgroundColor: 'var(--color-primary)', color: 'white', border: 'none', borderRadius: '6px', cursor: guardando ? 'not-allowed' : 'pointer', fontWeight: 'bold' }}
        >
          {guardando && <Spinner />}{guardando ? 'Guardando...' : `Guardar credenciales de ${nombre}`}
        </button>
      </div>
    </section>
  );
}

// RF-02.3: un formulario por cada courier que la tienda puede usar (Chilexpress, Starken…)
export default function GestorCouriers() {
  const [couriers, setCouriers] = useState(null);
  const [errorCarga, setErrorCarga] = useState('');

  useEffect(() => {
    clienteAxios.get('ventas/admin/couriers/')
      .then(({ data }) => setCouriers(data))
      .catch((error) => {
        console.error('Error al cargar los couriers:', error);
        setErrorCarga('No se pudieron cargar las credenciales de los couriers.');
      });
  }, []);

  if (errorCarga) return <p role="alert" style={{ ...ESTILOS_AVISO.error, padding: '10px 12px', borderRadius: '6px' }}>{errorCarga}</p>;
  if (!couriers) return <Cargando texto="Cargando credenciales de los couriers..."><EsqueletoFormulario campos={3} /></Cargando>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {couriers.map(courier => <FormularioCourier key={courier.codigo} inicial={courier} />)}
    </div>
  );
}
