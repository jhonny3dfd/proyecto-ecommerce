import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import Spinner from './carga/Spinner';

// Fotos y logo (pedido de un cliente, 2026-11-09): tres opciones independientes, apagadas por defecto, que cambian
// cómo se ven las fotos de los productos y el logo. Se aplican en toda la tienda con useConfiguracionTienda
const OPCIONES = [
  {
    campo: 'fotos_completas',
    titulo: 'Mostrar las fotos completas, sin recortar',
    ayuda: 'Para obras de distintas proporciones: cada foto se ve entera dentro de su marco, en el catálogo, en la '
      + 'página de inicio y en la ficha. Los bordes que sobran toman el color de fondo de tu tienda.',
  },
  {
    campo: 'ficha_horizontal',
    titulo: 'Ficha del producto con la foto horizontal y más grande',
    ayuda: 'La foto ocupa cerca de dos tercios del ancho, en un marco apaisado, y los textos de al lado se ven un '
      + 'poco más chicos. Ideal si la mayoría de tus trabajos son horizontales. En el celular sigue en una columna.',
  },
  {
    campo: 'logo_grande',
    titulo: 'Logo más grande',
    ayuda: 'El logo del menú superior se ve más grande en el computador, la tablet y el celular.',
  },
];

const formularioDe = (configuracion) =>
  Object.fromEntries(OPCIONES.map(({ campo }) => [campo, Boolean(configuracion?.[campo])]));

export default function GestorPresentacion() {
  const [formulario, setFormulario] = useState(formularioDe(null));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [exito, setExito] = useState('');

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setFormulario(formularioDe(data)))
      .catch((fallo) => {
        console.error('Error al cargar las opciones de fotos y logo:', fallo);
        setError('No se pudieron cargar las opciones de fotos y logo.');
      })
      .finally(() => setCargando(false));
  }, []);

  const editar = (campo, valor) => {
    setFormulario((actual) => ({ ...actual, [campo]: valor }));
    setError('');
    setExito('');
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError('');
    setExito('');
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', formulario);
      setFormulario(formularioDe(data));
      // La tienda se vuelve a marcar con las opciones nuevas (useConfiguracionTienda)
      await recargarConfiguracion();
      setExito('Opciones guardadas: revisa cómo se ve tu tienda con "Ver mi tienda".');
    } catch (fallo) {
      console.error('Error al guardar las opciones de fotos y logo:', fallo);
      setError('No se pudieron guardar las opciones. Inténtalo de nuevo.');
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando fotos y logo..."><EsqueletoFormulario campos={3} /></Cargando>;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Ajusta cómo se ven las fotos de tus productos y el logo. Puedes activar solo las que te sirvan; apagadas, tu
        tienda se ve como siempre.
      </p>

      {error && <p role="alert" className="admin-aviso admin-aviso--error">{error}</p>}
      {exito && <p role="status" className="admin-aviso admin-aviso--exito">{exito}</p>}

      <form onSubmit={guardar} className="admin-formulario">
        {OPCIONES.map(({ campo, titulo, ayuda }) => (
          <div key={campo}>
            <label className="admin-casilla">
              <input type="checkbox" checked={formulario[campo]} aria-describedby={`presentacion-${campo}-ayuda`}
                onChange={(e) => editar(campo, e.target.checked)} />
              {titulo}
            </label>
            <p id={`presentacion-${campo}-ayuda`} className="admin-ayuda presentacion-ayuda">{ayuda}</p>
          </div>
        ))}

        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar fotos y logo'}
          </button>
        </div>
      </form>
    </>
  );
}
