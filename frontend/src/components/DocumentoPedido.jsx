import { useState } from 'react';
import clienteAxios from './auth/axiosConfig';
import Spinner from './carga/Spinner';

// La boleta, factura o nota de crédito de un pedido: la tienda la emite por su cuenta y aquí anota su folio.
// documento_requerido y documento_por_emitir los calcula el backend (domain/documentos_tributarios.py)
const NOMBRES = { BOLETA: 'boleta', FACTURA: 'factura', NOTA_CREDITO: 'nota de crédito' };
const VENDIDOS = ['PAGADO', 'EN_PREPARACION', 'ENVIADO', 'ENTREGADO'];
const mayuscula = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);

const estiloPendiente = {
  display: 'inline-block', padding: '2px 8px', borderRadius: '12px', fontSize: '0.8rem', fontWeight: 'bold',
  whiteSpace: 'nowrap',
  backgroundColor: '#fffbeb', border: '1px solid #f59e0b', color: '#92400e',
};
const estiloBoton = {
  padding: '6px 10px', backgroundColor: 'var(--color-surface)', color: 'var(--color-primary)',
  border: '1px solid var(--color-primary)', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold',
};
const estiloEnlace = {
  minHeight: '24px', padding: 0, border: 0, background: 'none', color: 'var(--color-primary)',
  textDecoration: 'underline', cursor: 'pointer', fontSize: '0.85rem',
};

// onGuardado(texto): el panel muestra el aviso y recarga la página de pedidos
export default function DocumentoPedido({ pedido, deshabilitado, onGuardado }) {
  const cancelado = pedido.estado === 'CANCELADO';
  // En un cancelado el folio que se anota es el de la nota de crédito; si no, el de la boleta o factura
  const nombre = cancelado ? NOMBRES.NOTA_CREDITO : (NOMBRES[pedido.documento_requerido] || 'documento');
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [folio, setFolio] = useState('');
  const [error, setError] = useState('');
  const [guardando, setGuardando] = useState(false);
  const idError = `documento-${pedido.id}-error`;

  const folioDocumento = pedido.folio_documento;
  const folioNota = pedido.folio_nota_credito;
  const conFormulario = Boolean(pedido.documento_por_emitir) || corrigiendo;

  if (!conFormulario && !folioDocumento) {
    // Pago con tarjeta: el comprobante vale como boleta. Un pedido sin pagar todavía no se documenta
    const conVoucher = VENDIDOS.includes(pedido.estado) && !pedido.documento_requerido;
    return <span style={{ color: 'var(--color-muted)', fontSize: '0.9rem' }}>{conVoucher ? 'Voucher de pago' : '—'}</span>;
  }

  const corregir = () => {
    setCorrigiendo(true);
    setFolio(cancelado ? folioNota : folioDocumento);
    setError('');
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError('');
    try {
      await clienteAxios.post(`ventas/admin/ordenes/${pedido.id}/documento/`, { folio });
      setCorrigiendo(false);
      onGuardado(`${mayuscula(nombre)} N° ${folio.trim()} anotada en el pedido #${pedido.id}.`);
      setFolio('');
    } catch (err) {
      setError(err.response?.data?.folio?.[0] || err.response?.data?.detail || 'No se pudo guardar el folio.');
    } finally {
      setGuardando(false);
    }
  };

  // Se corrige el último folio anotado: la nota de crédito en un cancelado, la boleta o factura en los demás
  const puedeCorregir = !conFormulario && (cancelado ? Boolean(folioNota) : Boolean(folioDocumento));
  const botonCorregir = puedeCorregir && (
    <>
      {' '}
      <button type="button" onClick={corregir} disabled={deshabilitado} style={estiloEnlace}
        aria-label={`Corregir el folio de la ${nombre} del pedido #${pedido.id}`}>
        Corregir
      </button>
    </>
  );

  return (
    <div style={{ fontSize: '0.9rem' }}>
      {/* Primero lo ya emitido; debajo, lo que falta (ej. la nota de crédito de un pedido cancelado) */}
      {folioDocumento && (
        <div>
          {mayuscula(NOMBRES[pedido.documento_requerido] || 'documento')} N° {folioDocumento}
          {!cancelado && botonCorregir}
        </div>
      )}
      {cancelado && folioNota && <div>Nota de crédito N° {folioNota}{botonCorregir}</div>}
      {pedido.documento_por_emitir && (
        <span style={estiloPendiente}>{mayuscula(NOMBRES[pedido.documento_por_emitir])} pendiente</span>
      )}

      {conFormulario && (
        <form onSubmit={guardar} style={{ marginTop: '6px', display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
          <input
            type="text"
            inputMode="numeric"
            maxLength={10}
            value={folio}
            onChange={(e) => { setFolio(e.target.value); setError(''); }}
            placeholder="Folio"
            aria-label={`Folio de la ${nombre} del pedido #${pedido.id}`}
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? idError : undefined}
            required
            style={{ width: '9ch', padding: '6px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }}
          />
          <button type="submit" disabled={deshabilitado || guardando} style={estiloBoton}>
            {guardando && <Spinner />}{guardando ? 'Guardando...' : 'Guardar'}
          </button>
          {corrigiendo && (
            <button type="button" onClick={() => setCorrigiendo(false)} style={estiloEnlace}>Cancelar</button>
          )}
          {error && <p id={idError} style={{ flexBasis: '100%', margin: 0, fontSize: '0.85rem', color: '#b91c1c' }}>{error}</p>}
        </form>
      )}
    </div>
  );
}
