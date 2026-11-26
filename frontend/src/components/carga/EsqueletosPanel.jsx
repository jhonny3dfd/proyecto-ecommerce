import { Bloque } from './Esqueleto';

// Esqueletos del panel: usan las clases reales del panel (Admin.css), así ocupan el mismo lugar que lo que viene
// y la página no salta cuando llegan los datos. Van dentro de <Cargando>, que los oculta al lector de pantalla

// Anchos que se van alternando, para que las líneas no se vean todas iguales
const ANCHOS = ['70%', '45%', '85%', '55%', '65%'];
const lista = (cantidad) => Array.from({ length: cantidad }, (_, i) => i);
// Las secciones de la barra lateral, en rem: en el celular los ítems toman el ancho de su contenido
const ANCHOS_SECCIONES = ['5.5rem', '5rem', '3.5rem', '6.5rem', '4.5rem', '2.5rem', '6.5rem', '7.5rem'];

export function EsqueletoTabla({ filas = 5, columnas = 4 }) {
  return (
    <div className="esqueleto-tabla" style={{ '--columnas': columnas }}>
      {lista(filas + 1).map((fila) => (
        <div key={fila} className={fila === 0 ? 'esqueleto-tabla-fila esqueleto-tabla-fila--encabezado' : 'esqueleto-tabla-fila'}>
          {lista(columnas).map((columna) => (
            <Bloque key={columna} ancho={ANCHOS[(fila + columna) % ANCHOS.length]} alto={fila === 0 ? '0.8em' : '1em'} />
          ))}
        </div>
      ))}
    </div>
  );
}

// Tarjetas de una lista del panel (reseñas, cotizaciones, publicaciones): título, dos líneas y sus botones
export function EsqueletoLista({ elementos = 3 }) {
  return (
    <div className="esqueleto-lista">
      {lista(elementos).map((elemento) => (
        <div key={elemento} className="esqueleto-tarjeta">
          <Bloque ancho="40%" alto="1.2em" />
          <Bloque ancho={ANCHOS[elemento % ANCHOS.length]} />
          <Bloque ancho="55%" />
          <div className="esqueleto-botones">
            <Bloque ancho="7rem" alto="2.25rem" forma="boton" />
            <Bloque ancho="5rem" alto="2.25rem" forma="boton" />
          </div>
        </div>
      ))}
    </div>
  );
}

// Un formulario de Configuración: cada campo con su etiqueta, el editor de texto si lo tiene y el botón de guardar
export function EsqueletoFormulario({ campos = 2, editor = false }) {
  return (
    <div className="admin-formulario">
      {lista(campos).map((campo) => (
        <div key={campo} className="esqueleto-campo">
          <Bloque ancho={ANCHOS_SECCIONES[campo % ANCHOS_SECCIONES.length]} alto="0.85em" />
          <Bloque alto="2.5rem" />
        </div>
      ))}
      {editor && <Bloque alto="320px" />}
      <Bloque ancho="9rem" alto="2.75rem" forma="boton" />
    </div>
  );
}

// El dashboard bajo su título: filtro de fechas, indicadores, gráfico y últimos pedidos
export function EsqueletoDashboard() {
  return (
    <div className="esqueleto-dashboard">
      <div className="esqueleto-dashboard-filtro">
        {lista(2).map((campo) => (
          <div key={campo} className="esqueleto-campo">
            <Bloque ancho="3rem" alto="0.85em" />
            <Bloque ancho="9.5rem" alto="2.5rem" />
          </div>
        ))}
        <Bloque ancho="5rem" alto="2.5rem" forma="boton" />
      </div>

      <div className="esqueleto-dashboard-indicadores">
        {lista(2).map((indicador) => (
          <div key={indicador} className="admin-indicador">
            <Bloque ancho="45%" alto="0.75em" />
            <Bloque ancho="60%" alto="2.5rem" style={{ margin: '14px 0 10px' }} />
            <Bloque ancho="80%" alto="0.85em" />
          </div>
        ))}
      </div>

      <div className="esqueleto-dashboard-seccion">
        <Bloque ancho="12rem" alto="1.2em" />
        <Bloque ancho="60%" alto="0.9em" style={{ margin: '10px 0 25px' }} />
        <Bloque alto="350px" />
      </div>

      <div className="esqueleto-dashboard-seccion">
        <Bloque ancho="10rem" alto="1.2em" style={{ marginBottom: '20px' }} />
        <EsqueletoTabla filas={4} columnas={4} />
      </div>
    </div>
  );
}

// El panel entero mientras se verifica la sesión: barra lateral, saludo y dashboard.
// El texto para el lector de pantalla es el mismo de ProtectedRoute
export function EsqueletoPanel() {
  return (
    <div className="admin">
      <div className="admin-barra" aria-hidden="true">
        <div className="admin-marca">
          <Bloque ancho="9rem" alto="1.6rem" />
          <Bloque ancho="11rem" alto="0.7rem" style={{ marginTop: '10px' }} />
        </div>
        <div className="admin-nav">
          {ANCHOS_SECCIONES.map((ancho, i) => (
            <span key={i} className="admin-nav-item">
              <Bloque ancho="18px" alto="18px" />
              <Bloque ancho={ancho} alto="0.9em" />
            </span>
          ))}
        </div>
      </div>

      <main tabIndex={-1} id="contenido" className="admin-principal">
        <p role="status" className="visualmente-oculto">Verificando sesión...</p>
        <div className="admin-topbar" aria-hidden="true">
          <Bloque ancho="3.5rem" alto="0.7rem" />
          <Bloque ancho="16rem" alto="2.1rem" style={{ margin: '10px 0 8px' }} />
          <Bloque ancho="13rem" alto="0.85rem" />
        </div>
        <div className="admin-contenido" aria-hidden="true">
          <Bloque ancho="10rem" alto="1.8rem" />
          <Bloque ancho="18rem" alto="0.95rem" style={{ margin: '10px 0 25px' }} />
          <EsqueletoDashboard />
        </div>
      </main>
    </div>
  );
}
