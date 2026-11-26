import { expect } from '@playwright/test';

export const producto = {
  id: '000000000000000000000001', nombre: 'Producto de prueba', categoria: 'Prueba',
  descripcion: 'Descripción de prueba', imagenes: [], activo: true, publicado: true,
  variantes: [{ sku: 'QA-1', precio: 1000, stock: 5, atributos_variables: { talla: 'M' } }],
};

// Dashboard del admin sin ventas ni pendientes (RF-03.1); un test puede reemplazar partes con page.route
export const metricasDashboard = {
  periodo: { clave: 'ESTE_MES', desde: '2026-11-01', hasta: '2026-11-05', agrupacion: 'DIA' },
  anterior: { desde: '2026-10-01', hasta: '2026-10-05' },
  tarjetas: { ventas: 0, variacion_ventas: null, pedidos: 0, diferencia_pedidos: 0, ticket_promedio: 0,
    variacion_ticket: null, clientes_nuevos: 0 },
  serie: [], mas_vendidos: [], ultimas_ordenes: [],
  detalles: { medios_pago: [], entregas: [], comunas: [], cancelaciones: [], cupones: [],
    clientes: { nuevos: 0, recurrentes: 0, registrados: 0, invitados: 0 }, calificacion: null },
};

// Toda llamada API queda resuelta aquí o bloqueada. Esta suite no utiliza backend ni credenciales.
export async function prepararTienda(page, { sesion = false, tema = 1, tipografia = 1 } = {}) {
  const inesperadas = [];
  const llamadas = [];
  const configuracion = {
    nombre_tienda: 'Tienda QA', tema_seleccionado: tema, tipografia_seleccionada: tipografia,
    texto_bienvenida: 'Productos de prueba', texto_boton_ingreso: 'Ver catálogo',
    retiro_en_local_activo: true, pasarelas_activas: ['MERCADO_PAGO', 'TRANSFERENCIA'],
    calle_origen: 'Calle de prueba', numero_origen: '148', comuna_origen: 'Santiago',
    banner_url: 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2210%22 height=%2210%22%3E%3Crect width=%2210%22 height=%2210%22 fill=%22%232a2622%22/%3E%3C/svg%3E',
  };
  await page.addInitScript(({ sesion, producto }) => {
    localStorage.setItem('ecode_cookie_consent', 'rejected');
    if (sesion) {
      localStorage.setItem('access_token', 'sesion-simulada');
      localStorage.setItem('rol', 'ADMIN');
    }
    localStorage.setItem('carrito_local', JSON.stringify([{ id: producto.id, sku: 'QA-1', nombre: producto.nombre, precio: 1000, cantidad: 1 }]));
  }, { sesion, producto });
  await page.route('**/api/**', async route => {
    const peticion = route.request();
    const ruta = new URL(peticion.url()).pathname.replace('/api/', '');
    llamadas.push({ metodo: peticion.method(), ruta });
    const respuestas = {
      'configuracion/': configuracion,
      'configuracion/negocio/': configuracion,
      'ventas/dashboard/metricas/': metricasDashboard,
      'ventas/dashboard/pendientes/': { al_dia: true, tareas: [], agotadas: [], stock_bajo: [] },
      'ventas/admin/ordenes/': { count: 0, next: null, previous: null, results: [] },
      'ventas/admin/paginas-legales/': [{ tipo_pagina: 'TERMINOS', titulo: 'Términos QA', contenido: '<p>Texto legal QA.</p>', publicada: true }],
      'ventas/admin/medios-pago/': [],
      'ventas/admin/couriers/': [{ codigo: 'CHILEXPRESS', nombre: 'Chilexpress', ayuda: '', campos: [], datos: {}, faltantes: [], configuradas: false }],
      // Configuración > Página Sobre mí: las publicaciones del blog para elegir y los proyectos elegidos
      'ventas/admin/blog/': [],
      'ventas/admin/sobre-mi/proyectos/': { proyectos: [] },
      'ventas/promociones/': [],
      // Configuración > Suscripciones (pedido de un cliente, opcional): sin planes
      'ventas/admin/suscripciones/planes/': { planes: [] },
      // Sin descuentos automáticos: el checkout los pide para la vista previa
      'ventas/promociones/automaticas/': [],
      'ventas/paginas-legales/': [{ tipo_pagina: 'TERMINOS', titulo: 'Términos' }, { tipo_pagina: 'PRIVACIDAD', titulo: 'Privacidad' }],
      'ventas/checkout/reglas/': { modo_autenticacion: 'INVITADO' },
      'ventas/logistica/comunas/': { comunas: ['Santiago'] },
      'catalogo/vitrina/': { recientes: [producto], mas_vendidos: [] },
      'catalogo/productos/': { count: 1, total_pages: 1, current_page: 1, results: [producto], filtros: { categorias: ['Prueba'], atributos: {} } },
      'catalogo/filtros/': { categorias: ['Prueba'], atributos: {} },
      // Configuración > Renombrar o unir categorías
      'catalogo/categorias/': { categorias: [{ nombre: 'Prueba', productos: 1, publicados: 1 }] },
      [`catalogo/productos/${producto.id}/`]: producto,
      'usuarios/me/': { id: 1, nombre: 'Visitante QA', email: 'qa@example.test', rol: 'ADMIN' },
      'ventas/empresa/': {},
      'ventas/carrito/': { items: [] },
      'ventas/carrito/validar/': { items: [{ producto_mongo_id: producto.id, variante_sku: 'QA-1', disponible: 5, precio: 1000, problema: null }] },
      'ventas/direcciones/': [],
    };
    if (ruta in respuestas) return route.fulfill({ json: respuestas[ruta] });
    if (/ventas\/paginas-legales\/\w+\/$/.test(ruta)) return route.fulfill({ json: { titulo: 'Página legal QA', contenido: '<p>Contenido legal de prueba.</p>' } });
    inesperadas.push(`${peticion.method()} ${ruta}`);
    return route.abort('blockedbyclient');
  });
  return { llamadas, inesperadas };
}

export async function comprobarVista(page) {
  await expect(page.locator('main')).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
}
