import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda } from './soporte/tienda';

const COURIERS = [
  { codigo: 'CHILEXPRESS', nombre: 'Chilexpress', sucursales: true },
  { codigo: 'STARKEN', nombre: 'Starken', sucursales: false },
];

// RF-02.3: con dos couriers activos el comprador ve las dos tarifas, elige una y el pedido va con esa
test('el comprador elige entre dos couriers y el pedido se envía con el elegido', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page);
  await page.route('**/api/configuracion/', route => route.fulfill({ json: {
    nombre_tienda: 'Tienda QA', tema_seleccionado: 1, tipografia_seleccionada: 1,
    pasarelas_activas: ['TRANSFERENCIA'], retiro_en_local_activo: false, couriers: COURIERS,
  } }));
  const cotizaciones = [];
  await page.route('**/api/ventas/logistica/cotizar/', route => {
    cotizaciones.push(route.request().postDataJSON());
    return route.fulfill({ json: { opciones: [
      { proveedor: 'CHILEXPRESS', nombre: 'Chilexpress', tiempo_estimado: 'EXPRESS', precio: 3990, moneda: 'CLP' },
      { proveedor: 'STARKEN', nombre: 'Starken', tiempo_estimado: '', precio: 3500, moneda: 'CLP' },
    ] } });
  });
  let pedido;
  await page.route('**/api/ventas/checkout/', route => {
    pedido = route.request().postDataJSON();
    return route.fulfill({ json: { orden_id: '148', instrucciones_pago: {
      monto: 4500, referencia: '148', datos: [],
    } } });
  });

  await page.goto('/checkout');
  await expect(page.getByRole('radio', { name: 'A Domicilio' })).toBeChecked();
  await expect(page.getByRole('radio', { name: 'Sucursal Chilexpress' })).toBeVisible();
  await page.getByLabel(/Correo electrónico para el recibo/).fill('qa@example.test');
  await page.getByLabel('Calle').fill('Uno');
  await page.getByLabel('Número', { exact: true }).fill('123');
  await page.getByLabel('Comuna').selectOption('Santiago');
  await page.getByLabel('Ciudad').fill('Santiago');

  // A domicilio cotizan todos los couriers activos: el comprador ve las dos tarifas y elige
  const starken = page.getByRole('radio', { name: /Starken/ });
  await expect(page.getByRole('radio', { name: /Chilexpress - EXPRESS/ })).toBeChecked();
  expect(cotizaciones.at(-1)).not.toHaveProperty('proveedor');
  await starken.check();
  await expect(starken).toBeChecked();
  await expect(page.locator('.checkout-resumen')).toContainText('$3.500');

  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);

  await page.getByLabel(/Nombre de quien recibe/).fill('Comprador de prueba');
  await page.getByLabel(/Teléfono de contacto/).fill('+56911111111');
  await page.getByRole('checkbox', { name: /acepto los/i }).check();
  await page.getByRole('button', { name: 'Pagar con Transferencia bancaria' }).click();

  await expect.poll(() => pedido?.proveedor_logistico).toBe('STARKEN');
  await expect(page.getByRole('heading', { name: '¡Pedido recibido!' })).toBeVisible();
  expect(inesperadas).toEqual([]);
});
