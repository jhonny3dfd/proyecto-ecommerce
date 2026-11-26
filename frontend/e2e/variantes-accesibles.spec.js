import { test, expect } from '@playwright/test';
import { prepararTienda, producto } from './soporte/tienda';

test('la validación asíncrona de stock conserva el foco del comprador', async ({ page }) => {
  const { llamadas, inesperadas } = await prepararTienda(page);
  await page.goto(`/catalogo/producto/${producto.id}`);
  await page.getByRole('button', { name: 'M', exact: true }).press('Space');
  const agregar = page.getByRole('button', { name: 'Agregar al carrito', exact: true });
  await agregar.press('Enter');
  await expect(page.getByRole('status')).toContainText('Agregaste');
  await expect(agregar).toBeFocused();
  expect(llamadas.filter(llamada => llamada.ruta === 'ventas/carrito/validar/')).toHaveLength(1);
  expect(inesperadas).toEqual([]);
});
