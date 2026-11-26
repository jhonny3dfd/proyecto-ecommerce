import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// Activa las reseñas: el correo de "pedido entregado" las pide y la tienda muestra las que el admin aprobó
export default function GestorActivarResenas() {
  const [activas, setActivas] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setActivas(Boolean(data.resenas_activas)))
      .catch(() => setAviso({ tipo: 'error', texto: 'No se pudo cargar la configuración de las reseñas.' }))
      .finally(() => setCargando(false));
  }, []);

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setAviso(null);
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', { resenas_activas: activas });
      setActivas(Boolean(data.resenas_activas));
      await recargarConfiguracion();
      setAviso({ tipo: 'exito', texto: data.resenas_activas
        ? 'Reseñas activadas: el correo de cada pedido entregado invitará a tu cliente a dejar la suya.'
        : 'Reseñas desactivadas: no se piden reseñas y la tienda no muestra ninguna.' });
    } catch {
      setAviso({ tipo: 'error', texto: 'No se pudieron guardar los cambios. Inténtalo de nuevo.' });
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando reseñas..."><EsqueletoFormulario campos={1} /></Cargando>;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Cuando marques un pedido como Entregado, el correo le pedirá a tu cliente que califique la tienda y los
        productos con estrellas. Ninguna reseña se publica hasta que la apruebes en el panel, en Reseñas; las
        aprobadas aparecen en la página de inicio y en la ficha de cada producto.
      </p>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'} className={`admin-aviso admin-aviso--${aviso.tipo}`}>
          {aviso.texto}
        </p>
      )}

      <form onSubmit={guardar} className="admin-formulario">
        <label className="admin-casilla">
          <input type="checkbox" checked={activas} onChange={(e) => { setActivas(e.target.checked); setAviso(null); }} />
          Pedir reseñas a mis clientes y mostrarlas en la tienda
        </label>
        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar reseñas'}
          </button>
        </div>
      </form>
    </>
  );
}
