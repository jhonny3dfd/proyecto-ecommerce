import { test, expect } from '@playwright/test';
import { prepararTienda } from './soporte/tienda';

async function comprobarTeclado(page, dialogo) {
  await expect(dialogo).toBeVisible();
  await expect(dialogo.locator('[data-foco-inicial]')).toBeFocused();
  const botones = dialogo.locator('button:enabled, a[href]');
  await botones.first().focus();
  await page.keyboard.press('Shift+Tab');
  // El título puede participar en el recorrido inicial; nunca debe enfocarse el fondo.
  expect(await dialogo.evaluate(elemento => elemento.contains(document.activeElement))).toBeTruthy();
  await botones.last().focus();
  await page.keyboard.press('Tab');
  expect(await dialogo.evaluate(elemento => elemento.contains(document.activeElement))).toBeTruthy();
}

for (const resultado of ['pagado', 'cancelado', 'error']) {
  test(`el diálogo conserva una sola orden y consulta periódica: ${resultado}`, async ({ page }) => {
    await page.clock.install();
    const { inesperadas } = await prepararTienda(page);
    let compras = 0;
    let consultas = 0;
    let estado = {};
    let resolver;
    let detener = false;
    await page.addInitScript(() => { window.open = () => ({}); });
    await page.route('**/api/ventas/checkout/', async route => {
      compras++;
      await route.fulfill({ json: { orden_id: '148', token_verificacion: 'verificacion-simulada', url_pago: 'https://pago.example.test/148' } });
    });
    await page.route('**/api/ventas/checkout/verificar-pago/**', async route => {
      consultas++;
      if (detener) await new Promise(resolve => { resolver = resolve; });
      if (estado.error) await route.fulfill({ status: 503, json: { detail: 'Indisponible' } });
      else await route.fulfill({ json: estado });
    });
    await page.goto('/checkout');
    await page.getByRole('radio', { name: /retiro en local/i }).focus();
    await page.keyboard.press('Space');
    await expect(page.getByRole('radio', { name: /retiro en local/i })).toBeChecked();
    await page.getByLabel(/Correo electrónico para el recibo/).fill('qa@example.test');
    await page.getByLabel(/Nombre de quien recibe/).fill('Comprador de prueba');
    await page.getByLabel(/Teléfono de contacto/).fill('+56911111111');
    await page.getByRole('checkbox', { name: /acepto los/i }).check();
    await page.getByRole('button', { name: 'Pagar con Mercado Pago' }).click();
    const dialogo = page.getByRole('dialog');
    await comprobarTeclado(page, dialogo);
    await page.keyboard.press('Escape');
    await expect(dialogo).toHaveCount(0);
    const reabrir = page.getByRole('button', { name: 'Volver a ver el pago pendiente' });
    await expect(reabrir).toBeFocused();
    expect(compras).toBe(1);
    expect(consultas).toBe(0);
    await page.clock.runFor(3000);
    await expect.poll(() => consultas).toBe(1);
    await reabrir.press('Enter');
    await comprobarTeclado(page, dialogo);
    await dialogo.getByRole('button', { name: 'Cerrar y volver al checkout' }).click();
    await expect(reabrir).toBeFocused();
    await reabrir.click();
    // Una consulta lenta no debe solaparse con el botón manual ni con otro intervalo.
    detener = true;
    await page.clock.runFor(3000);
    await expect.poll(() => consultas).toBe(2);
    await expect(dialogo.getByRole('button', { name: /Consultando a Mercado Pago/ })).toBeDisabled();
    await page.clock.runFor(6000);
    expect(consultas).toBe(2);
    estado = resultado === 'error' ? { error: true } : { [resultado]: true };
    detener = false;
    resolver();
    if (resultado === 'pagado') await expect(page).toHaveURL(/pago-exitoso\?orden=148/);
    if (resultado === 'cancelado') {
      await expect(dialogo).toHaveCount(0);
      await expect(page.getByRole('status').filter({ hasText: 'La orden fue cancelada o rechazada.' })).toBeVisible();
    }
    if (resultado === 'error') {
      await expect(dialogo.getByRole('button', { name: /Ya pagué/ })).toBeEnabled();
      await page.clock.runFor(3000);
      await expect.poll(() => consultas).toBe(3);
    } else {
      await page.clock.runFor(6000);
      expect(consultas).toBe(2);
    }
    expect(compras).toBe(1);
    expect(inesperadas).toEqual([]);
  });
}

test('el detalle de historial se cierra y reabre con foco contenido', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  await page.route('**/api/ventas/mis-pedidos/', route => route.fulfill({ json: [
    { id: 148, estado: 'PAGADO', fecha_creacion: '2026-10-01', total: 1000, proveedor_logistico: 'CHILEXPRESS', id_transaccion_pasarela: 'QA148', direccion: { calle: 'Calle QA', numero: '148', comuna: 'Santiago' } },
  ] }));
  await page.goto('/mis-pedidos');
  const abrir = page.getByRole('button', { name: /detalle/i });
  await abrir.click();
  await comprobarTeclado(page, page.getByRole('dialog'));
  await page.keyboard.press('Escape');
  await expect(abrir).toBeFocused();
  await abrir.press('Enter');
  await comprobarTeclado(page, page.getByRole('dialog'));
  await page.getByRole('dialog').getByRole('button', { name: 'Cerrar', exact: true }).click();
  await expect(abrir).toBeFocused();
  expect(inesperadas).toEqual([]);
});
