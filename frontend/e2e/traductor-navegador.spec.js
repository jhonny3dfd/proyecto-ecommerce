import { test, expect } from '@playwright/test';
import { prepararTienda, producto } from './soporte/tienda';
import { MARCA, traducirComoElNavegador } from './soporte/traductor';

// Un visitante extranjero traduce la tienda con su navegador (Chrome usa el traductor de Google), que cambia los
// textos de la página por los suyos. React no debe caerse ni dejar a la vista textos o montos viejos
// (probado en una tienda publicada el 2026-11-11: "Agregar al carrito" dejaba la página en blanco).

async function abrirFichaTraducida(page) {
  const errores = [];
  page.on('pageerror', (error) => errores.push(error.message));
  const tienda = await prepararTienda(page);
  await page.goto(`/catalogo/producto/${producto.id}`);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await traducirComoElNavegador(page);
  await expect(page.getByRole('heading', { level: 1 })).toContainText(MARCA);
  return { ...tienda, errores };
}

const paginaConContenido = async (page) => expect((await page.locator('main').innerText()).trim().length).toBeGreaterThan(20);

test('con la página traducida se elige la variante y se agrega al carrito sin que la página se caiga', async ({ page }) => {
  const { errores, inesperadas } = await abrirFichaTraducida(page);

  await page.getByRole('button', { name: /^(EN·)?M$/ }).click();
  const agregar = page.locator('.selector-variantes-agregar');
  // El botón muestra lo que corresponde ahora, no el texto que tenía antes de traducirse
  await expect(agregar).toHaveText(`${MARCA}Agregar al carrito`);
  await agregar.click();

  await expect(page.getByRole('status').filter({ hasText: 'Agregaste' })).toBeVisible();
  await expect(agregar).toHaveText(`${MARCA}Agregar al carrito`);
  await paginaConContenido(page);
  expect(errores).toEqual([]);
  expect(inesperadas).toEqual([]);
});

test('con la página traducida el carrito muestra los montos al día al cambiar la cantidad', async ({ page }) => {
  const { errores } = await abrirFichaTraducida(page);

  await page.getByRole('button', { name: /^Carrito de compras/ }).click();
  const precio = page.locator('.carrito-item-precio');
  const total = page.locator('.carrito-total');
  // El carrito parte con 1 unidad de $1.000
  await expect(precio).toContainText('1.000');
  await page.getByRole('button', { name: `Aumentar cantidad de ${producto.nombre}` }).click();
  await expect(precio).toContainText('2.000');
  await expect(total).toContainText('2.000');
  await page.getByRole('button', { name: `Disminuir cantidad de ${producto.nombre}` }).click();
  await expect(precio).toContainText('1.000');
  await expect(total).toContainText('1.000');
  await expect(total).not.toContainText('2.000');

  await page.getByRole('link', { name: /Ir a Pagar/ }).click();
  await expect(page).toHaveURL(/\/checkout$/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Finalizar Compra');
  await expect(page.locator('.checkout-total-linea--final')).toContainText('1.000');
  expect(errores).toEqual([]);
});
