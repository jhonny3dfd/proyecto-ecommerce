import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda, producto } from './soporte/tienda';

// Suscripciones (pedido de un cliente, opcional y apagado por defecto): el admin crea un plan, el comprador se
// suscribe y administra su suscripción. La API está simulada: no se usa el backend ni la base

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

const plan = {
  id: 1, nombre: 'Café del mes', descripcion: 'Recién tostado, en tu puerta.', precio: 14990, frecuencia_semanas: 4,
  frecuencia_texto: 'Cada 4 semanas', unidades: 1, beneficios: ['Guía de preparación'], categorias: ['Prueba'],
  productos: [], envio_gratis: true, envio_gratis_compras: false, descuento: 10, activo: true, orden: 1, suscripciones: 1,
};

const opciones = [{
  id: producto.id, nombre: producto.nombre, categoria: 'Prueba', descripcion: '', imagen: null,
  variantes: [
    { sku: 'QA-1', atributos: { talla: 'M' }, disponible: true },
    { sku: 'QA-2', atributos: { talla: 'L' }, disponible: false },
  ],
}];

const suscripcion = (cambios = {}) => ({
  id: 4, plan, estado: 'ACTIVA', estado_texto: 'Activa', producto_mongo_id: producto.id, variante_sku: 'QA-1',
  producto: `${producto.nombre} - M`,
  entrega: { proveedor_logistico: 'RETIRO_LOCAL', direccion_envio_snapshot: {}, nombre_destinatario: 'Visitante QA',
    telefono_destinatario: '+56912345678', texto: 'Retiro en el local' },
  metodo_pago: 'TRANSFERENCIA', proxima_entrega: '2026-12-12', fecha_creacion: '2026-11-11T12:00:00Z',
  pedido_pendiente: { orden_id: 82, total: 14990, ciclo_fecha: '2026-11-14', metodo_pago: 'TRANSFERENCIA' },
  acciones: ['PAUSAR', 'SALTAR', 'ADELANTAR', 'CANCELAR', 'CAMBIAR'],
  cliente: { nombre: 'Visitante QA', email: 'qa@example.test' }, motivo_cancelacion: '',
  ...cambios,
});

async function simularSuscripciones(page, { tema = 1, sesion = true } = {}) {
  const tienda = await prepararTienda(page, { tema, sesion });
  const enviadas = [];
  const planesCreados = [];
  const configuracion = {
    nombre_tienda: 'Tienda QA', tema_seleccionado: tema, texto_bienvenida: 'Productos de prueba',
    suscripciones_activas: true, suscripciones_dias_aviso: 3, retiro_en_local_activo: true, couriers: [],
    pasarelas_activas: ['MERCADO_PAGO', 'TRANSFERENCIA'], calle_origen: 'Calle de prueba', numero_origen: '148',
    comuna_origen: 'Santiago',
  };
  // Registradas después: tienen prioridad sobre las de prepararTienda
  await page.route('**/api/configuracion/', route => route.fulfill({ json: configuracion }));
  await page.route('**/api/configuracion/negocio/', route => route.fulfill({
    json: route.request().method() === 'PATCH' ? { ...configuracion, ...route.request().postDataJSON() } : configuracion,
  }));
  await page.route('**/api/ventas/suscripciones/**', async route => {
    const peticion = route.request();
    const ruta = new URL(peticion.url()).pathname.replace('/api/ventas/suscripciones/', '');
    if (ruta === 'planes/') return route.fulfill({ json: { planes: [plan], dias_aviso: 3 } });
    if (ruta === 'planes/1/opciones/') return route.fulfill({ json: { productos: opciones } });
    if (ruta === 'mias/') return route.fulfill({ json: { suscripciones: [suscripcion()], activas_en_tienda: true } });
    if (ruta === '' && peticion.method() === 'POST') {
      enviadas.push(peticion.postDataJSON());
      return route.fulfill({ status: 201, json: { suscripcion_id: 4, orden_id: 81, total: 14990, token_verificacion: 'x',
        instrucciones_pago: { monto: 14990, referencia: 'Pedido 81', vence: null,
          datos: [{ etiqueta: 'Banco', valor: 'Banco de prueba' }] } } });
    }
    if (ruta === '4/pausar/') {
      return route.fulfill({ json: suscripcion({ estado: 'PAUSADA', estado_texto: 'Pausada', pedido_pendiente: null,
        acciones: ['REANUDAR', 'CANCELAR', 'CAMBIAR'] }) });
    }
    return route.fulfill({ status: 404, json: { detail: 'No encontrado' } });
  });
  await page.route('**/api/ventas/admin/suscripciones/**', async route => {
    const peticion = route.request();
    const ruta = new URL(peticion.url()).pathname.replace('/api/ventas/admin/suscripciones/', '');
    if (ruta === 'planes/' && peticion.method() === 'POST') {
      planesCreados.push(peticion.postDataJSON());
      return route.fulfill({ status: 201, json: { id: 2, orden: 2, frecuencia_texto: 'Cada 2 semanas', ...peticion.postDataJSON() } });
    }
    if (ruta === 'planes/') return route.fulfill({ json: { planes: [plan] } });
    if (ruta === '') return route.fulfill({ json: { count: 1, next: null, previous: null, results: [suscripcion()] } });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.route('**/api/catalogo/productos/?todos=true', route => route.fulfill({ json: [producto] }));
  return { ...tienda, enviadas, planesCreados };
}

test('el comprador se suscribe con transferencia y ve los datos para pagar', async ({ page }) => {
  const { enviadas, inesperadas } = await simularSuscripciones(page);
  await page.goto('/suscripcion');
  await page.getByRole('link', { name: 'Suscribirme a Café del mes' }).click();

  const pagar = page.getByRole('button', { name: /Suscribirme y pagar/ });
  await expect(pagar).toBeDisabled();
  await page.getByRole('radio', { name: new RegExp(producto.nombre) }).check();
  await expect(page.getByRole('option', { name: 'Talla: L (sin stock)' })).toBeDisabled();
  await page.getByLabel('Opción').selectOption('QA-1');
  await page.getByLabel('Teléfono').fill('+56 9 1234 5678');
  await page.getByRole('radio', { name: 'Transferencia bancaria' }).check();
  // RF-04.4: sin aceptar los términos no se puede seguir
  await expect(pagar).toBeDisabled();
  await page.getByRole('checkbox', { name: /Acepto los/ }).check();
  await expect(pagar).toHaveText('Suscribirme y pagar $14.990');
  await pagar.click();

  await expect(page).toHaveURL(/\/pedido-recibido\?orden=81$/);
  await expect(page.getByText('Pedido 81')).toBeVisible();
  expect(enviadas).toEqual([{
    plan_id: 1, producto_mongo_id: producto.id, variante_sku: 'QA-1', proveedor_logistico: 'RETIRO_LOCAL',
    direccion_envio_snapshot: {}, nombre_destinatario: 'Visitante QA', telefono_destinatario: '+56 9 1234 5678',
    metodo_pago: 'TRANSFERENCIA', acepta_terminos: true,
  }]);
  expect(inesperadas).toEqual([]);
});

test('el comprador pausa su suscripción solo con el teclado', async ({ page }) => {
  await simularSuscripciones(page);
  page.on('dialog', dialogo => dialogo.accept());
  await page.goto('/mis-suscripciones');

  const tarjeta = page.getByRole('article', { name: 'Café del mes' });
  await expect(tarjeta.getByRole('link', { name: 'Pagar esta entrega' })).toHaveAttribute('href', '/mis-suscripciones/pagar/82');
  await tarjeta.getByRole('button', { name: 'Pausar' }).focus();
  await page.keyboard.press('Enter');

  await expect(tarjeta.getByText('Pausaste tu suscripción.', { exact: false })).toBeVisible();
  await expect(tarjeta.getByText('En pausa: se fija cuando la reanudes')).toBeVisible();
  await expect(tarjeta.getByRole('button', { name: 'Reanudar' })).toBeVisible();
});

test('el admin crea un plan y ve a sus suscriptores', async ({ page }) => {
  const { planesCreados } = await simularSuscripciones(page);
  await page.goto('/admin');
  await page.getByRole('button', { name: 'Configuración' }).click();
  await page.getByRole('button', { name: 'Suscripciones', exact: true }).click();

  await page.getByRole('button', { name: '+ Nuevo plan' }).click();
  await page.getByLabel('Nombre del plan').fill('Café quincenal');
  await page.getByLabel('Precio por entrega ($)').fill('12990');
  await page.getByLabel('Cada cuánto llega').selectOption('2');
  await page.getByRole('checkbox', { name: 'Prueba', exact: true }).check();
  await page.getByRole('button', { name: 'Crear plan' }).click();

  await expect(page.getByText('Creaste el plan "Café quincenal".')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Café quincenal' })).toBeVisible();
  expect(planesCreados[0]).toMatchObject({ nombre: 'Café quincenal', precio: 12990, frecuencia_semanas: 2, categorias: ['Prueba'] });

  await page.getByRole('button', { name: 'Suscriptores' }).click();
  const tarjeta = page.getByRole('article', { name: 'Visitante QA · Café del mes' });
  await expect(tarjeta.getByText(/Pedido #82 de \$14\.990/)).toBeVisible();
});

for (const tema of [1, 2, 3, 4, 5, 6, 7, 8]) {
  test(`las páginas de suscripción cumplen WCAG AA en la paleta ${tema}, en escritorio y celular`, async ({ page }) => {
    await simularSuscripciones(page, { tema });
    for (const ancho of [1280, 375]) {
      await page.setViewportSize({ width: ancho, height: 900 });
      for (const ruta of ['/suscripcion', '/suscripcion/1', '/mis-suscripciones', '/mis-suscripciones/pagar/82']) {
        await page.goto(ruta);
        await expect(page.locator('h1')).toBeVisible();
        if (ruta === '/suscripcion/1') {
          // Con un producto elegido: la opción invertida y el resumen completo
          await page.getByRole('radio', { name: new RegExp(producto.nombre) }).check();
        }
        await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
        const axe = await new AxeBuilder({ page }).include('main').withTags(WCAG).analyze();
        expect(axe.violations, `${ruta} a ${ancho}px`).toEqual([]);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${ruta} a ${ancho}px`).toBeTruthy();
      }
    }
  });
}

test('el panel de suscripciones cumple WCAG AA', async ({ page }) => {
  await simularSuscripciones(page);
  for (const ancho of [1280, 375]) {
    await page.setViewportSize({ width: ancho, height: 900 });
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Suscriptores' }).click();
    await expect(page.getByRole('article', { name: 'Visitante QA · Café del mes' })).toBeVisible();
    const axe = await new AxeBuilder({ page }).include('main').withTags(WCAG).analyze();
    expect(axe.violations, `Suscriptores a ${ancho}px`).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  }
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('button', { name: 'Configuración' }).click();
  await page.getByRole('button', { name: 'Suscripciones', exact: true }).click();
  await page.getByRole('button', { name: 'Editar Café del mes' }).click();
  const axe = await new AxeBuilder({ page }).include('#config-suscripciones').withTags(WCAG).analyze();
  expect(axe.violations).toEqual([]);
});
