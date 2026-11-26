import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { prepararTienda } from './soporte/tienda';

const base = {
  email_cliente: 'ana@example.test', total_final: 25000, requiere_revision: false, transiciones_permitidas: [],
  proveedor_logistico: 'RETIRO_LOCAL', metodo_pago: 'TRANSFERENCIA', documento_requerido: 'BOLETA',
  folio_documento: '', folio_nota_credito: '',
};

// El backend simulado: anotar un folio cambia lo que falta emitir, como lo haría domain/documentos_tributarios.py
async function simularPedidos(page) {
  const pedidos = [
    { ...base, id: 5, estado: 'PAGADO', documento_por_emitir: 'BOLETA' },
    { ...base, id: 3, estado: 'PAGADO', metodo_pago: 'TRANSBANK', documento_requerido: null, documento_por_emitir: null },
    { ...base, id: 2, estado: 'CANCELADO', documento_por_emitir: 'NOTA_CREDITO', folio_documento: '120' },
  ];
  const consultas = [];
  const folios = [];
  await page.route('**/api/ventas/admin/ordenes/**', async route => {
    const url = new URL(route.request().url());
    const documento = url.pathname.match(/ordenes\/(\d+)\/documento\/$/);
    if (documento) {
      const { folio } = route.request().postDataJSON();
      const pedido = pedidos.find(p => p.id === Number(documento[1]));
      folios.push([pedido.id, folio]);
      if (pedido.estado === 'CANCELADO') pedido.folio_nota_credito = folio;
      else pedido.folio_documento = folio;
      pedido.documento_por_emitir = null;
      return route.fulfill({ json: pedido });
    }
    consultas.push(Object.fromEntries(url.searchParams));
    const lista = url.searchParams.get('documento') === 'pendiente'
      ? pedidos.filter(p => p.documento_por_emitir) : pedidos;
    return route.fulfill({ json: { count: lista.length, next: null, previous: null, results: lista } });
  });
  return { consultas, folios };
}

async function sinViolaciones(page) {
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(axe.violations).toEqual([]);
}

test('la tienda anota la boleta y la nota de crédito que emitió, y filtra lo pendiente', async ({ page }) => {
  const { inesperadas } = await prepararTienda(page, { sesion: true });
  const { consultas, folios } = await simularPedidos(page);

  await page.goto('/admin');
  await page.getByRole('button', { name: /^Ventas/ }).first().click();
  await expect(page.getByText('Boleta pendiente')).toBeVisible();
  await expect(page.getByText('Voucher de pago')).toBeVisible();
  await sinViolaciones(page);

  // Boleta de la transferencia, solo con el teclado
  await page.getByRole('textbox', { name: 'Folio de la boleta del pedido #5' }).fill('123');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toHaveText('Boleta N° 123 anotada en el pedido #5.');
  const tabla = page.getByRole('region', { name: 'Pedidos y operaciones de venta' });
  await expect(tabla.getByText('Boleta N° 123')).toBeVisible();

  // Nota de crédito del pedido cancelado que ya tenía boleta
  await page.getByRole('textbox', { name: 'Folio de la nota de crédito del pedido #2' }).fill('7');
  await page.getByRole('textbox', { name: 'Folio de la nota de crédito del pedido #2' }).press('Enter');
  await expect(tabla.getByText('Nota de crédito N° 7')).toBeVisible();
  expect(folios).toEqual([[5, '123'], [2, '7']]);

  // Ya no queda nada pendiente
  await page.getByRole('checkbox', { name: 'Solo con boleta o factura pendiente' }).check();
  await expect(page.getByText('No hay boletas, facturas ni notas de crédito pendientes.')).toBeVisible();
  expect(consultas.at(-1)).toEqual({ pagina: '1', documento: 'pendiente' });
  expect(inesperadas).toEqual([]);
});

test('la tienda elige su modelo de emisión en Configuración', async ({ page }) => {
  const { inesperadas, llamadas } = await prepararTienda(page, { sesion: true });
  let guardado;
  await page.route('**/api/configuracion/negocio/', async route => {
    if (route.request().method() === 'PATCH') {
      guardado = route.request().postDataJSON();
      return route.fulfill({ json: { modelo_emision: guardado.modelo_emision } });
    }
    return route.fulfill({ json: { modelo_emision: 'VOUCHER' } });
  });

  await page.goto('/admin');
  await page.getByRole('button', { name: 'Configuración', exact: true }).click();
  const siempre = page.getByRole('radio', { name: /Siempre emito boleta/ });
  await siempre.scrollIntoViewIfNeeded();
  await expect(page.getByRole('radio', { name: /vale como boleta/ })).toBeChecked();
  await siempre.check();
  await page.getByRole('button', { name: 'Guardar modelo de emisión' }).click();

  await expect(page.getByText(/Modelo de emisión guardado/)).toBeVisible();
  expect(guardado).toEqual({ modelo_emision: 'SIEMPRE_BOLETA' });
  await sinViolaciones(page);
  expect(llamadas.length).toBeGreaterThan(0);
  expect(inesperadas).toEqual([]);
});
