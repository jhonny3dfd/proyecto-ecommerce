import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// RF-02.3: entrega que acuerda la tienda con el comprador (ej. en persona), sin transportista ni dirección del local
const CAMPOS = ['entrega_coordinada_activa', 'costo_entrega_coordinada', 'instrucciones_entrega_coordinada'];

const formularioDe = (configuracion) => ({
  entrega_coordinada_activa: Boolean(configuracion?.entrega_coordinada_activa),
  costo_entrega_coordinada: String(configuracion?.costo_entrega_coordinada ?? 0),
  instrucciones_entrega_coordinada: configuracion?.instrucciones_entrega_coordinada || ''
});

// El backend responde { campo: [mensajes] }
const erroresDe = (error) => {
  const datos = error.response?.data;
  if (!datos || typeof datos !== 'object') return { general: 'No se pudieron guardar los cambios. Inténtalo de nuevo.' };
  const porCampo = Object.fromEntries(Object.entries(datos)
    .filter(([campo]) => CAMPOS.includes(campo))
    .map(([campo, mensajes]) => [campo, [].concat(mensajes).join(' ')]));
  return { ...porCampo, general: 'Revisa los datos marcados.' };
};

export default function GestorEntregaCoordinada() {
  const [formulario, setFormulario] = useState(formularioDe(null));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState({});
  const [exito, setExito] = useState('');

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setFormulario(formularioDe(data)))
      .catch((error) => {
        console.error('Error al cargar la entrega coordinada:', error);
        setErrores({ general: 'No se pudo cargar la configuración de la entrega coordinada.' });
      })
      .finally(() => setCargando(false));
  }, []);

  const editar = (campo, valor) => {
    setFormulario((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actual) => ({ ...actual, [campo]: undefined }));
    setExito('');
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrores({});
    setExito('');
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', {
        ...formulario,
        // Un costo vacío es una entrega gratis
        costo_entrega_coordinada: formulario.costo_entrega_coordinada.trim() === ''
          ? 0 : Number(formulario.costo_entrega_coordinada)
      });
      setFormulario(formularioDe(data));
      await recargarConfiguracion();
      setExito(data.entrega_coordinada_activa
        ? 'Entrega coordinada guardada: tus clientes ya la ven al comprar.'
        : 'Entrega coordinada guardada: está desactivada y no se ofrece al comprar.');
    } catch (error) {
      setErrores(erroresDe(error));
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando entrega coordinada..."><EsqueletoFormulario campos={3} /></Cargando>;

  // Asocia el error del backend con su campo (aria-describedby)
  const describir = (campo, ayuda) => {
    const ids = [ayuda, errores[campo] && `entrega-${campo}-error`].filter(Boolean).join(' ');
    return { 'aria-describedby': ids || undefined, 'aria-invalid': errores[campo] ? true : undefined };
  };
  const errorCampo = (campo) => errores[campo]
    ? <p id={`entrega-${campo}-error`} className="admin-error-campo">{errores[campo]}</p>
    : null;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        El comprador deja su dirección y tú lo contactas para acordar el día y el lugar de la entrega. Sirve si
        entregas en persona o con tu propio repartidor, sin Chilexpress.
      </p>

      {errores.general && <p role="alert" className="admin-aviso admin-aviso--error">{errores.general}</p>}
      {exito && <p role="status" className="admin-aviso admin-aviso--exito">{exito}</p>}

      <form onSubmit={guardar} className="admin-formulario">
        <label className="admin-casilla">
          <input
            type="checkbox"
            checked={formulario.entrega_coordinada_activa}
            onChange={(e) => editar('entrega_coordinada_activa', e.target.checked)}
            {...describir('entrega_coordinada_activa')}
          />
          Ofrecer "Entrega coordinada" en el checkout
        </label>
        {errorCampo('entrega_coordinada_activa')}

        <div className="admin-campo">
          <label htmlFor="entrega-costo">Costo de la entrega (CLP)</label>
          <input
            id="entrega-costo"
            type="number"
            inputMode="numeric"
            min={0}
            max={1000000}
            step={1}
            value={formulario.costo_entrega_coordinada}
            onChange={(e) => editar('costo_entrega_coordinada', e.target.value)}
            {...describir('costo_entrega_coordinada', 'entrega-costo-ayuda')}
          />
          <p id="entrega-costo-ayuda" className="admin-ayuda">
            Se suma al total de la compra. Déjalo en 0 si la entrega es gratis. El envío gratis sobre un monto
            de tus promociones también se aplica a esta entrega.
          </p>
          {errorCampo('costo_entrega_coordinada')}
        </div>

        <div className="admin-campo">
          <label htmlFor="entrega-instrucciones">Instrucciones para el comprador</label>
          <textarea
            id="entrega-instrucciones"
            rows={3}
            maxLength={300}
            value={formulario.instrucciones_entrega_coordinada}
            onChange={(e) => editar('instrucciones_entrega_coordinada', e.target.value)}
            placeholder="Ej: Entregamos en Santiago de lunes a viernes. Te escribimos por WhatsApp para coordinar."
            {...describir('instrucciones_entrega_coordinada', 'entrega-instrucciones-ayuda')}
          />
          <p id="entrega-instrucciones-ayuda" className="admin-ayuda">
            Se muestran al elegir esta entrega y en los correos del pedido. Si las dejas vacías, se dice que la
            tienda lo contactará para acordar el día y la hora.
          </p>
          {errorCampo('instrucciones_entrega_coordinada')}
        </div>

        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar entrega coordinada'}
          </button>
        </div>
      </form>
    </>
  );
}
