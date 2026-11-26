import { useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import useConfiguracionTienda, { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import {
  CLAVE_TIPOGRAFIA, TIPOGRAFIAS, TIPOGRAFIA_PREDETERMINADA, aplicarTipografia, familiasDe
} from '../constants/tipografias';
import Spinner from './carga/Spinner';

// RF-01.2: el admin elige una de las 5 combinaciones de fuentes. Al hacer clic se ve en toda la página (tienda y
// panel); se publica al guardar, igual que la paleta.
export default function TipografiaSelector() {
  const configuracion = useConfiguracionTienda();
  const guardada = Number(configuracion?.tipografia_seleccionada ?? TIPOGRAFIA_PREDETERMINADA);
  // null = sin elegir todavía: se muestra la guardada
  const [elegida, setElegida] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState(null);
  const seleccionada = elegida ?? guardada;

  const elegir = (id) => {
    setElegida(id);
    setAviso(null);
    aplicarTipografia(id);
  };

  const guardar = async () => {
    setGuardando(true);
    setAviso(null);
    try {
      await clienteAxios.patch('configuracion/negocio/', { tipografia_seleccionada: seleccionada });
      localStorage.setItem(CLAVE_TIPOGRAFIA, String(seleccionada));
      await recargarConfiguracion();
      setElegida(null);
      setAviso({ tipo: 'exito', texto: 'Tipografía guardada: ya se ve en toda tu tienda.' });
    } catch (error) {
      console.error('Error al guardar la tipografía:', error);
      setAviso({ tipo: 'error', texto: 'No se pudo guardar la tipografía. Inténtalo de nuevo.' });
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="selector-tipografias">
      <p className="texto-secundario admin-descripcion">
        Cambia las letras de los títulos y del texto en toda la tienda y en este panel. Al elegir una ves cómo
        queda; se publica cuando la guardas.
      </p>

      <div className="selector-paletas-opciones" role="group" aria-label="Combinaciones de fuentes">
        {TIPOGRAFIAS.map((tipografia) => {
          const familias = familiasDe(tipografia.id);
          return (
            <button
              key={tipografia.id}
              type="button"
              aria-pressed={seleccionada === tipografia.id}
              onClick={() => elegir(tipografia.id)}
              className="selector-paleta selector-tipografia"
            >
              {/* Muestra: un título y una frase con las fuentes de la combinación */}
              <span className="selector-tipografia-vista" aria-hidden="true">
                <span className="selector-tipografia-titulo" style={{ fontFamily: familias.titulos }}>
                  Hecho a mano
                </span>
                <span className="selector-tipografia-texto" style={{ fontFamily: familias.texto }}>
                  Piezas únicas para tu hogar, con envío a todo Chile.
                </span>
              </span>
              <span className="selector-paleta-nombre">{tipografia.nombre}</span>
              <span className="selector-tipografia-descripcion">
                {tipografia.descripcion}.{' '}
                {tipografia.titulos.nombre === tipografia.texto.nombre
                  ? tipografia.titulos.nombre
                  : `${tipografia.titulos.nombre} y ${tipografia.texto.nombre}`}
              </span>
            </button>
          );
        })}
      </div>

      <div className="selector-paletas-acciones">
        <button type="button" onClick={guardar} disabled={guardando || seleccionada === guardada}
          className="boton boton-primario">
          {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar tipografía'}
        </button>
      </div>

      {aviso && (
        <p role={aviso.tipo === 'error' ? 'alert' : 'status'}
          className={`admin-aviso ${aviso.tipo === 'exito' ? 'admin-aviso--exito' : 'admin-aviso--error'}`}>
          {aviso.texto}
        </p>
      )}
    </div>
  );
}
