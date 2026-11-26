import { useEffect, useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoFormulario } from './carga/EsqueletosPanel';
import Spinner from './carga/Spinner';

// La tienda emite sus boletas y facturas por su cuenta (el sistema gratuito del SII u otro): el panel solo le
// indica qué pedidos necesitan documento. Las reglas viven en domain/documentos_tributarios.py
const MODELOS = [
  {
    valor: 'VOUCHER',
    etiqueta: 'El comprobante del pago con tarjeta vale como boleta',
    ayuda: 'Declaraste "No emito boleta cuando recibo un pago electrónico", o no declaraste ningún modelo (es lo que asume el SII). Las ventas con tarjeta no piden boleta.',
  },
  {
    valor: 'SIEMPRE_BOLETA',
    etiqueta: 'Siempre emito boleta, aunque me paguen con tarjeta',
    ayuda: 'Declaraste "Siempre emito boleta aún cuando reciba un pago electrónico". Todas las ventas piden boleta.',
  },
];

const SII_BOLETA = 'https://www.sii.cl/servicios_online/3532-.html';
const SII_MODELO = 'https://www.sii.cl/destacados/boleta_electronica_voucher/index.html';

export default function GestorDocumentosTributarios() {
  const [modelo, setModelo] = useState('VOUCHER');
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  const [exito, setExito] = useState('');

  useEffect(() => {
    clienteAxios.get('configuracion/negocio/')
      .then(({ data }) => setModelo(data.modelo_emision || 'VOUCHER'))
      .catch((err) => {
        console.error('Error al cargar el modelo de emisión:', err);
        setError('No se pudo cargar el modelo de emisión.');
      })
      .finally(() => setCargando(false));
  }, []);

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError('');
    setExito('');
    try {
      const { data } = await clienteAxios.patch('configuracion/negocio/', { modelo_emision: modelo });
      setModelo(data.modelo_emision);
      setExito('Modelo de emisión guardado: Ventas > Pedidos ya muestra qué documento falta en cada pedido.');
    } catch (err) {
      console.error('Error al guardar el modelo de emisión:', err);
      setError('No se pudo guardar el modelo de emisión. Inténtalo de nuevo.');
    } finally {
      setGuardando(false);
    }
  };

  if (cargando) return <Cargando texto="Cargando boletas y facturas..."><EsqueletoFormulario campos={2} /></Cargando>;

  return (
    <>
      <p className="texto-secundario admin-descripcion">
        La tienda no emite boletas ni facturas: las emites tú, en el sistema gratuito del SII o en el que uses. En
        Ventas &gt; Pedidos te mostramos qué pedidos necesitan documento y ahí anotas su folio.
      </p>

      <div className="admin-guia">
        <p className="admin-guia-titulo">Qué emitir en cada caso</p>
        <ul>
          <li><strong>Pago con tarjeta</strong> (Webpay o Mercado Pago): según tu modelo de emisión, el comprobante del pago vale como boleta.</li>
          <li><strong>Transferencia:</strong> siempre emites boleta. El comprobante de la transferencia no es un documento tributario.</li>
          <li><strong>Compra como empresa:</strong> siempre emites factura, con los datos que dejó el comprador.</li>
          <li><strong>Pedido cancelado que ya tenía boleta o factura:</strong> emites una nota de crédito.</li>
          <li><strong>Venta a una persona sobre 135 UF:</strong> la boleta debe llevar el nombre y el RUT de quien paga.</li>
        </ul>
        <p className="admin-ayuda">
          Para emitir necesitas inicio de actividades en el SII. Ante dudas, consulta a tu contador.{' '}
          <a href={SII_BOLETA} target="_blank" rel="noopener noreferrer">Boleta electrónica gratuita del SII
            <span className="visualmente-oculto"> (se abre en una pestaña nueva)</span></a>
          {' · '}
          <a href={SII_MODELO} target="_blank" rel="noopener noreferrer">Qué es el modelo de emisión
            <span className="visualmente-oculto"> (se abre en una pestaña nueva)</span></a>
        </p>
      </div>

      {error && <p role="alert" className="admin-aviso admin-aviso--error">{error}</p>}
      {exito && <p role="status" className="admin-aviso admin-aviso--exito">{exito}</p>}

      <form onSubmit={guardar} className="admin-formulario">
        <fieldset className="admin-opciones">
          <legend>Tu modelo de emisión en el SII</legend>
          <p id="modelo-emision-ayuda" className="admin-ayuda">
            Elige el mismo que declaraste en sii.cl (Servicios online &gt; Boleta de ventas y servicios electrónica).
          </p>
          {MODELOS.map(({ valor, etiqueta, ayuda }) => (
            <label key={valor} className="admin-casilla">
              <input
                type="radio"
                name="modelo_emision"
                value={valor}
                checked={modelo === valor}
                onChange={() => { setModelo(valor); setExito(''); }}
                aria-describedby={`modelo-emision-ayuda modelo-${valor}-ayuda`}
              />
              <span>
                {etiqueta}
                <span id={`modelo-${valor}-ayuda`} className="admin-ayuda admin-opcion-ayuda">{ayuda}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <div>
          <button type="submit" disabled={guardando} className="boton boton-primario">
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar modelo de emisión'}
          </button>
        </div>
      </form>
    </>
  );
}
