import { useState, useEffect } from 'react';
import clienteAxios from './auth/axiosConfig';

const FORMULARIO_VACIO = {
  codigo: '',
  tipo_descuento: 'PORCENTAJE',
  valor_descuento: '',
  umbral_envio_gratis: '',
  fecha_expiracion: '',
  // RF-04.1: desde qué compra vale, cuántas veces se puede usar y si se aplica solo (domain/promociones.py)
  monto_minimo: '',
  usos_maximos: '',
  automatica: false
};

const vacioANull = (valor) => (valor === '' ? null : valor);

// El cupón vale hasta el final del día elegido, en la hora de la tienda (el backend usa America/Santiago)
const fechaParaBackend = (fecha) => (fecha ? `${fecha}T23:59:59` : null);

// "2026-10-31T23:59:59-03:00" -> "2026-10-31", en la hora local del navegador
const fechaParaFormulario = (iso) => {
  if (!iso) return '';
  const fecha = new Date(iso);
  const dosDigitos = (n) => String(n).padStart(2, '0');
  return `${fecha.getFullYear()}-${dosDigitos(fecha.getMonth() + 1)}-${dosDigitos(fecha.getDate())}`;
};

const estaVencida = (promo) => Boolean(promo.fecha_expiracion) && new Date(promo.fecha_expiracion) < new Date();

export default function GestorPromociones() {
  const [promociones, setPromociones] = useState([]);
  const [formData, setFormData] = useState(FORMULARIO_VACIO);
  const [editId, setEditId] = useState(null);
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    if (type === 'checkbox') {
      setFormData(prev => ({ ...prev, [name]: checked }));
      return;
    }
    setFormData(prev => ({
      ...prev,
      // El código se guarda en mayúsculas y sin espacios (domain/promociones.py): así se ve desde que se escribe
      [name]: name === 'codigo' ? value.toUpperCase().replace(/\s/g, '') : value
    }));
  };

  
  useEffect(() => {
    const cargarPromociones = async () => {
      try {
        
        const respuesta = await clienteAxios.get('ventas/promociones/'); 
        setPromociones(respuesta.data);
      } catch (error) {
        console.error("Error cargando promociones:", error);
      }
    };
    cargarPromociones();
  }, []);

  
  const handleSubmit = async (e) => {
    e.preventDefault();
    // Los campos opcionales vacíos se envían como null (sin umbral, sin vencimiento)
    const datos = {
        ...formData,
        umbral_envio_gratis: vacioANull(formData.umbral_envio_gratis),
        monto_minimo: vacioANull(formData.monto_minimo),
        usos_maximos: vacioANull(formData.usos_maximos),
        fecha_expiracion: fechaParaBackend(formData.fecha_expiracion)
    };
    try {
        if (editId) {

            const respuesta = await clienteAxios.put(`ventas/promociones/${editId}/`, datos);
            setPromociones(promociones.map(p => p.id === editId ? respuesta.data : p));
        } else {

            const respuesta = await clienteAxios.post('ventas/promociones/', datos);
            setPromociones([...promociones, respuesta.data]);
        }


        setFormData(FORMULARIO_VACIO);
        setEditId(null); 
    } catch (error) {
        console.error("Error al guardar promoción:", error);
        // El backend responde { campo: [mensajes] }: se muestran para que el admin sepa qué corregir
        const mensajes = Object.values(error.response?.data || {}).flat().filter(m => typeof m === 'string');
        alert(mensajes.length ? `No se pudo guardar el código:\n${mensajes.join('\n')}` : "Hubo un error al guardar el código.");
    }
  };

  
  const eliminarPromocion = async (id) => {
    try {
      await clienteAxios.delete(`ventas/promociones/${id}/`);
      setPromociones(promociones.filter(p => p.id !== id));
    } catch (error) {
      console.error("Error al eliminar:", error);
    }
  };
  const cargarPromocionParaEditar = (promo) => {
    setEditId(promo.id);
    setFormData({
        codigo: promo.codigo,
        tipo_descuento: promo.tipo_descuento,
        valor_descuento: promo.valor_descuento, 
        umbral_envio_gratis: promo.umbral_envio_gratis || '',
        monto_minimo: promo.monto_minimo ?? '',
        usos_maximos: promo.usos_maximos ?? '',
        automatica: Boolean(promo.automatica),
        fecha_expiracion: fechaParaFormulario(promo.fecha_expiracion)
    });
  };

  return (
    // El título lo pone la sección "Promociones y Descuentos" de Configuración
    <div style={{ maxWidth: '950px' }}>

      {/* FORMULARIO DE CREACIÓN */}
      <div style={{ backgroundColor: 'var(--color-secondary)', padding: '20px', marginBottom: '30px' }}>
        <h5 style={{ marginTop: 0, color: 'var(--color-text)' }}>Crear nuevo código</h5>
        
        <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div>
            <label htmlFor="promocion-codigo" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Código de Descuento</label>
            <input required type="text" id="promocion-codigo" name="codigo" value={formData.codigo} onChange={handleChange} maxLength={50} pattern="[A-Za-zÑñ0-9_\-]+" title="Solo letras, números, guiones o guiones bajos, sin espacios" placeholder="Ej. VERANO20"style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)', textTransform: 'uppercase' }} />
          </div>

          <div>
            <label htmlFor="promocion-tipo" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Tipo de Descuento</label>
            <select id="promocion-tipo" name="tipo_descuento" value={formData.tipo_descuento} onChange={handleChange} style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }}>
              <option value="PORCENTAJE">Porcentaje (%)</option>
              <option value="MONTO_FIJO">Monto Fijo ($)</option>
            </select>
          </div>

          <div>
            <label htmlFor="promocion-valor" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Valor del Descuento</label>
            <input required type="number" id="promocion-valor" name="valor_descuento" value={formData.valor_descuento} onChange={handleChange} min={formData.tipo_descuento === 'PORCENTAJE' ? 0.01 : 1} max={formData.tipo_descuento === 'PORCENTAJE' ? 100 : undefined} step={formData.tipo_descuento === 'PORCENTAJE' ? 0.01 : 1}placeholder={formData.tipo_descuento === 'PORCENTAJE' ? 'Ej. 15' : 'Ej. 5000'} style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }} />
          </div>

          <div>
            <label htmlFor="promocion-umbral-envio" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Umbral Envío Gratis ($)</label>
            <input type="number" id="promocion-umbral-envio" name="umbral_envio_gratis" value={formData.umbral_envio_gratis} onChange={handleChange} min={1} step={1}placeholder="Ej. 30000 (Opcional)" style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }} />
          </div>

          <div>
            <label htmlFor="promocion-fecha-expiracion" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Válido hasta (opcional)</label>
            <input id="promocion-fecha-expiracion" type="date" name="fecha_expiracion" value={formData.fecha_expiracion} onChange={handleChange} aria-describedby="promocion-fecha-expiracion-ayuda" style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }} />
            <p id="promocion-fecha-expiracion-ayuda" style={{ margin: '5px 0 0', fontSize: '13px', color: 'var(--color-muted)' }}>
              El código deja de funcionar al terminar ese día. Déjalo vacío para que no venza.
            </p>
          </div>

          <div>
            <label htmlFor="promocion-monto-minimo" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Compra mínima ($)</label>
            <input type="number" id="promocion-monto-minimo" name="monto_minimo" value={formData.monto_minimo} onChange={handleChange} min={1} step={1} required={formData.automatica} aria-describedby="promocion-monto-minimo-ayuda" placeholder="Ej. 30000 (Opcional)" style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }} />
            <p id="promocion-monto-minimo-ayuda" style={{ margin: '5px 0 0', fontSize: '13px', color: 'var(--color-muted)' }}>
              El código solo vale si la compra llega a este monto.
            </p>
          </div>

          <div>
            <label htmlFor="promocion-usos-maximos" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', fontSize: '14px' }}>Usos máximos</label>
            <input type="number" id="promocion-usos-maximos" name="usos_maximos" value={formData.usos_maximos} onChange={handleChange} min={1} step={1} aria-describedby="promocion-usos-maximos-ayuda" placeholder="Sin límite" style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid var(--color-control-border)' }} />
            <p id="promocion-usos-maximos-ayuda" style={{ margin: '5px 0 0', fontSize: '13px', color: 'var(--color-muted)' }}>
              Cuántas compras pueden usarlo en total (ej. 1 para un regalo único). Vacío: sin límite.
            </p>
          </div>

          <div style={{ gridColumn: '1 / -1' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold', fontSize: '14px', cursor: 'pointer' }}>
              <input type="checkbox" name="automatica" checked={formData.automatica} onChange={handleChange} aria-describedby="promocion-automatica-ayuda" />
              Aplicar automáticamente
            </label>
            <p id="promocion-automatica-ayuda" style={{ margin: '5px 0 0', fontSize: '13px', color: 'var(--color-muted)' }}>
              Se aplica solo a toda compra desde la compra mínima, sin escribir el código (el código no se muestra en la tienda). Si el comprador escribe otro, se aplica el que más le conviene: no se suman.
            </p>
          </div>

          <div style={{ gridColumn: '1 / -1', textAlign: 'right', marginTop: '10px' }}>
            <button type="submit" style={{ padding: '10px 24px', backgroundColor: 'var(--color-primary)', color: 'var(--color-on-primary)', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
              Guardar Promoción
            </button>
          </div>
        </form>
      </div>

      {/* TABLA DE PROMOCIONES ACTIVAS */}
      <div style={{ backgroundColor: 'var(--color-surface)', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 6px rgba(0,0,0,0.1)' }}>
        <h5 style={{ marginTop: 0, color: 'var(--color-text)' }}>Códigos activos</h5>
        <div tabIndex={0} role="region" aria-label="Promociones y acciones" style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--color-border)', backgroundColor: 'var(--color-secondary)' }}>
                <th style={{ padding: '12px' }}>Código</th>
                <th style={{ padding: '12px' }}>Tipo</th>
                <th style={{ padding: '12px' }}>Valor</th>
                <th style={{ padding: '12px' }}>Envío Gratis Desde</th>
                <th style={{ padding: '12px' }}>Compra mínima</th>
                <th style={{ padding: '12px' }}>Usos</th>
                <th style={{ padding: '12px' }}>Válido hasta</th>
                <th style={{ padding: '12px', textAlign: 'center' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
                {promociones.map((promo) => (
                    <tr key={promo.id}>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', fontWeight: 'bold', color: 'var(--color-primary, #0369a1)' }}>
                        {promo.codigo}
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                        {promo.tipo_descuento === 'PORCENTAJE' ? 'Porcentaje' : 'Monto Fijo'}
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                        {promo.tipo_descuento === 'PORCENTAJE' 
                        ? `${promo.valor_descuento}%` 
                        : `$${Number(promo.valor_descuento).toLocaleString('es-CL')}`
                        }
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                        {promo.umbral_envio_gratis ? `$${Number(promo.umbral_envio_gratis).toLocaleString('es-CL')}` : '-'}
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                        {promo.monto_minimo ? `$${Number(promo.monto_minimo).toLocaleString('es-CL')}` : '-'}
                        {promo.automatica && <span style={{ display: 'block', fontSize: '13px' }}>Automático</span>}
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', color: 'var(--color-muted)' }}>
                        {promo.usos_maximos ? `${promo.usos} de ${promo.usos_maximos}` : `${promo.usos} (sin límite)`}
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)', color: estaVencida(promo) ? '#b91c1c' : 'var(--color-muted)' }}>
                        {promo.fecha_expiracion
                          ? `${new Date(promo.fecha_expiracion).toLocaleDateString('es-CL')}${estaVencida(promo) ? ' (vencido)' : ''}`
                          : 'Sin vencimiento'}
                    </td>
                    <td style={{ padding: '12px', borderBottom: '1px solid var(--color-border)' }}>
                      <button
                          
                          onClick={() => cargarPromocionParaEditar(promo)}
                          style={{ padding: '6px 12px', backgroundColor: 'var(--color-primary)', color: 'var(--color-on-primary)', border: 'none', borderRadius: '4px', cursor: 'pointer', marginRight: '8px' }}
                      >
                          Editar
                      </button>
                      <button
                          onClick={() => eliminarPromocion(promo.id)}
                          style={{ padding: '6px 12px', backgroundColor: '#e11d48', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                      >
                          Eliminar
                      </button>
                    </td>
                    </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
