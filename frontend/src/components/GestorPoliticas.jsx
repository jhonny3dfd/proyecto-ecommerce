import { useState, useEffect, useCallback } from 'react';
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

const NOMBRES_PAGINA = {
  TERMINOS: 'Términos y Condiciones',
  PRIVACIDAD: 'Política de Privacidad',
  REEMBOLSOS: 'Política de Reembolsos'
};

// En producción la tienda no vende mientras estas dos no estén publicadas
const REQUERIDAS_PARA_VENDER = ['TERMINOS', 'PRIVACIDAD'];

const ESTILOS_AVISO = {
  error: { backgroundColor: '#fef2f2', border: '1px solid #fca5a5', color: '#991b1b' },
  exito: { backgroundColor: '#f0fdf4', border: '1px solid #86efac', color: '#166534' },
  advertencia: { backgroundColor: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e' }
};

const estadoDe = (pagina) => {
  if (pagina.publicada) return 'Publicada';
  return pagina.ultima_actualizacion ? 'Borrador' : 'Sin redactar';
};

const mensajeDeError = (error) => {
  const data = error.response?.data;
  return data?.contenido?.[0] || data?.titulo?.[0] || data?.detail || 'No se pudo guardar la página.';
};

const estiloCampo = {
  padding: '10px',
  width: '100%',
  maxWidth: '400px',
  borderRadius: '4px',
  border: '1px solid var(--color-control-border)',
  fontSize: '1rem'
};

const estiloEtiqueta = { display: 'block', marginBottom: '8px', fontWeight: 'bold', color: 'var(--color-text)' };

const formularioDe = (pagina) => ({
  titulo: pagina?.titulo || '',
  contenido: pagina?.contenido || '',
  publicada: Boolean(pagina?.publicada)
});

export default function GestorPoliticas() {
  const [paginas, setPaginas] = useState([]);
  const [tipo, setTipo] = useState('TERMINOS');
  const [formulario, setFormulario] = useState(formularioDe(null));
  // Solo cambios hechos por el admin; cargar una página en el editor no cuenta
  const [modificado, setModificado] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  // { tipo: 'error' | 'exito', texto }
  const [aviso, setAviso] = useState(null);

  const editar = (campo, valor) => setFormulario(actual => ({ ...actual, [campo]: valor }));

  const cargarPaginas = (tipoActual) => clienteAxios.get('ventas/admin/paginas-legales/')
    .then(({ data }) => {
      setPaginas(data);
      setFormulario(formularioDe(data.find(p => p.tipo_pagina === tipoActual)));
      setModificado(false);
    })
    .catch((error) => {
      console.error('Error al cargar las páginas legales:', error);
      setAviso({ tipo: 'error', texto: 'No se pudieron cargar las páginas legales.' });
    })
    .finally(() => setCargando(false));

  useEffect(() => {
    cargarPaginas('TERMINOS');
  }, []);

  const prepararEditor = useCallback(instancia => {
    if (!instancia) return;
    const editor = instancia.getEditor();
    editor.root.setAttribute('role', 'textbox');
    editor.root.setAttribute('aria-multiline', 'true');
    editor.root.setAttribute('aria-labelledby', 'pagina-legal-contenido');
    const barra = editor.getModule('toolbar').container;
    barra.setAttribute('aria-label', 'Formato del contenido legal');
    const nombres = { bold: 'Negrita', italic: 'Cursiva', underline: 'Subrayado', link: 'Insertar enlace', clean: 'Quitar formato', list: 'Lista', header: 'Nivel de encabezado' };
    for (const control of barra.querySelectorAll('button, .ql-picker-label, .ql-picker-item')) {
      const formato = [...control.classList].find(clase => clase.startsWith('ql-') && nombres[clase.slice(3)])?.slice(3);
      if (formato) control.setAttribute('aria-label', nombres[formato] + (control.value ? `: ${control.value === 'ordered' ? 'numerada' : control.value === 'bullet' ? 'con viñetas' : control.value}` : ''));
      if (control.classList.contains('ql-picker-label')) control.setAttribute('aria-label', 'Nivel de encabezado');
      if (control.classList.contains('ql-picker-item')) control.setAttribute('aria-label', control.dataset.value ? `Encabezado de nivel ${control.dataset.value}` : 'Párrafo');
    }
    const enlace = editor.container.querySelector('.ql-tooltip input');
    enlace?.setAttribute('aria-label', 'Dirección del enlace');
  }, []);

  const handleCambioTipo = (nuevoTipo) => {
    if (modificado && !window.confirm('Hay cambios sin guardar en esta página. ¿Descartarlos?')) return;
    setTipo(nuevoTipo);
    setAviso(null);
    setFormulario(formularioDe(paginas.find(p => p.tipo_pagina === nuevoTipo)));
    setModificado(false);
  };

  const handleGuardar = async () => {
    setGuardando(true);
    setAviso(null);
    try {
      const { data } = await clienteAxios.put(`ventas/admin/paginas-legales/${tipo.toLowerCase()}/`, formulario);
      setAviso({
        tipo: 'exito',
        texto: data.publicada
          ? `"${data.titulo}" guardada y publicada: ya aparece en el pie de página de la tienda.`
          : `"${data.titulo}" guardada como borrador: no es visible para los clientes.`
      });
      // Muestra lo que quedó guardado (el servidor limpia el HTML)
      await cargarPaginas(tipo);
    } catch (error) {
      setAviso({ tipo: 'error', texto: mensajeDeError(error) });
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return (
    <div>
      <h2 className="admin-titulo">Páginas legales</h2>
      <Cargando texto="Cargando páginas legales..."><EsqueletoFormulario campos={2} editor /></Cargando>
    </div>
  );

  const paginaActual = paginas.find(p => p.tipo_pagina === tipo);
  const faltantes = REQUERIDAS_PARA_VENDER.filter(t => !paginas.find(p => p.tipo_pagina === t)?.publicada);

  return (
    <div>
      <h2 className="admin-titulo">Páginas legales</h2>

      {faltantes.length > 0 && (
        <div style={{ ...ESTILOS_AVISO.advertencia, padding: '12px 16px', borderRadius: '6px', marginBottom: '20px' }}>
          Falta publicar: <strong>{faltantes.map(t => NOMBRES_PAGINA[t]).join(' y ')}</strong>. En producción la tienda
          no puede vender hasta que estén publicadas, porque el cliente las acepta al comprar.
        </div>
      )}

      {aviso && (
        <div
          role={aviso.tipo === 'error' ? 'alert' : 'status'}
          style={{ ...ESTILOS_AVISO[aviso.tipo], padding: '12px 16px', borderRadius: '6px', marginBottom: '20px' }}
        >
          {aviso.texto}
        </div>
      )}

      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="pagina-legal-tipo" style={estiloEtiqueta}>
          Selecciona la página a editar:
        </label>
        <select
          id="pagina-legal-tipo"
          value={tipo}
          onChange={(e) => handleCambioTipo(e.target.value)}
          style={estiloCampo}
        >
          {paginas.map(p => (
            <option key={p.tipo_pagina} value={p.tipo_pagina}>
              {NOMBRES_PAGINA[p.tipo_pagina]} ({estadoDe(p)})
            </option>
          ))}
        </select>
        {paginaActual?.ultima_actualizacion && (
          <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: 'var(--color-muted)' }}>
            Última actualización: {new Date(paginaActual.ultima_actualizacion).toLocaleString('es-CL')}
          </p>
        )}
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label htmlFor="pagina-legal-titulo" style={estiloEtiqueta}>
          Título visible en la tienda:
        </label>
        <input
          id="pagina-legal-titulo"
          type="text"
          value={formulario.titulo}
          maxLength={255}
          onChange={(e) => { editar('titulo', e.target.value); setModificado(true); }}
          style={estiloCampo}
        />
      </div>

      <div className="editor-legal" style={{ marginBottom: '20px' }}>
        <span id="pagina-legal-contenido" style={estiloEtiqueta}>Contenido:</span>
        <ReactQuill
          ref={prepararEditor}
          theme="snow"
          // HTML interno de Quill: el semántico convierte los espacios en &nbsp; (el texto no se ajusta al ancho)
          // y quita el marcador de las listas que usa el CSS de la página pública (PaginaLegal.jsx)
          useSemanticHTML={false}
          value={formulario.contenido}
          onChange={(valor, _delta, origen) => {
            editar('contenido', valor);
            if (origen === 'user') setModificado(true);
          }}
        />
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '20px', cursor: 'pointer', color: 'var(--color-text)' }}>
        <input
          type="checkbox"
          checked={formulario.publicada}
          onChange={(e) => { editar('publicada', e.target.checked); setModificado(true); }}
        />
        Publicada (visible en el pie de página y en la tienda)
      </label>

      <button
        type="button"
        onClick={handleGuardar}
        disabled={guardando || !modificado}
        style={{
          padding: '12px 24px',
          backgroundColor: 'var(--color-primary)',
          color: 'var(--color-on-primary)',
          border: 'none',
          borderRadius: '4px',
          cursor: guardando || !modificado ? 'not-allowed' : 'pointer',
          opacity: guardando || !modificado ? 0.6 : 1,
          fontWeight: 'bold',
          marginTop: '20px',
          fontSize: '1rem',
          transition: 'opacity 0.2s'
        }}
      >
        {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar cambios'}
      </button>
    </div>
  );
}
