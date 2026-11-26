import React, { useState, useEffect, useMemo } from 'react';
import clienteAxios from './auth/axiosConfig';
import { Cargando } from './carga/Esqueleto';
import { EsqueletoTabla } from './carga/EsqueletosPanel';

const obtenerStockTotal = (variantes) => {
  if (!variantes || variantes.length === 0) return 0;
  return variantes.reduce((total, v) => total + (v.stock || 0), 0);
};

const obtenerPrecioMinimo = (variantes) => {
  if (!variantes || variantes.length === 0) return 0;
  return Math.min(...variantes.map(v => parseFloat(v.precio) || 0));
};

const obtenerRangoPrecios = (variantes) => {
  if (!variantes || variantes.length === 0) return '$0.00';
  const precios = variantes.map(v => parseFloat(v.precio) || 0);
  const min = Math.min(...precios);
  const max = Math.max(...precios);
  if (min === max) return `$${min.toFixed(2)}`;
  return `$${min.toFixed(2)} - $${max.toFixed(2)}`;
};

const formatearAtributos = (atributos) => {
  if (!atributos || Object.keys(atributos).length === 0) return 'Base';
  return Object.entries(atributos)
    .map(([clave, valor]) => `${clave.replace('_', ' ')}: ${valor}`)
    .join(' | ');
};

export default function TablaInventario({ onEditarProducto }) {
  const [productos, setProductos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [filasExpandidas, setFilasExpandidas] = useState({});

  const [categoriaFiltro, setCategoriaFiltro] = useState('');
  const [ordenFiltro, setOrdenFiltro] = useState('');

  // La tabla parte cargando: el efecto solo actualiza el estado cuando responde el servidor
  useEffect(() => {
    const cargarProductos = async () => {
      try {
        const { data } = await clienteAxios.get('catalogo/productos/?todos=true');
        setProductos(Array.isArray(data) ? data : (data?.results || []));
        setError(null);
      } catch (err) {
        console.error('Error al cargar inventario:', err);
        setError('No se pudo cargar la lista de productos.');
      } finally {
        setCargando(false);
      }
    };
    cargarProductos();
  }, []);

  const eliminarProducto = async (id) => {
    if (!window.confirm('¿Estás seguro de que deseas desactivar este producto? (Se ocultará de la tienda pero se mantendrá en el historial)')) return;
    
    try {
      await clienteAxios.patch(`catalogo/productos/${id}/`, { activo: false });
      setProductos(productos.filter((p) => (p.id || p._id) !== id));
    } catch (err) {
      console.error('Error al desactivar el producto:', err);
      alert('Hubo un error al intentar desactivar el producto.');
    }
  };

  const toggleFila = (id) => {
    setFilasExpandidas((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const categoriasUnicas = useMemo(() => {
    return [...new Set(productos.map(p => p.categoria).filter(Boolean))];
  }, [productos]);

  const productosFiltradosYOrdenados = useMemo(() => {
    let resultado = [...productos];

    if (categoriaFiltro) {
      resultado = resultado.filter(p => p.categoria === categoriaFiltro);
    }

    if (ordenFiltro === 'PRECIO_ASC') {
      resultado.sort((a, b) => obtenerPrecioMinimo(a.variantes) - obtenerPrecioMinimo(b.variantes));
    } else if (ordenFiltro === 'PRECIO_DESC') {
      resultado.sort((a, b) => obtenerPrecioMinimo(b.variantes) - obtenerPrecioMinimo(a.variantes));
    } else if (ordenFiltro === 'STOCK_ASC') {
      resultado.sort((a, b) => obtenerStockTotal(a.variantes) - obtenerStockTotal(b.variantes));
    } else if (ordenFiltro === 'STOCK_DESC') {
      resultado.sort((a, b) => obtenerStockTotal(b.variantes) - obtenerStockTotal(a.variantes));
    }

    return resultado;
  }, [productos, categoriaFiltro, ordenFiltro]);

  if (cargando) return <Cargando texto="Cargando inventario..."><EsqueletoTabla filas={6} columnas={6} /></Cargando>;
  if (error) return <p role="alert" style={{ color: '#b91c1c' }}>{error}</p>;

  const selectStyle = {
    padding: '8px 12px',
    borderRadius: '4px',
    border: '1px solid var(--color-control-border)',
    backgroundColor: 'var(--color-surface)',
    color: 'var(--color-text)',
    width: '100%'
  };

  // Cada filtro crece hasta llenar la fila, pero se puede encoger en celular (sin min-width: 0 empuja la página)
  const filtroStyle = { display: 'flex', flexDirection: 'column', gap: '5px', flex: '1 1 200px', minWidth: 0 };

  return (
    <div>
      <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', marginBottom: '20px', backgroundColor: 'var(--color-secondary)', padding: '15px', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
        <div style={filtroStyle}>
          <label htmlFor="inventario-categoria" style={{ fontSize: '0.9em', fontWeight: 'bold', color: 'var(--color-text)' }}>Filtrar por Categoría</label>
          <select id="inventario-categoria" value={categoriaFiltro} onChange={(e) => setCategoriaFiltro(e.target.value)} style={selectStyle}>
            <option value="">Todas las categorías</option>
            {categoriasUnicas.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        <div style={filtroStyle}>
          <label htmlFor="inventario-orden" style={{ fontSize: '0.9em', fontWeight: 'bold', color: 'var(--color-text)' }}>Ordenar por</label>
          <select id="inventario-orden" value={ordenFiltro} onChange={(e) => setOrdenFiltro(e.target.value)} style={selectStyle}>
            <option value="">Sin orden (Agregados recientemente)</option>
            <option value="PRECIO_ASC">Precio: Menor a Mayor</option>
            <option value="PRECIO_DESC">Precio: Mayor a Menor</option>
            <option value="STOCK_ASC">Stock Total: Menor a Mayor</option>
            <option value="STOCK_DESC">Stock Total: Mayor a Menor</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end', marginLeft: 'auto' }}>
          <span role="status" style={{ fontSize: '0.9em', color: 'var(--color-muted)' }}>
            Mostrando {productosFiltradosYOrdenados.length} de {productos.length} producto(s)
          </span>
        </div>
      </div>

      {productosFiltradosYOrdenados.length === 0 ? (
        <p style={{ color: 'var(--color-text)', textAlign: 'center', padding: '40px 0' }}>No hay productos que coincidan con estos filtros.</p>
      ) : (
        <div tabIndex={0} role="region" aria-label="Inventario de productos y variantes" style={{ overflowX: 'auto', backgroundColor: 'var(--color-surface)', borderRadius: '8px', border: '1px solid var(--color-border)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ backgroundColor: 'var(--color-background)', borderBottom: '2px solid var(--color-primary)' }}>
              <tr>
                <th scope="col" style={{ width: '50px', padding: '15px' }}><span className="visualmente-oculto">Variantes</span></th>
                <th style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold' }}>Imagen</th>
                <th style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold' }}>Producto</th>
                <th style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold' }}>Categoría</th>
                <th style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold' }}>Precio Base</th>
                <th style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold' }}>Stock Total</th>
                <th style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold', textAlign: 'center' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {productosFiltradosYOrdenados.map((producto) => {
                const id = producto.id || producto._id;
                const estaExpandida = filasExpandidas[id];
                const stockTotal = obtenerStockTotal(producto.variantes);
                
                return (
                  <React.Fragment key={id}>
                    {/* FILA PADRE (PRODUCTO GENERAL) */}
                    <tr 
                      style={{ 
                        borderBottom: estaExpandida ? 'none' : '1px solid var(--color-border)', 
                        backgroundColor: estaExpandida ? 'var(--color-secondary)' : 'var(--color-surface)',
                        transition: 'background-color 0.2s',
                        cursor: 'pointer' 
                      }}
                      onClick={() => toggleFila(id)}
                    >
                      <td style={{ padding: '15px', textAlign: 'center', color: 'var(--color-primary)', fontWeight: 'bold' }}>
                        <button type="button" aria-expanded={Boolean(estaExpandida)}
                          aria-label={`${estaExpandida ? 'Ocultar' : 'Mostrar'} variantes de ${producto.nombre}`}
                          onClick={evento => { evento.stopPropagation(); toggleFila(id); }}
                          style={{ minWidth: '44px', minHeight: '44px', border: 0, background: 'transparent', color: 'inherit', cursor: 'pointer' }}>
                          <span aria-hidden="true">{estaExpandida ? '▼' : '▶'}</span>
                        </button>
                      </td>
                      <td style={{ padding: '15px' }}>
                        {producto.imagenes && producto.imagenes.length > 0 ? (
                          <img src={producto.imagenes[0]} alt={producto.nombre} style={{ width: '50px', height: '50px', objectFit: 'cover', borderRadius: '4px', border: '1px solid var(--color-border)' }} />
                        ) : (
                          <div style={{ width: '50px', height: '50px', backgroundColor: 'var(--color-secondary)', borderRadius: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', color: 'var(--color-muted)' }}>Sin img</div>
                        )}
                      </td>
                      <td style={{ padding: '15px', color: 'var(--color-text)', fontWeight: 'bold' }}>
                        {/* NUEVO: Contenedor con la etiqueta visual del estado de publicación */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          {producto.nombre}
                          <span style={{ 
                            backgroundColor: producto.publicado ? '#dcfce3' : 'var(--color-secondary)', 
                            color: producto.publicado ? '#166534' : 'var(--color-muted)', 
                            padding: '2px 8px', borderRadius: '12px', fontSize: '0.75em', fontWeight: 'bold' 
                          }}>
                            {producto.publicado ? 'Publicado' : 'Borrador'}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8em', color: 'var(--color-muted)', fontWeight: 'normal', marginTop: '4px' }}>
                          {producto.variantes?.length || 0} variante(s)
                        </div>
                      </td>
                      <td style={{ padding: '15px', color: 'var(--color-text)' }}>
                        <span style={{ backgroundColor: 'var(--color-secondary)', padding: '4px 8px', borderRadius: '12px', fontSize: '0.85em' }}>{producto.categoria}</span>
                      </td>
                      <td style={{ padding: '15px', color: 'var(--color-text)', fontWeight: '500' }}>
                        {obtenerRangoPrecios(producto.variantes)}
                      </td>
                      <td style={{ padding: '15px' }}>
                        <span style={{ color: stockTotal > 10 ? '#166534' : (stockTotal > 0 ? '#92400e' : '#b91c1c'), fontWeight: 'bold', fontSize: '1.1em' }}>
                          {stockTotal}
                        </span>
                      </td>
                      <td style={{ padding: '15px', textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                        <button aria-label={`Editar ${producto.nombre}`} style={{ background: 'transparent', border: 'none', color: 'var(--color-primary)', cursor: 'pointer', marginRight: '10px', fontWeight: 'bold' }} onClick={() => onEditarProducto(producto)}>Editar</button>
                        <button aria-label={`Borrar ${producto.nombre}`} style={{ background: 'transparent', border: 'none', color: '#b91c1c', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => eliminarProducto(id)}>Borrar</button>
                      </td>
                    </tr>

                    {/* FILAS HIJAS (VARIANTES) */}
                    {estaExpandida && producto.variantes && producto.variantes.map((variante, index) => (
                      <tr key={index} style={{ backgroundColor: 'var(--color-secondary)', borderBottom: index === producto.variantes.length - 1 ? '1px solid var(--color-border)' : 'none' }}>
                        <td></td>
                        <td colSpan="2" style={{ padding: '10px 15px', borderLeft: '3px solid var(--color-primary)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span style={{ color: 'var(--color-muted)' }}>↳</span>
                            <span style={{ fontFamily: 'monospace', color: 'var(--color-primary)', fontWeight: 'bold' }}>{variante.sku}</span>
                            <span style={{ fontSize: '0.9em', color: 'var(--color-text)', textTransform: 'capitalize' }}>
                              ({formatearAtributos(variante.atributos_variables)})
                            </span>
                          </div>
                        </td>
                        <td></td>
                        <td style={{ padding: '10px 15px', color: 'var(--color-text)' }}>
                          ${parseFloat(variante.precio).toFixed(2)}
                        </td>
                        <td style={{ padding: '10px 15px' }}>
                          <span style={{ color: variante.stock > 10 ? '#166534' : (variante.stock > 0 ? '#92400e' : '#b91c1c') }}>
                            {variante.stock} en stock
                          </span>
                        </td>
                        {/* CELDA DE ACCIONES VACÍA PARA NO ROMPER LA TABLA */}
                        <td style={{ padding: '10px 15px', textAlign: 'center' }}>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
