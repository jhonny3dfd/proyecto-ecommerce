import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// Activa el formulario de cotización y encargos: con él aparece "Cotizar" en el menú, el pie y cada producto
export default function GestorFormularioCotizacion() {
  const [activas, setActivas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setActivas(Boolean(data.cotizaciones_activas)))
      .catch(() => setAviso({ tipo: 'error', texto: 'No se pudo cargar la configuración de las cotizaciones.' }))
      .finally(() => setCargando(false));
  }, []);

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setAviso(null);
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', { cotizaciones_activas: activas });
      setActivas(Boolean(data.cotizaciones_activas));
      await recargarConfiguracion();
      setAviso({ tipo: 'exito', texto: data.cotizaciones_activas
        ? 'Formulario activado: tus clientes ya ven "Cotizar" en la tienda.'
        : 'Formulario desactivado: la tienda no recibe cotizaciones.' });
    } catch {
      setAviso({ tipo: 'error', texto: 'No se pudieron guardar los cambios. Inténtalo de nuevo.' });
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando cotizaciones..."><EsqueletoFormulario campos={1} /></Cargando>;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Para encargos, productos personalizados o compras en cantidad, de personas o empresas. Te llega cada
        solicitud a tu correo de contacto (o al de tu cuenta, si no lo cargaste) y la ves en el panel, en Cotizaciones.
      </p>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      <form onSubmit={guardar} className="admin-formulario">
        <label className="admin-casilla">
          <input type="checkbox" checked={activas} onChange={(e) => { setActivas(e.target.checked); setAviso(null); }} />
          Recibir solicitudes de cotización desde la tienda
        </label>
        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar cotizaciones'}
          </button>
        </div>
      </form>
    </>
  );
}
