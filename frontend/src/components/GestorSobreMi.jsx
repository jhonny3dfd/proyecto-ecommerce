
import { useCallback, useEffect, useState } from 'react';
import ReactQuill from 'react-quill-new';
import clienteAxios from './auth/axiosConfig';
import { recargarConfiguracion } from '../hooks/useConfiguracionTienda';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';
import SelectorProyectosSobreMi from './SelectorProyectosSobreMi';
import FotosSobreMi from './FotosSobreMi';

const CAMPOS = ['sobre_mi_activo', 'sobre_mi_nombre', 'sobre_mi_biografia', 'sobre_mi_foto_1', 'sobre_mi_foto_1_alt',
  'sobre_mi_foto_2', 'sobre_mi_foto_2_alt'];

// Las fotos guardadas (url) y lo que el admin cambió sin guardar todavía (archivo y su vista previa)
const fotosDe = (configuracion) => Object.fromEntries([1, 2].map((numero) => {
  const url = configuracion?.[`sobre_mi_foto_${numero}`] || null;
  const alt = configuracion?.[`sobre_mi_foto_${numero}_alt`] || '';
  // guardada y altGuardado: lo que está en el servidor, para enviar solo lo que cambió
  return [numero, { url, alt, archivo: null, vista: null, guardada: url, altGuardado: alt }];
}));

const formularioDe = (configuracion) => ({
  sobre_mi_activo: Boolean(configuracion?.sobre_mi_activo),
  sobre_mi_nombre: configuracion?.sobre_mi_nombre || 'Sobre mí',
  sobre_mi_biografia: configuracion?.sobre_mi_biografia || ''
});

const erroresDe = (error) => {
  const datos = error.response?.data;

  if (!datos || typeof datos !== 'object') {
    return { general: 'No se pudieron guardar los cambios.' };
  }

  const porCampo = Object.fromEntries(
    Object.entries(datos)
      .filter(([campo]) => CAMPOS.includes(campo))
      .map(([campo, mensajes]) => [campo, [].concat(mensajes).join(' ')])
  );

  return { ...porCampo, general: 'Revisa los datos marcados.' };
};

export default function GestorSobreMi() {
  const [formulario, setFormulario] = useState(formularioDe(null));
  const [fotos, setFotos] = useState(fotosDe(null));
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState({});
  const [exito, setExito] = useState('');
  // Los proyectos son publicaciones del blog: con el blog apagado no se muestran (domain/sobre_mi.py)
  const [blogActivo, setBlogActivo] = useState(true);

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => {
        setFormulario(formularioDe(data));
        setFotos(fotosDe(data));
        setBlogActivo(Boolean(data.blog_activo));
      })
      .catch((error) => {
        console.error('Error al cargar Sobre mí:', error);
        setErrores({ general: 'No se pudo cargar la configuración de Sobre mí.' });
      })
      .finally(() => setCargando(false));
  }, []);

  // WCAG: Quill no les pone nombre a su área de texto ni a sus controles; se los ponemos como en GestorPoliticas.jsx
  const prepararEditor = useCallback((instancia) => {
    if (!instancia) return;
    const editor = instancia.getEditor();
    editor.root.setAttribute('role', 'textbox');
    editor.root.setAttribute('aria-multiline', 'true');
    editor.root.setAttribute('aria-labelledby', 'sobre-mi-biografia-etiqueta');
    const barra = editor.getModule('toolbar').container;
    barra.setAttribute('aria-label', 'Formato de la biografía');
    const nombres = { bold: 'Negrita', italic: 'Cursiva', underline: 'Subrayado', link: 'Insertar enlace', clean: 'Quitar formato', list: 'Lista', header: 'Nivel de encabezado' };
    for (const control of barra.querySelectorAll('button, .ql-picker-label, .ql-picker-item')) {
      const formato = [...control.classList].find((clase) => clase.startsWith('ql-') && nombres[clase.slice(3)])?.slice(3);
      if (formato) control.setAttribute('aria-label', nombres[formato] + (control.value ? `: ${control.value === 'ordered' ? 'numerada' : control.value === 'bullet' ? 'con viñetas' : control.value}` : ''));
      if (control.classList.contains('ql-picker-label')) control.setAttribute('aria-label', 'Nivel de encabezado');
      if (control.classList.contains('ql-picker-item')) control.setAttribute('aria-label', control.dataset.value ? `Encabezado de nivel ${control.dataset.value}` : 'Párrafo');
    }
    editor.container.querySelector('.ql-tooltip input')?.setAttribute('aria-label', 'Dirección del enlace');
  }, []);

  const editar = (campo, valor) => {
    setFormulario((actual) => ({ ...actual, [campo]: valor }));
    setErrores((actual) => ({ ...actual, [campo]: undefined }));
    setExito('');
  };

  const cambiarFoto = (numero, cambios, error) => {
    const campo = `sobre_mi_foto_${numero}`;
    if (error) {
      setErrores((actual) => ({ ...actual, [campo]: error }));
      return;
    }
    setFotos((actual) => {
      // La vista previa anterior ya no se usa
      if ('vista' in cambios && actual[numero].vista) URL.revokeObjectURL(actual[numero].vista);
      return { ...actual, [numero]: { ...actual[numero], ...cambios } };
    });
    setErrores((actual) => ({ ...actual, [campo]: undefined, [`${campo}_alt`]: undefined }));
    setExito('');
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setErrores({});
    setExito('');

    try {
      // Los textos, las descripciones y las fotos quitadas van en JSON (null quita la foto); las nuevas, aparte
      const datos = { ...formulario };
      const nuevas = new FormData();
      for (const numero of [1, 2]) {
        const foto = fotos[numero];
        if (foto.alt !== foto.altGuardado) datos[`sobre_mi_foto_${numero}_alt`] = foto.alt;
        if (foto.archivo) nuevas.append(`sobre_mi_foto_${numero}`, foto.archivo);
        else if (foto.guardada && !foto.url) datos[`sobre_mi_foto_${numero}`] = null;
      }
      let { data } = await clienteAxios.patch('configuracion/negocio/', datos);
      if ([...nuevas.keys()].length > 0) {
        ({ data } = await clienteAxios.patch('configuracion/negocio/', nuevas, { headers: { 'Content-Type': undefined } }));
      }

      setFormulario(formularioDe(data));
      Object.values(fotos).forEach((foto) => foto.vista && URL.revokeObjectURL(foto.vista));
      setFotos(fotosDe(data));
      await recargarConfiguracion();

      setExito(
        data.sobre_mi_activo
          ? 'La página Sobre mí está activada y su información fue guardada.'
          : 'La configuración fue guardada. La página Sobre mí está desactivada.'
      );
    } catch (error) {
      setErrores(erroresDe(error));
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) {
    return (
      <Cargando texto="Cargando Sobre mí...">
        <EsqueletoFormulario campos={3} />
      </Cargando>
    );
  }

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        Crea una página independiente para contar tu historia,
        presentar tu emprendimiento y destacar tus proyectos.
        Puedes prepararla antes de activarla.
      </p>

      {errores.general && (
        <p role="alert" className="admin-aviso admin-aviso--error">
          {errores.general}
        </p>
      )}

      {exito && (
        <p role="status" className="admin-aviso admin-aviso--exito">
          {exito}
        </p>
      )}

      <form onSubmit={guardar} className="admin-formulario">
        <label className="admin-casilla">
          <input
            type="checkbox"
            checked={formulario.sobre_mi_activo}
            onChange={(e) =>
              editar('sobre_mi_activo', e.target.checked)
            }
          />
          Mostrar la página Sobre mí en mi tienda
        </label>

        <div className="admin-campo">
          <label htmlFor="sobre-mi-nombre">
            Nombre de la página
          </label>

          <input
            id="sobre-mi-nombre"
            type="text"
            maxLength={30}
            value={formulario.sobre_mi_nombre}
            onChange={(e) =>
              editar('sobre_mi_nombre', e.target.value)
            }
            placeholder="Sobre mí"
          />

          <p className="admin-ayuda">
            Por ejemplo: Sobre mí, Nosotros, Mi historia o
            Conoce nuestro emprendimiento.
          </p>
        </div>

        <div className="admin-campo">
          <label id="sobre-mi-biografia-etiqueta" htmlFor="sobre-mi-biografia">
            Biografía del emprendimiento
          </label>

          <div id="sobre-mi-biografia">
            <ReactQuill
              ref={prepararEditor}
              theme="snow"
              value={formulario.sobre_mi_biografia}
              onChange={(contenido) =>
                editar('sobre_mi_biografia', contenido)
              }
              placeholder="Cuenta la historia de tu emprendimiento..."
            />
          </div>

          <p className="admin-ayuda">
            Puedes utilizar títulos, negritas, listas y párrafos
            para presentar tu emprendimiento.
          </p>
        </div>

        <FotosSobreMi fotos={fotos} onCambiar={cambiarFoto} errores={errores} />

        <div>
          <button
            type="submit"
            disabled={guardando}
            className="boton boton-primario"
          >
            {guardando && <Spinner />}
            {guardando ? 'Guardando...' : 'Guardar Sobre mí'}
          </button>
        </div>
      </form>
      <hr className="admin-separador" />

      <SelectorProyectosSobreMi blogActivo={blogActivo} />
    </>
  );
}
