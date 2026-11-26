import { useState, useEffect } from 'react';
import clienteAxios from "./auth/axiosConfig";
import { PALETTES, aplicarPaleta } from '../constants/palettes';
import Spinner from './carga/Spinner';


export default function PaletteSelector() {
  const [selectedId, setSelectedId] = useState(() => {
     // ... tu estado inicial se mantiene igual
    const saved = localStorage.getItem('ecommerce_palette');
    const initialId = saved ? Number(saved) : 1;
    const initialPalette = PALETTES.find((p) => p.id === initialId) || PALETTES[0];
    aplicarPaleta(initialPalette.id);
    return initialId;
  });

  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // 1. fetchTema LIMPIO usando clienteAxios
  useEffect(() => {
    const fetchTema = async () => {
      try {
        // clienteAxios ya incluye la dirección de la API (VITE_API_URL)
        const response = await clienteAxios.get('configuracion/');
        const config = Array.isArray(response.data) ? response.data[0] : response.data;
        if (config && config.tema_seleccionado !== undefined) {
          const temaId = Number(config.tema_seleccionado);
          setSelectedId(temaId);
          localStorage.setItem('ecommerce_palette', temaId.toString());
          const palette = PALETTES.find((p) => p.id === temaId) || PALETTES[0];
          aplicarPaleta(palette.id);
        }
      } catch (error) {
        console.error('Error al sincronizar configuración con backend:', error);
      }
    };

    fetchTema();
  }, []);

  const handleSelect = (palette) => {
      // ... se mantiene igual
    setSelectedId(palette.id);
    aplicarPaleta(palette.id);
    localStorage.setItem('ecommerce_palette', palette.id.toString());
    window.dispatchEvent(
      new CustomEvent('themeChanged', { detail: { temaId: palette.id } })
    );
  };

  // 2. handleSave LIMPIO usando clienteAxios
  const handleSave = async () => {
    setLoading(true);
    setFeedback(null);
    // Ya no necesitas sacar el token a mano ni armar los headers, Axios lo hace por ti

    try {
      await clienteAxios.patch('configuracion/negocio/', { 
        tema_seleccionado: String(selectedId) 
      });

      localStorage.setItem('ecommerce_palette', selectedId.toString());
      setFeedback({ type: 'success', message: 'Configuración guardada exitosamente en el servidor.' });

      window.dispatchEvent(
        new CustomEvent('themeChanged', { detail: { temaId: selectedId } })
      );
    } catch (error) {
      console.error('Error al guardar paleta en backend:', error);
      localStorage.setItem('ecommerce_palette', selectedId.toString());
      setFeedback({
        type: 'warning',
        message: 'Guardado localmente. Error de sincronización con el servidor.'
      });
    } finally {
      setLoading(false);
    }
  };

  // Los 5 colores que identifican a cada tema (el resto son variantes de texto y bordes)
  const COLORES_MUESTRA = ['primary', 'secondary', 'accent', 'background', 'text'];

  return (
    <div className="selector-paletas">
      <div className="selector-paletas-opciones" role="group" aria-label="Paletas de colores">
        {PALETTES.map((palette) => {
          const isSelected = selectedId === palette.id;
          const { colors } = palette;
          return (
            <button
              key={palette.id}
              type="button"
              aria-pressed={isSelected}
              onClick={() => handleSelect(palette)}
              className="selector-paleta"
            >
              {/* Vista previa: texto y botón de la paleta sobre su fondo */}
              <span className="selector-paleta-vista" aria-hidden="true"
                style={{ backgroundColor: colors.background, color: colors.text }}>
                <span className="selector-paleta-letras">Aa</span>
                <span className="selector-paleta-boton" style={{ backgroundColor: colors.primary, color: colors.onPrimary }}>
                  Comprar
                </span>
              </span>
              <span className="selector-paleta-nombre">{palette.name}</span>
              <span className="selector-paleta-muestras" aria-hidden="true">
                {COLORES_MUESTRA.map((clave) => (
                  <span key={clave} style={{ backgroundColor: colors[clave] }} />
                ))}
              </span>
            </button>
          );
        })}
      </div>

      <div className="selector-paletas-acciones">
        <button type="button" onClick={handleSave} disabled={loading} className="boton boton-primario">
          {loading && <Spinner />}{loading ? 'Guardando...' : 'Guardar Preferencia'}
        </button>
      </div>

      {feedback && (
        <p role="status" className={`admin-aviso ${feedback.type === 'success' ? 'admin-aviso--exito' : 'admin-aviso--error'}`}>
          {feedback.message}
        </p>
      )}
    </div>
  );
}
