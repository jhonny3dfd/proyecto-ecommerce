import { useEffect, useRef } from 'react';
import { CAMPOS_TEXTO } from '../../hooks/useEdicionLanding';
import { SelectorImagen } from './ControlesEdicion';

const nombreCampo = (campo) => CAMPOS_TEXTO[campo]?.etiqueta || campo.replace(/_/g, ' ');

// Barra fija del modo edición: identidad (logo y favicon), estado y botones para guardar o descartar
export default function BarraEdicion({ edicion }) {
  const { vista, hayCambios, guardando, errores, mensaje } = edicion;
  const listaErrores = Object.entries(errores);
  const barra = useRef(null);

  // La barra está fija abajo: reserva su alto al final de la página para que no tape nada, tampoco el footer
  // (que va fuera de la landing). Se mide en vivo porque crece con los avisos de error
  useEffect(() => {
    const elemento = barra.current;
    const reservar = () => { document.body.style.paddingBottom = `${elemento.offsetHeight}px`; };
    reservar();
    const observador = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(reservar);
    observador?.observe(elemento);
    return () => {
      observador?.disconnect();
      document.body.style.paddingBottom = '';
    };
  }, []);

  return (
    <div ref={barra} className="barra-edicion" role="region" aria-label="Modo edición de la página de inicio">
      <div className="contenedor barra-edicion-contenido">
        <div className="barra-edicion-estado">
          <strong>Modo edición</strong>
          <span role="status">
            {guardando ? 'Guardando…' : mensaje || (hayCambios ? 'Tienes cambios sin guardar' : 'Sin cambios')}
          </span>
        </div>

        <div className="barra-edicion-identidad">
          <SelectorImagen campo="logo" nombre="logo" tieneImagen={Boolean(vista.logo)} edicion={edicion} claro />
          <SelectorImagen campo="favicon" nombre="favicon" tieneImagen={Boolean(vista.favicon)} edicion={edicion} claro />
          {/* RN-01: solo cambia de lugar (header o footer); no hay opción para ocultarlo */}
          <label className="barra-edicion-ubicacion">
            <span>Logo de la Universidad</span>
            <select value={vista.ubicacion_logo_universidad || 'HEADER'}
              onChange={(e) => edicion.cambiarTexto('ubicacion_logo_universidad', e.target.value)}>
              <option value="HEADER">Arriba, junto a tu logo</option>
              <option value="FOOTER">Abajo, en el pie de página y más grande</option>
            </select>
          </label>
        </div>

        <div className="barra-edicion-acciones">
          <button type="button" className="boton-edicion" onClick={edicion.descartar}
            disabled={!hayCambios || guardando}>
            Descartar
          </button>
          <button type="button" className="boton boton-primario" onClick={edicion.guardar}
            disabled={!hayCambios || guardando}>
            {guardando ? 'Guardando…' : 'Guardar cambios'}
          </button>
          <button type="button" className="boton-edicion" disabled={guardando}
            onClick={() => {
              if (!hayCambios || window.confirm('Tienes cambios sin guardar. ¿Salir y descartarlos?')) edicion.salir();
            }}>
            Salir
          </button>
        </div>
      </div>

      {listaErrores.length > 0 && (
        <ul className="contenedor barra-edicion-errores" role="alert">
          {listaErrores.map(([campo, texto]) => (
            <li key={campo}>{campo === 'general' ? texto : `${nombreCampo(campo)}: ${texto}`}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
